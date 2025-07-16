import subprocess
import yaml
import os


def list_existing_macvlan_networks():
    """
    Returns a list of tuples: [(name, parent_iface), ...]
    """
    output = subprocess.check_output(
        ['docker', 'network', 'ls', '--filter', 'driver=macvlan', '--format', '{{.Name}}']
    ).decode()

    names = output.strip().splitlines()
    networks = []
    for name in names:
        inspect = subprocess.check_output(['docker', 'network', 'inspect', name]).decode()
        details = yaml.safe_load(inspect)[0]
        parent = details.get('Options', {}).get('parent', 'unknown')
        networks.append((name, parent))
    return networks


def list_physical_interfaces():
    """
    Lists only physical host interfaces (has /sys/class/net/<iface>/device).
    """
    physical = []
    for iface in os.listdir('/sys/class/net'):
        if os.path.exists(f'/sys/class/net/{iface}/device'):
            physical.append(iface)
    return physical


def create_macvlan_network():
    """
    Prompts user to create a new macvlan network.
    Returns (network_name, parent_iface)
    """
    default_name = 'a-135'
    default_subnet = '192.168.150.0/24'
    default_gateway = '192.168.150.1'

    name = input(f"📋 Enter name for the new macvlan network (default: {default_name}): ").strip() or default_name
    subnet = input(f"📋 Enter subnet (default: {default_subnet}): ").strip() or default_subnet
    gateway = input(f"📋 Enter gateway (default: {default_gateway}): ").strip() or default_gateway

    # List physical interfaces
    interfaces = list_physical_interfaces()
    if not interfaces:
        print("❌ No physical interfaces found on host. Cannot create macvlan network.")
        exit(1)

    print("\n📋 Available host interfaces:")
    for idx, iface in enumerate(interfaces, 1):
        print(f"  {idx}. {iface}")

    while True:
        choice = input("👉 Enter the number of the interface to use: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(interfaces):
            parent = interfaces[int(choice) - 1]
            break
        else:
            print("⚠️ Invalid choice. Try again.")

    print(f"🛠️ Running: docker network create -d macvlan "
          f"--subnet {subnet} --gateway {gateway} -o parent={parent} {name}")
    subprocess.run([
        "docker", "network", "create", "-d", "macvlan",
        "--subnet", subnet,
        "--gateway", gateway,
        "-o", f"parent={parent}",
        name
    ], check=True)

    print(f"✅ Management network '{name}' created and bound to '{parent}'.")
    return name, parent


def ensure_or_select_mgmt_network(topo_file):
    """
    Ensures a macvlan network exists, lets the user select or create one,
    updates topology.yml if needed.
    Returns (mgmt_net, created) — name of mgmt network and whether we created it.
    """
    existing = list_existing_macvlan_networks()
    if existing:
        print("\n📋 Existing macvlan networks:")
        for idx, (name, iface) in enumerate(existing, 1):
            print(f"  {idx}. {name} → {iface}")
        choice = input("👉 Enter the number of the network to use, or [C]reate a new one: ").strip().lower()
        if choice == 'c':
            mgmt_net, _ = create_macvlan_network()
            created = True
        else:
            idx = int(choice) - 1
            mgmt_net, _ = existing[idx]
            created = False
    else:
        print("⚠️ No macvlan networks found. Creating one.")
        mgmt_net, _ = create_macvlan_network()
        created = True

    # Update topology.yml if needed
    with open(topo_file) as f:
        topo = yaml.safe_load(f)

    if topo.get('management_network') != mgmt_net:
        print(f"\n⚠️ Detected mismatch:")
        print(f"   topology.yml → management_network: {topo.get('management_network')}")
        print(f"   selected      → {mgmt_net}")
        print(f"✍️  Updating topology.yml with management_network: {mgmt_net}")
        topo['management_network'] = mgmt_net
        with open(topo_file, 'w') as f:
            yaml.dump(topo, f, default_flow_style=False, sort_keys=False)
        print(f"✅ topology.yml updated successfully.")

    return mgmt_net, created
