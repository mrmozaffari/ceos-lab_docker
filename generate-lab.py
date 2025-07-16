import os
import sys
import yaml
import ipaddress
import hashlib
import subprocess
import json
from collections import defaultdict
from mgmt_network import ensure_or_select_mgmt_network

DEFAULT_SUBNET_POOL = ipaddress.ip_network('172.16.0.0/16')


def get_existing_docker_subnets():
    try:
        network_ids = subprocess.check_output(['docker', 'network', 'ls', '-q']).decode().splitlines()
        if not network_ids:
            return set()
        existing_subnets = set()
        for net_id in network_ids:
            output = subprocess.check_output(['docker', 'network', 'inspect', net_id])
            network_info = json.loads(output.decode())[0]
            if 'IPAM' in network_info and 'Config' in network_info['IPAM']:
                for cfg in network_info['IPAM']['Config']:
                    if 'Subnet' in cfg:
                        existing_subnets.add(ipaddress.ip_network(cfg['Subnet']))
        return existing_subnets
    except subprocess.CalledProcessError as e:
        print(f"Error getting Docker network info: {e}")
        sys.exit(1)


def next_subnet(used_subnets, existing_docker_subnets, base_subnet, prefixlen=24):
    for subnet in base_subnet.subnets(new_prefix=prefixlen):
        if subnet in used_subnets or any(subnet.overlaps(existing) for existing in existing_docker_subnets):
            continue
        used_subnets.add(subnet)
        return subnet
    raise Exception("No more available subnets!")


def mac_from_name(name):
    h = hashlib.md5(name.encode()).hexdigest()
    return f'02:{h[0:2]}:{h[2:4]}:{h[4:6]}:{h[6:8]}:{h[8:10]}'


def generate_device_files(devices, connections):
    volume_paths = {}
    interface_mapping_per_device = defaultdict(list)

    for conn in connections:
        for dev_key, intf_key in [('device1', 'intf1'), ('device2', 'intf2')]:
            device = conn[dev_key]
            intf = conn[intf_key]
            if intf not in interface_mapping_per_device[device]:
                interface_mapping_per_device[device].append(intf)

    base_devices_dir = os.path.abspath('devices')
    os.makedirs(base_devices_dir, exist_ok=True)

    for device in devices:
        device_dir = os.path.join(base_devices_dir, device)
        os.makedirs(device_dir, exist_ok=True)

        ceos_config_path = os.path.join(device_dir, 'ceos-config')
        with open(ceos_config_path, 'w') as f:
            f.write(f"SERIALNUMBER={device.upper()}-SN\n")
            f.write(f"SYSTEMMACADDR={mac_from_name(device)}\n")
            f.write("TFA_VERSION=2\n")

        ordered_intfs = interface_mapping_per_device[device]
        mapping = {
            "ManagementIntf": {"eth0": "Management1"},
            "EthernetIntf": {f"eth{idx+1}": iface for idx, iface in enumerate(ordered_intfs)}
        }

        eos_mapping_path = os.path.join(device_dir, 'EosIntfMapping.json')
        with open(eos_mapping_path, 'w') as f:
            json.dump(mapping, f, indent=2)

        volume_paths[device] = {
            'ceos_config': ceos_config_path,
            'eos_mapping': eos_mapping_path
        }

    return volume_paths


