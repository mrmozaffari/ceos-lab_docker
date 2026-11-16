#!/usr/bin/env python3

import argparse
import os
import sys
import yaml
import ipaddress
import hashlib
import subprocess
import json
import logging
import re
import shutil
from collections import defaultdict
from mgmt_network import ensure_or_select_mgmt_network


DEFAULT_SUBNET_POOL = ipaddress.ip_network('172.16.0.0/16')

# Written to devices/<device>/startup-config for every device
STARTUP_CONFIG = (
    "event-handler ENABLE-ENTROPY\n"
    "   trigger on-boot\n"
    "   action bash bash /mnt/flash/enable_entropy.sh\n"
    "   delay 90\n"
    "   asynchronous\n"
    "!\n"
    "interface Management1\n"
    "   no lldp transmit\n"
    "   no lldp receive\n"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate docker-compose.yml and device configs for cEOS lab."
    )
    parser.add_argument(
        'topology',
        nargs='?',
        default='topology.yml',
        help='Topology YAML file (default: topology.yml)'
    )
    parser.add_argument('--auto', action='store_true', help='Run in non-interactive mode with defaults')
    parser.add_argument('--dry-run', action='store_true', help='Validate everything but don’t create files or networks')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging to generate-lab.log')
    parser.add_argument('--parent', help='Specify parent interface explicitly (e.g., eth0)')
    parser.add_argument('--update', action='store_true',
                        help='Update a lab that already exists in this folder: keep the existing links and subnets, '
                             'add/remove/change only what differs, and print the exact commands to apply it')
    parser.add_argument('--fresh', action='store_true',
                        help='Ignore an existing docker-compose.yml and generate everything from scratch')
    parser.add_argument('--reset-startup', action='store_true',
                        help='Overwrite existing devices/<dev>/flash/startup-config with the generated default '
                             '(default: keep saved configs)')
    return parser.parse_args()


def setup_logging(verbose):
    if verbose:
        logging.basicConfig(
            filename='generate-lab.log',
            level=logging.INFO,
            format='%(asctime)s %(levelname)s: %(message)s'
        )
        logging.info("Logging started")


def normalize_linux_nodes(topo):
    """linux_nodes can be written the short way. All of these are the same node with the default image:
         linux_nodes: [Host1, Host2]          (a list of names)
         linux_nodes: {Host1: , Host2: }      (names without settings)
         linux_nodes: {Host1: pvlan-sw:latest} (a name with just an image)
       or the long way with image/isolated/vlan. Returns {name: settings dict}."""
    raw = topo.get('linux_nodes') or {}
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, list):
        raw = {n: None for n in raw}
    if not isinstance(raw, dict):
        raise ValueError("'linux_nodes' must be a list of names or a mapping of name to settings")
    nodes = {}
    for name, cfg in raw.items():
        if cfg is None:
            cfg = {}
        elif isinstance(cfg, str):
            cfg = {'image': cfg}
        elif not isinstance(cfg, dict):
            raise ValueError(f"linux_nodes '{name}': settings must be a mapping or an image name")
        nodes[str(name)] = cfg
    return nodes


def validate_topology(topo):
    if not isinstance(topo, dict):
        raise ValueError("Topology file is not a YAML dictionary")
    if 'connections' not in topo or not isinstance(topo['connections'], list):
        raise ValueError("Missing or invalid 'connections' section")
    for conn in topo['connections']:
        if not all(k in conn for k in ('device1', 'intf1', 'device2', 'intf2')):
            raise ValueError(f"Invalid connection entry: {conn}")
    used = defaultdict(list)
    for n, conn in enumerate(topo['connections'], 1):
        for dev, intf in ((conn['device1'], conn['intf1']), (conn['device2'], conn['intf2'])):
            used[(dev, intf)].append(n)
    dups = [f"{dev} {intf} (connections #{', #'.join(map(str, nums))})"
            for (dev, intf), nums in used.items() if len(nums) > 1]
    if dups:
        raise ValueError("duplicate interface, an interface can only be used by one connection: " + "; ".join(dups))
    linux = normalize_linux_nodes(topo)
    for name, cfg in linux.items():
        labels = [c[i] for c in topo['connections']
                  for d, i in (('device1', 'intf1'), ('device2', 'intf2')) if c[d] == name]
        if not labels:
            continue      # not connected: main() warns and leaves it out
        for lbl in cfg.get('isolated', []) or []:
            if lbl not in labels:
                raise ValueError(f"linux_nodes '{name}': isolated port '{lbl}' is not in its connections")


