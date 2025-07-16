import subprocess
import sys
import re
import yaml
import os

def list_existing_macvlan_networks():
    """Returns a list of (name, parent) for existing macvlan networks."""
    result = []
    try:
        output = subprocess.check_output(['docker', 'network', 'ls', '--filter', 'driver=macvlan', '--format', '{{.Name}}']).decode()
        names = [line.strip() for line in output.splitlines() if line.strip()]
        for name in names:
            inspect = subprocess.check_output(['docker', 'network', 'inspect', name]).decode()
            match = re.search(r'"parent":\s*"([^"]+)"', inspect)
            parent = match.group(1) if match else "unknown"
            result.append((name, parent))
    except subprocess.CalledProcessError as e:
        print(f"❌ Error listing macvlan networks: {e}")
        sys.exit(1)
    return result

def pick_host_interface():
    output = subprocess.check_output(['ip', '-o', 'link', 'show']).decode()
    interfaces = []
    for line in output.strip().splitlines():
        match = re.match(r'\d+: ([^:]+):', line)
        if match:
            name = match.group(1)
            if name.startswith('lo') or name.startswith('docker') or name.startswith('br-') or name.startswith('veth'):
                continue
            interfaces.append(name)

    if not interfaces:
        print("❌ No suitable network interfaces found.")
        sys.exit(1)

    print("\n📋 Available host interfaces:")
    for idx, iface in enumerate(interfaces, 1):
        print(f"  {idx}. {iface}")

    while True:
        choice = input("👉 Enter the number of the interface to use: ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(interfaces)):
            print("⚠️ Invalid choice. Please enter a valid number.")
            continue
        return interfaces[int(choice)-1]

def create_macvlan_network():
    name = input("📋 Enter name for the new macvlan network (default: a-135): ").strip() or "a-135"
    subnet = input("📋 Enter subnet (default: 192.168.150.0/24): ").strip() or "192.168.150.0/24"
    gateway = input("📋 Enter gateway (default: 192.168.150.1): ").strip() or "192.168.150.1"
    parent = pick_host_interface()

    cmd = [
        'docker', 'network', 'create', '-d', 'macvlan',
        '--subnet', subnet,
        '--gateway', gateway,
        '-o', f'parent={parent}',
        name
    ]
    print(f"🛠️ Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    print(f"✅ Management network '{name}' created and bound to '{parent}'.")
    return name

def ensure_or_select_mgmt_network(topo_file):
    """Detect or create management macvlan network & auto-update topology.yml if needed."""
    existing = list_existing_macvlan_networks()

    if existing:
        print("\n📋 Existing macvlan networks:")
        for idx, (name, parent) in enumerate(existing, 1):
            print(f"  {idx}. {name} → {parent}")
        while True:
            choice = input("👉 Enter the number of the network to use, or [C]reate a new one: ").strip().lower()
            if choice == 'c':
                mgmt_net = create_macvlan_network()
                break
            elif choice.isdigit() and (1 <= int(choice) <= len(existing)):
                mgmt_net = existing[int(choice)-1][0]
                break
            else:
                print("⚠️ Invalid choice. Please enter a valid number or 'C'.")
    else:
        print("⚠️ No macvlan management networks exist. You need to create one.")
        mgmt_net = create_macvlan_network()

    # Load topology.yml
    with open(topo_file) as f:
        topo = yaml.safe_load(f)

    current = topo.get('management_network', 'a-135')

    if mgmt_net != current:
        print(f"\n⚠️ Detected mismatch:")
        print(f"   topology.yml → management_network: {current}")
        print(f"   selected      → {mgmt_net}")
        print(f"✍️  Updating topology.yml with management_network: {mgmt_net}")
        topo['management_network'] = mgmt_net
        with open(topo_file, 'w') as f:
            yaml.dump(topo, f, default_flow_style=False, sort_keys=False)
        print(f"✅ topology.yml updated successfully.")

    return mgmt_net