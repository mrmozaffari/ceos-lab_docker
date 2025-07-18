#!/usr/bin/env python3

import subprocess
import yaml
import os


def list_existing_macvlan_networks():
    """
    List existing macvlan networks with their name, parent interface, and mode (private/public).
    """
    output = subprocess.check_output(
        ['docker', 'network', 'ls', '--filter', 'driver=macvlan', '--format', '{{.Name}}']
    ).decode().splitlines()

    networks = []
    for name in output:
        inspect = yaml.safe_load(subprocess.check_output(['docker', 'network', 'inspect', name]).decode())[0]
        parent = inspect.get('Options', {}).get('parent', 'unknown')
        mode = inspect.get('Options', {}).get('macvlan_mode', 'bridge')  # default is public
        if mode == 'private':
            mode_str = 'private'
        else:
            mode_str = 'public'
        networks.append((name, parent, mode_str))
    return networks


def list_physical_interfaces():
    """
    List physical NICs.
    """
    return [iface for iface in os.listdir('/sys/class/net') if os.path.exists(f'/sys/class/net/{iface}/device')]


def create_macvlan_network(dry_run=False):
    """
    Create a new macvlan network. User can select private or public.
    """
    name = 'a-135'
    subnet = '192.168.150.0/24'
    gateway = '192.168.150.1'
    parent = list_physical_interfaces()[0]

    print("\n⚙️  Creating a new macvlan network:")
    print(f"   Name: {name}")
    print(f"   Subnet: {subnet}")
    print(f"   Gateway: {gateway}")
    print(f"   Parent interface: {parent}")
    mode = input("👉 Choose mode [private/public] (default: public): ").strip().lower()
    if mode not in ('private', 'public'):
        mode = 'public'

    if dry_run:
        print(f"📝 Dry-run: would create macvlan network '{name}' on '{parent}' with {subnet}, gateway {gateway}, mode {mode}")
        return name, mode, True

    args = [
        "docker", "network", "create", "-d", "macvlan",
        "--subnet", subnet, "--gateway", gateway,
        "-o", f"parent={parent}",
        "-o", f"macvlan_mode={mode}",
        name
    ]

    subprocess.run(args, check=True)

    print(f"✅ Created macvlan network '{name}' on '{parent}' in mode '{mode}'")
    return name, mode, True


def ensure_or_select_mgmt_network(topo_file, auto=False, dry_run=False):
    """
    Either select an existing macvlan network or create a new one.
    Warn user if public mode and allow them to retry.
    """
    while True:
        existing = list_existing_macvlan_networks()
        if existing:
            if dry_run:
                print("📝 Dry-run: would detect existing macvlan networks:")
                for name, iface, mode in existing:
                    print(f"   - {name} → {iface} [mode: {mode}]")
                mgmt_net = existing[0][0]
                created = False
                if existing[0][2] != 'private':
                    print(f"⚠️ In public mode (bridge), LLDP frames can reach your mgmt network!")
                return mgmt_net, created

            elif auto:
                mgmt_net, _, mode = existing[0]
                created = False
                if mode != 'private':
                    print(f"⚠️ In public mode (bridge), LLDP frames can reach your mgmt network!")
                return mgmt_net, created

            else:
                print("\n📋 Existing macvlan networks:")
                for idx, (name, iface, mode) in enumerate(existing, 1):
                    print(f"  {idx}. {name} → {iface} [mode: {mode}]")
                choice = input("👉 Choose one or [C]reate new: ").strip().lower()
                if choice == 'c':
                    mgmt_net, mode, created = create_macvlan_network(dry_run)
                else:
                    mgmt_net, _, mode = existing[int(choice)-1]
                    created = False

        else:
            if dry_run:
                print("📝 Dry-run: would create new macvlan network.")
                mgmt_net = 'a-135'
                created = True
                print(f"⚠️ In public mode (bridge), LLDP frames can reach your mgmt network!")
                return mgmt_net, created
            else:
                mgmt_net, mode, created = create_macvlan_network(dry_run)

        # If public mode, confirm with the user
        if mode != 'private':
            print(f"⚠️ WARNING: You chose a macvlan in public (bridge) mode. LLDP and broadcast frames may reach your management network.")
            confirm = input("❓ Do you want to continue anyway? [y/N]: ").strip().lower()
            if confirm != 'y':
                print("🔁 Okay, please choose again.")
                continue  # re-loop

        break  # happy path

    if dry_run:
        print(f"📝 Dry-run: would update topology.yml with management_network: {mgmt_net}")
        return mgmt_net, created

    # Write back to topology
    with open(topo_file) as f:
        topo = yaml.safe_load(f)
    if topo.get('management_network') != mgmt_net:
        topo['management_network'] = mgmt_net
        with open(topo_file, 'w') as f:
            yaml.dump(topo, f, sort_keys=False)

    return mgmt_net, created


if __name__ == "__main__":
    # simple test
    topo = 'topology.yml'
    net, created = ensure_or_select_mgmt_network(topo, auto=False, dry_run=False)
    print(f"✅ Selected management network: {net}")