def get_existing_docker_subnets():
    output = subprocess.check_output(['docker', 'network', 'ls', '-q']).decode().splitlines()
    existing_subnets = set()
    for net_id in output:
        info = json.loads(subprocess.check_output(['docker', 'network', 'inspect', net_id]).decode())[0]
        ipam = info.get('IPAM')
        if not ipam or not ipam.get('Config'):
            continue
        for cfg in ipam['Config']:
            if 'Subnet' in cfg:
                existing_subnets.add(ipaddress.ip_network(cfg['Subnet']))
    return existing_subnets


def next_subnet(used_subnets, existing_docker_subnets, base_subnet, prefixlen=24):
    for subnet in base_subnet.subnets(new_prefix=prefixlen):
        if subnet in used_subnets or any(subnet.overlaps(existing) for existing in existing_docker_subnets):
            continue
        used_subnets.add(subnet)
        return subnet
    raise Exception("No more available subnets!")


# ---------------------------------------------------------------------------------------------
# Incremental update support
#
# A lab is a set of point to point links. Each link is one docker network (link01, link02 ...)
# and a device's interfaces are numbered eth1, eth2 ... in the order of the NAMES of the links
# it is attached to. The label list of a device (eth1=Ethernet1 ...) therefore follows the link
# numbers, not the order of the lines in the topology file. A fresh lab numbers links in file
# order, so both orders are the same. In update mode existing links keep their number, and new
# links get the next free numbers.
# ---------------------------------------------------------------------------------------------

def link_net_name(n):
    return f'link{n:02d}'


def link_number(net_name):
    return int(net_name[4:])


def conn_ends(conn):
    return ((conn['device1'], conn['intf1']), (conn['device2'], conn['intf2']))


def ports_per_device(links):
    """Ordered interface labels per device: eth1 is the first one, eth2 the second ..."""
    per = defaultdict(list)
    for link in sorted(links, key=lambda l: l['net_name']):
        per[link['device1']].append(link['intf1'])
        per[link['device2']].append(link['intf2'])
    return dict(per)


def device_link_state(links):
    """device -> [(net_name, label), ...] in eth order. Used to see which devices changed."""
    per = defaultdict(list)
    for link in sorted(links, key=lambda l: l['net_name']):
        per[link['device1']].append((link['net_name'], link['intf1']))
        per[link['device2']].append((link['net_name'], link['intf2']))
    return dict(per)


