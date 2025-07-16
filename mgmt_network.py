import subprocess
import yaml
import os


def list_existing_macvlan_networks():
    output = subprocess.check_output(
        ['docker', 'network', 'ls', '--filter', 'driver=macvlan', '--format', '{{.Name}}']
    ).decode().splitlines()

    networks = []
    for name in output:
        inspect = yaml.safe_load(subprocess.check_output(['docker', 'network', 'inspect', name]).decode())[0]
        parent = inspect.get('Options', {}).get('parent', 'unknown')
        networks.append((name, parent))
    return networks


def list_physical_interfaces():
    return [iface for iface in os.listdir('/sys/class/net') if os.path.exists(f'/sys/class/net/{iface}/device')]


def ensure_or_select_mgmt_network(topo_file, auto=False, dry_run=False):
    existing = list_existing_macvlan_networks()
    if existing:
        if dry_run:
            print("📝 Dry-run: would detect existing macvlan networks:")
            for name, iface in existing:
                print(f"   - {name} → {iface}")
            mgmt_net = existing[0][0]
            created = False
        elif auto:
            mgmt_net = existing[0][0]
            created = False
        else:
            print("\n📋 Existing macvlan networks:")
            for idx, (name, iface) in enumerate(existing, 1):
                print(f"  {idx}. {name} → {iface}")
            choice = input("👉 Choose one or [C]reate new: ").strip().lower()
            if choice == 'c':
                mgmt_net, created = create_macvlan_network(dry_run)
            else:
                mgmt_net = existing[int(choice)-1][0]
                created = False
    else:
        if dry_run:
            print("📝 Dry-run: would create new macvlan network.")
            mgmt_net = 'a-135'
            created = True
        else:
            mgmt_net, created = create_macvlan_network(dry_run)

    if dry_run:
        print(f"📝 Dry-run: would update topology.yml with management_network: {mgmt_net}")
        return mgmt_net, created

    with open(topo_file) as f:
        topo = yaml.safe_load(f)
    if topo.get('management_network') != mgmt_net:
        topo['management_network'] = mgmt_net
        with open(topo_file, 'w') as f:
            yaml.dump(topo, f, sort_keys=False)

    return mgmt_net, created


def create_macvlan_network(dry_run=False):
    name = 'a-135'
    subnet = '192.168.150.0/24'
    gateway = '192.168.150.1'
    parent = list_physical_interfaces()[0]

    if dry_run:
        print(f"📝 Dry-run: would create macvlan network '{name}' on '{parent}' with {subnet}, gateway {gateway}")
        return name, True

    subprocess.run([
        "docker", "network", "create", "-d", "macvlan",
        "--subnet", subnet, "--gateway", gateway, "-o", f"parent={parent}", name
    ], check=True)

    print(f"✅ Created macvlan network '{name}' on '{parent}'")
    return name, True