def select_ceos_image():
    try:
        output = subprocess.check_output(['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}']).decode()
        images = [line for line in output.splitlines() if line.startswith('ceos')]
        if not images:
            print("❌ No ceos images found. Please import one and try again.")
            sys.exit(1)

        print("\n📋 Available ceos images:")
        for idx, img in enumerate(images, 1):
            print(f"  {idx}. {img}")

        while True:
            choice = input("👉 Enter the number of the image you want to use: ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(images)):
                print("⚠️ Invalid choice. Please enter a valid number.")
                continue
            return images[int(choice)-1]

    except subprocess.CalledProcessError as e:
        print(f"❌ Error listing Docker images: {e}")
        sys.exit(1)


def generate_compose(devices, links, mgmt_net, volume_paths, ceos_image):
    compose = {
        'version': '3.7',
        'services': {},
        'networks': {mgmt_net: {'external': True}}
    }

    for idx, link in enumerate(links, start=1):
        net_name = f'link{idx:02d}'
        link['net_name'] = net_name
        compose['networks'][net_name] = {
            'driver': 'bridge',
            'ipam': {'config': [{'subnet': str(link["subnet"])}]}
        }

    for device in devices:
        paths = volume_paths[device]
        service_networks = [mgmt_net] + [link['net_name'] for link in links if device in (link['device1'], link['device2'])]

        compose['services'][device] = {
            'image': ceos_image,
            'privileged': True,
            'hostname': device,
            'volumes': [
                {'type': 'bind', 'source': paths["ceos_config"], 'target': '/mnt/flash/ceos-config', 'read_only': True},
                {'type': 'bind', 'source': paths["eos_mapping"], 'target': '/mnt/flash/EosIntfMapping.json', 'read_only': True},
                {'type': 'bind', 'source': os.path.abspath('setup_entropy.sh'), 'target': '/mnt/flash/setup_entropy.sh', 'read_only': True},
                {'type': 'bind', 'source': os.path.abspath('enable_entropy.sh'), 'target': '/mnt/flash/enable_entropy.sh', 'read_only': True}
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
            'networks': service_networks
        }

    with open('docker-compose.yml', 'w') as f:
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False)


def main():
    print("ℹ️  Run with `-h` or `--help` for usage instructions.\n")

    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] in ('-h', '--help')):
        print("""
Usage: python3 generate-lab.py [topology_file.yml]

If no topology file is provided, defaults to: topology.yml

This script will:
✅ Detect or create a macvlan management network
✅ Let you select a cEOS image
✅ Auto-assign subnets and generate docker-compose.yml
✅ Optionally show you the generated docker-compose.yml

After running:
👉 Start your lab with: docker compose up -d
""")
        sys.exit(0)

    topo_file = sys.argv[1] if len(sys.argv) == 2 else "topology.yml"

    if not os.path.isfile(topo_file):
        print(f"Error: File '{topo_file}' does not exist.")
        sys.exit(1)

    with open(topo_file) as f:
        topo = yaml.safe_load(f)

    base_subnet = ipaddress.ip_network(topo.get('subnet_pool', str(DEFAULT_SUBNET_POOL)))
    connections = topo.get('connections', [])

    created_mgmt_net = None

    try:
        mgmt_net, created_by_us = ensure_or_select_mgmt_network(topo_file)
        if created_by_us:
            created_mgmt_net = mgmt_net

        existing_docker_subnets = get_existing_docker_subnets()
        devices = {}
        used_subnets = set()
        links = []

        for link in connections:
            subnet = next_subnet(used_subnets, existing_docker_subnets, base_subnet)
            links.append({
                'device1': link['device1'],
                'intf1': link['intf1'],
                'device2': link['device2'],
                'intf2': link['intf2'],
                'subnet': subnet
            })
            for device, intf in [(link['device1'], link['intf1']), (link['device2'], link['intf2'])]:
                devices.setdefault(device, set()).add(intf)

        ceos_image = select_ceos_image()
        volume_paths = generate_device_files(devices, connections)
        generate_compose(devices, links, mgmt_net, volume_paths, ceos_image)

        print("\n✅ Subnets assigned to links:")
        for link in links:
            print(f"  {link['net_name']}: {link['device1']} ({link['intf1']}) <--> {link['device2']} ({link['intf2']}) => {link['subnet']}")

        print("\n✅ docker-compose.yml file has been generated successfully. 🎉")
        print("👉 You can now run the following command to create your lab:\n")
        print("   docker compose up -d\n")

        view_choice = input("👀 Would you like to view the content of docker-compose.yml now? [y/N]: ").strip().lower()
        if view_choice == 'y':
            print("\n📄 Contents of docker-compose.yml:\n")
            with open("docker-compose.yml") as f:
                print(f.read())

    except KeyboardInterrupt:
        print("\n⛔ Script interrupted by user.")
        if created_mgmt_net:
            print(f"🧹 Cleaning up created management network: {created_mgmt_net}")
            subprocess.run(["docker", "network", "rm", created_mgmt_net])
        else:
            print("🚫 Existing management network was not removed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