def load_lab_state(compose_path='docker-compose.yml', devices_dir='devices'):
    """Rebuild the links of the CURRENT lab from docker-compose.yml and the interface mapping of each
    device (devices/<dev>/flash/EosIntfMapping.json for cEOS, PORT_MAP for Linux nodes).
    Returns (links, services, mgmt_net). No extra state file is needed, so labs created by older
    versions of this script can be updated too."""
    with open(compose_path) as f:
        comp = yaml.safe_load(f) or {}
    nets = comp.get('networks') or {}
    services = comp.get('services') or {}
    mgmt_net = next((n for n, cfg in nets.items() if (cfg or {}).get('external')), None)
    link_nets = {}
    for name, cfg in nets.items():
        ipam_cfg = (((cfg or {}).get('ipam') or {}).get('config') or [])
        if name.startswith('link') and ipam_cfg:
            link_nets[name] = ipaddress.ip_network(ipam_cfg[0]['subnet'])

    ends_by_net = defaultdict(list)
    for dev, svc in services.items():
        env = svc.get('environment') or {}
        if isinstance(env, list):
            env = dict(e.split('=', 1) for e in env if '=' in e)
        if 'PORT_MAP' in env:
            pairs = [kv.split('=', 1) for kv in str(env['PORT_MAP']).split()]
            labels = [k for k, v in sorted(pairs, key=lambda kv: int(kv[1][3:]))]
        else:
            mapping_file = os.path.join(devices_dir, dev, 'flash', 'EosIntfMapping.json')
            if not os.path.isfile(mapping_file):
                raise ValueError(f"{mapping_file} not found, cannot read the interfaces of {dev}")
            with open(mapping_file) as f:
                eth = json.load(f)['EthernetIntf']
            labels = [eth[k] for k in sorted(eth, key=lambda k: int(k[3:]))]
        dev_nets = sorted(n for n in (svc.get('networks') or []) if n in link_nets)
        if len(dev_nets) != len(labels):
            raise ValueError(f"{dev}: {len(dev_nets)} link networks but {len(labels)} interface labels")
        for net, label in zip(dev_nets, labels):
            ends_by_net[net].append((dev, label))

    links = []
    for net, subnet in link_nets.items():
        ends = ends_by_net.get(net, [])
        if len(ends) != 2:
            raise ValueError(f"{net} has {len(ends)} endpoints, expected 2")
        links.append({'net_name': net, 'subnet': subnet,
                      'device1': ends[0][0], 'intf1': ends[0][1],
                      'device2': ends[1][0], 'intf2': ends[1][1]})
    return links, services, mgmt_net


def plan_update(old_links, connections, base_subnet, existing_docker_subnets):
    """Compare the links of the running lab with the topology file.
    1. same two endpoints (device and interface)        -> kept: same network, same subnet
    2. same two devices but another interface label     -> changed: same network, same subnet
    3. anything else in the file                        -> added: next free link number, new subnet
    4. old links nobody claimed                         -> removed
    Returns (links in file order with 'status', removed links)."""
    left = list(old_links)
    claimed = [None] * len(connections)
    status = [None] * len(connections)

    for i, conn in enumerate(connections):
        key = frozenset(conn_ends(conn))
        for old in left:
            if frozenset(((old['device1'], old['intf1']), (old['device2'], old['intf2']))) == key:
                claimed[i], status[i] = old, 'kept'
                left.remove(old)
                break
    for i, conn in enumerate(connections):
        if claimed[i] is not None:
            continue
        pair = frozenset((conn['device1'], conn['device2']))
        for old in left:
            if frozenset((old['device1'], old['device2'])) == pair:
                claimed[i], status[i] = old, 'changed'
                left.remove(old)
                break

    used_subnets = {o['subnet'] for o in old_links if o not in left}
    next_n = max([link_number(o['net_name']) for o in old_links] + [0]) + 1
    links = []
    for i, conn in enumerate(connections):
        old = claimed[i]
        if old is None:
            if next_n > 99:
                raise ValueError("More than 99 links: link names would no longer sort in order")
            link = {'net_name': link_net_name(next_n),
                    'subnet': next_subnet(used_subnets, existing_docker_subnets, base_subnet),
                    'status': 'added'}
            next_n += 1
        else:
            link = {'net_name': old['net_name'], 'subnet': old['subnet'], 'status': status[i]}
        link.update({'device1': conn['device1'], 'intf1': conn['intf1'],
                     'device2': conn['device2'], 'intf2': conn['intf2']})
        links.append(link)
    return links, left


def describe_link(l):
    return f"{l['device1']} {l['intf1']} <-> {l['device2']} {l['intf2']}"


