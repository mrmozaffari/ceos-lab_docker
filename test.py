import subprocess
import json

def inspect_docker_network(network_name):
    try:
        output = subprocess.check_output(
            ['docker', 'network', 'inspect', network_name],
            text=True
        )
        data = json.loads(output)[0]
        driver = data.get("Driver", "")
        if driver == "bridge":
            # Bridge networks have a br-xxxx interface matching the network id
            net_id = data.get("Id", "")[:12]
            print(f"🔷 Docker network '{network_name}' uses driver: bridge")
            print(f"➡️  Associated Linux bridge: br-{net_id}")
            print(f"💡 You can check it with: ip link show br-{net_id}")
        elif driver == "macvlan":
            parent = data.get("Options", {}).get("parent", "(unknown)")
            print(f"🔷 Docker network '{network_name}' uses driver: macvlan")
            print(f"➡️  Attached to parent interface: {parent}")
        else:
            print(f"❓ Docker network '{network_name}' uses driver: {driver}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to inspect Docker network: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    net_name = input("👉 Enter Docker network name: ").strip()
    inspect_docker_network(net_name)