def print_update_plan(links, removed, old_links, old_services, new_services=None):
    """Show what changes. Returns the list of devices that must be (re)created."""
    old_state = device_link_state(old_links)
    new_state = device_link_state(links)
    added = [l for l in links if l['status'] == 'added']
    changed = [l for l in links if l['status'] == 'changed']
    old_by_net = {o['net_name']: o for o in old_links}

    print("\n🔎 Changes compared with the running lab:")
    for l in added:
        print(f"  + link  {l['net_name']}  {describe_link(l)}   ({l['subnet']})")
    for l in changed:
        print(f"  ~ link  {l['net_name']}  {describe_link(old_by_net[l['net_name']])}  ->  {describe_link(l)}")
    for o in removed:
        print(f"  - link  {o['net_name']}  {describe_link(o)}")
    if not (added or changed or removed):
        print("  (no link changes)")

    new_devs = sorted(d for d in new_state if d not in old_state)
    gone_devs = sorted(d for d in old_state if d not in new_state)
    changed_devs = sorted(d for d in new_state if d in old_state and new_state[d] != old_state[d])
    # a service whose compose settings changed (image, isolated ports, ...) is recreated too
    if new_services is not None:
        for d in sorted(new_state):
            if d in old_state and d not in changed_devs and old_services.get(d) != new_services.get(d):
                changed_devs.append(d)
    for d in new_devs:
        print(f"  + device {d}")
    for d in gone_devs:
        print(f"  - device {d}   (its devices/{d} folder is kept)")
    for d in changed_devs:
        print(f"  ~ device {d}   interfaces changed, it will be recreated")
    return new_devs + changed_devs, gone_devs


def mac_from_name(name):
    h = hashlib.md5(name.encode()).hexdigest()
    return f'02:{h[0:2]}:{h[2:4]}:{h[4:6]}:{h[6:8]}:{h[8:10]}'


LINUX_DEFAULT_IMAGE = 'pvlan-sw:latest'


def linux_ports(device, connections):
    """Ordered list of the interface labels a device uses; label i becomes eth(i+1) in the container."""
    ports = []
    for conn in connections:
        for dev_key, intf_key in (('device1', 'intf1'), ('device2', 'intf2')):
            if conn[dev_key] == device:
                ports.append(conn[intf_key])
    return ports


def linux_env(device, cfg, connections, ports=None):
    """VLANs are NOT defined here, they are created inside the container with the pvlan command.
    Optional boot-time settings in the topology: isolated (list of port labels), vlan (pre-create it)."""
    cfg = cfg or {}
    ports = ports if ports is not None else linux_ports(device, connections)
    isolated = set(cfg.get('isolated') or [])
    env = {
        'PORT_MAP': ' '.join(f"{p}=eth{i+1}" for i, p in enumerate(ports)),
        'ISOLATED_PORTS': ' '.join(f"eth{i+1}" for i, p in enumerate(ports) if p in isolated),
    }
    if cfg.get('vlan') is not None:
        env['VLAN'] = str(cfg['vlan'])
    return env


ENTROPY_SCRIPTS = ('setup_entropy.sh', 'enable_entropy.sh')


def seed_startup_config(device, device_dir, flash_dir, reset):
    """Create flash/startup-config without ever overwriting a saved config."""
    target = os.path.join(flash_dir, 'startup-config')
    legacy = os.path.join(device_dir, 'startup-config')  # old single-file mount location

    if os.path.isfile(target) and not reset:
        print(f"  {device}: keeping existing flash/startup-config")
        return
    if os.path.isfile(target) and reset:
        shutil.copy2(target, target + '.bak')
    if os.path.isfile(legacy) and not reset:
        shutil.copy2(legacy, target)  # migrate, legacy file is left in place as a backup
        print(f"  {device}: migrated legacy startup-config into flash/")
        return
    with open(target, 'w') as f:
        f.write(STARTUP_CONFIG)


def generate_device_files(devices, connections, dry_run, reset_startup=False, linux_nodes=None, ports=None):
    """Build devices/<device>/flash/, which is bind-mounted as a whole onto /mnt/flash.
    ports: device -> ordered interface labels (eth1, eth2 ...). Defaults to the order in the file."""
    volume_paths = {}
    interface_mapping_per_device = defaultdict(list)

    if ports is not None:
        interface_mapping_per_device.update(ports)
    else:
        for conn in connections:
            for dev_key, intf_key in [('device1', 'intf1'), ('device2', 'intf2')]:
                interface_mapping_per_device[conn[dev_key]].append(conn[intf_key])

    if dry_run:
        print("📝 Dry-run: would generate device configs.")
        return {}

    os.makedirs('devices', exist_ok=True)

    for device, intfs in interface_mapping_per_device.items():
        if device in (linux_nodes or {}):
            continue  # plain Linux container, no cEOS flash/config needed
        device_dir = os.path.join('devices', device)
        flash_dir = os.path.join(device_dir, 'flash')
        os.makedirs(flash_dir, exist_ok=True)

        with open(os.path.join(flash_dir, 'ceos-config'), 'w') as f:
            f.write(f"SERIALNUMBER={device.upper()}-SN\n")
            f.write(f"SYSTEMMACADDR={mac_from_name(device)}\n")
            f.write("TFA_VERSION=2\n")

        mapping = {
            "ManagementIntf": {"eth0": "Management1"},
            "EthernetIntf": {f"eth{i+1}": iface for i, iface in enumerate(intfs)}
        }
        with open(os.path.join(flash_dir, 'EosIntfMapping.json'), 'w') as f:
            json.dump(mapping, f, indent=2)

        seed_startup_config(device, device_dir, flash_dir, reset_startup)

        for name in ENTROPY_SCRIPTS:
            if os.path.isfile(name):
                shutil.copy2(name, os.path.join(flash_dir, name))
            else:
                print(f"⚠️ {name} not found next to the script, not copied to {device}/flash")

        volume_paths[device] = {'flash': os.path.abspath(flash_dir)}

    return volume_paths


def select_ceos_image(auto, dry_run):
    output = subprocess.check_output(['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}']).decode()
    images = [line for line in output.splitlines() if line.startswith('ceos')]
    if not images:
        print("❌ No ceos images found. Please import one and try again.")
        sys.exit(1)

    print("\n📋 Available ceos images:")
    for idx, img in enumerate(images, 1):
        print(f"  {idx}. {img}")

    if auto or dry_run:
        print(f"✅ Auto/Dry-run: would select {images[0]}")
        return images[0]

    while True:
        choice = input("👉 Enter the number of the image you want to use: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(images):
            return images[int(choice)-1]
        print("⚠️ Invalid choice. Try again.")


def generate_compose(devices, links, mgmt_net, volume_paths, ceos_image, dry_run, linux_nodes=None, connections=None,
                     ports=None, write=True):
    if dry_run:
        print("📝 Dry-run: would generate docker-compose.yml.")
        return

    compose = {'version': '3.7', 'services': {}, 'networks': {mgmt_net: {'external': True}}}

    for idx, link in enumerate(links, 1):
        net_name = link.get('net_name') or f'link{idx:02d}'
        link['net_name'] = net_name
        compose['networks'][net_name] = {
            'driver': 'bridge',
            'ipam': {'config': [{'subnet': str(link["subnet"])}]}
        }

    for device in devices:
        nets = [mgmt_net] + sorted(link['net_name'] for link in links if device in (link['device1'], link['device2']))
        paths = volume_paths.get(device, {})

        if device in (linux_nodes or {}):
            cfg = linux_nodes[device] or {}
            compose['services'][device] = {
                'image': cfg.get('image', LINUX_DEFAULT_IMAGE),
                'privileged': True,
                'hostname': device,
                'labels': {'lab.kind': 'linux'},
                'environment': linux_env(device, cfg, connections, (ports or {}).get(device)),
                'volumes': [
                    {'type': 'bind', 'source': os.path.abspath(os.path.join('devices', device, 'config')),
                     'target': '/config'},
                ],
                'networks': nets,
            }
            continue

        compose['services'][device] = {
            'image': ceos_image,
            'privileged': True,
            'hostname': device,
            'volumes': [
                {'type': 'bind', 'source': paths.get('flash', ''), 'target': '/mnt/flash'},
            ],
            'environment': {
                'CEOS': '1', 'EOS_PLATFORM': 'ceoslab', 'container': 'docker',
                'ETBA': '1', 'INTFTYPE': 'eth', 'SKIP_ZEROTOUCH_BARRIER_IN_SYSDBINIT': '1'
            },
            'command': (
                '/sbin/init systemd.setenv=INTFTYPE=eth systemd.setenv=ETBA=1 '
                'systemd.setenv=CEOS=1 systemd.setenv=EOS_PLATFORM=ceoslab '
                'systemd.setenv=container=docker systemd.setenv=MAPETH0=1 '
                'systemd.setenv=MGMT_INTF=eth0'
            ),
            'networks': nets
        }

    if write:
        with open('docker-compose.yml', 'w') as f:
            yaml.dump(compose, f, default_flow_style=False, sort_keys=False)
    return compose


def choose_mode(args):
    """'update' keeps the running lab's links and subnets, 'fresh' generates everything again."""
    if args.update and args.fresh:
        print("❌ Use either --update or --fresh, not both.")
        sys.exit(1)
    if not os.path.isfile('docker-compose.yml'):
        if args.update:
            print("❌ --update needs an existing docker-compose.yml in this folder.")
            sys.exit(1)
        return 'fresh'
    if args.fresh:
        return 'fresh'
    if args.update:
        return 'update'
    if args.auto or args.dry_run:
        return 'fresh'      # same behaviour as before, ask for --update explicitly
    print("\n📄 A docker-compose.yml already exists in this folder.")
    print("  [U] Update it in place: keep the existing links and subnets, change only what differs (default)")
    print("  [F] Fresh: generate everything again (new subnets, meant for a lab that is stopped or deleted)")
    print("  [C] Cancel")
    while True:
        choice = input("👉 Choose [U/f/c]: ").strip().lower() or 'u'
        if choice in ('u', 'update'):
            return 'update'
        if choice in ('f', 'fresh'):
            return 'fresh'
        if choice in ('c', 'cancel'):
            sys.exit(0)


def print_apply_commands(recreate, gone, removed, old_services=None, linux_nodes=None):
    project = re.sub(r'[^a-z0-9_-]', '', os.path.basename(os.getcwd()).lower())
    old_services = old_services or {}
    # running Linux nodes whose settings are not on disk yet (started before the /config mount existed):
    # their pvlan settings are saved by hand once, before the node is recreated
    legacy = [d for d in recreate if d in (linux_nodes or {}) and d in old_services
              and not os.path.isfile(os.path.join('devices', d, 'config', 'pvlan.conf'))]
    step = 1
    if legacy:
        print("👉 Step 1: save the pvlan settings of these running Linux nodes (needed once, no saved config on the host yet):")
        for d in legacy:
            c = f'$(docker ps -q --filter label=com.docker.compose.project={project} --filter label=com.docker.compose.service={d})'
            print(f"   c={c}; docker cp pvlan-sw/pvlan $c:/root/pvlan && docker exec $c sh -c 'chmod +x /root/pvlan && /root/pvlan save'"
                  f" && docker cp $c:/config/pvlan.conf devices/{d}/config/pvlan.conf")
        step = 2
        print(f"\n👉 Step {step}: apply the changes to the running lab:")
    else:
        print("👉 Apply the changes to the running lab:")
    print("   docker-compose up -d --remove-orphans" + (" --force-recreate " + " ".join(recreate) if recreate else ""))
    if recreate:
        print("   Devices listed above are recreated: cEOS keeps its saved config (run 'write memory' first),")
        print("   Linux nodes restore their pvlan settings (vlans, vrfs, IPs, tags) from devices/<node>/config.")
        print("   All other devices keep running untouched.")
        if any(d in (linux_nodes or {}) for d in recreate):
            print("   Rebuild the pvlan-sw image first if you have not since the save/restore feature was added.")
    if removed:
        print("\n🧹 Afterwards remove the networks of the deleted links (optional):")
        for o in removed:
            print(f"   docker network rm {project}_{o['net_name']}")
    print()


def main():
    args = parse_args()
    setup_logging(args.verbose)

    if not os.path.isfile(args.topology):
        print(f"❌ Topology file '{args.topology}' does not exist.")
        sys.exit(1)

    with open(args.topology) as f:
        topo = yaml.safe_load(f)

    try:
        validate_topology(topo)
    except Exception as e:
        print(f"❌ Invalid topology file: {e}")
        sys.exit(1)

    base_subnet = ipaddress.ip_network(topo.get('subnet_pool', str(DEFAULT_SUBNET_POOL)))
    connections = topo['connections']

    mgmt_net, _ = ensure_or_select_mgmt_network(args.topology, auto=args.auto, dry_run=args.dry_run, parent=args.parent)

    mode = choose_mode(args)
    existing_docker_subnets = get_existing_docker_subnets()
    linux_nodes = normalize_linux_nodes(topo)
    seen = {c[k] for c in connections for k in ('device1', 'device2')}
    for name in [n for n in linux_nodes if n not in seen]:
        print(f"⚠️  linux node '{name}' has no connection, it is left out. Add a link to it to create it.")
        del linux_nodes[name]
    old_links = old_services = None
    removed = []

    if mode == 'update':
        try:
            old_links, old_services, old_mgmt = load_lab_state()
        except Exception as e:
            print(f"❌ Cannot read the current lab from docker-compose.yml: {e}")
            print("   Use --fresh to generate everything from scratch.")
            sys.exit(1)
        if old_mgmt and old_mgmt != mgmt_net:
            print(f"❌ The management network changed ({old_mgmt} -> {mgmt_net}). Use --fresh.")
            sys.exit(1)
        try:
            links, removed = plan_update(old_links, connections, base_subnet, existing_docker_subnets)
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
    else:
        used_subnets = set()
        links = []
        for idx, link in enumerate(connections, 1):
            subnet = next_subnet(used_subnets, existing_docker_subnets, base_subnet)
            links.append({
                'net_name': link_net_name(idx),
                'device1': link['device1'], 'intf1': link['intf1'],
                'device2': link['device2'], 'intf2': link['intf2'],
                'subnet': subnet
            })

    devices = {}
    for link in links:
        devices.setdefault(link['device1'], set()).add(link['intf1'])
        devices.setdefault(link['device2'], set()).add(link['intf2'])
    ports = ports_per_device(links)

    if linux_nodes:
        print("\n🐧 Linux nodes: " + ", ".join(linux_nodes))
    ceos_image = None
    if any(d not in linux_nodes for d in devices):
        old_ceos = [svc['image'] for svc in (old_services or {}).values()
                    if (svc.get('labels') or {}).get('lab.kind') != 'linux' and svc.get('image')]
        if old_ceos:
            ceos_image = old_ceos[0]
            print(f"\n✅ Keeping the cEOS image of the running lab: {ceos_image}")
        else:
            ceos_image = select_ceos_image(auto=args.auto, dry_run=args.dry_run)

    recreate = []
    if mode == 'update':
        preview_paths = {d: {'flash': os.path.abspath(os.path.join('devices', d, 'flash'))} for d in devices}
        preview = generate_compose(devices, [dict(l) for l in links], mgmt_net, preview_paths, ceos_image,
                                   dry_run=False, linux_nodes=linux_nodes, connections=connections,
                                   ports=ports, write=False)
        recreate, gone = print_update_plan(links, removed, old_links, old_services, preview['services'])

    if args.dry_run:
        print("\n📝 Dry-run completed successfully, nothing was written.")
        return

    volume_paths = generate_device_files(devices, connections, dry_run=False,
                                         reset_startup=args.reset_startup, linux_nodes=linux_nodes, ports=ports)
    for d in devices:
        if d in linux_nodes:
            os.makedirs(os.path.join('devices', d, 'config'), exist_ok=True)
    generate_compose(devices, links, mgmt_net, volume_paths, ceos_image, dry_run=False,
                     linux_nodes=linux_nodes, connections=connections, ports=ports)

    print("\n✅ docker-compose.yml generated successfully. 🎉\n")
    if mode == 'update':
        print_apply_commands(recreate, gone, removed, old_services, linux_nodes)
        return
    print("👉 To start your lab:\n   docker-compose up -d\n\n👉 To tear it down:\n   docker-compose down\n")
    show = input("👀 Would you like to see the contents of docker-compose.yml? [y/N]: ").strip().lower()
    if show == 'y':
        with open('docker-compose.yml') as f:
            print("\n" + f.read())


if __name__ == "__main__":
    main()
