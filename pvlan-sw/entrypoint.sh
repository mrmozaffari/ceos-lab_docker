#!/bin/sh
# Boots a blank VLAN-aware bridge: every data port is attached but carries NO VLAN yet.
# Create VLANs afterwards from inside the container with the "pvlan" command.
#
# Optional env (from the topology file):
#   PORT_MAP        "Ethernet1=eth1 Ethernet2=eth2 ..." so pvlan accepts topology labels
#   ISOLATED_PORTS  ports to start in isolated mode (can be changed later with pvlan)
#   VLAN            optional: pre-create this VLAN (untagged) on all ports at boot
PORTS=$(for kv in $PORT_MAP; do echo "${kv#*=}"; done)

for p in $PORTS; do
  n=0
  until ip link show "$p" >/dev/null 2>&1; do
    n=$((n+1)); [ "$n" -gt 60 ] && { echo "port $p never appeared"; break; }
    sleep 1
  done
done

ip link add br0 type bridge vlan_filtering 1 vlan_default_pvid 0
for p in $PORTS; do   # give br0 a real MAC, VLAN interfaces on it cannot come up with an all-zero one
  mac=$(cat "/sys/class/net/$p/address" 2>/dev/null); [ -n "$mac" ] && { ip link set br0 address "$mac"; break; }
done
ip link set br0 up

for p in $PORTS; do
  ip addr flush dev "$p"     # docker gave the port an IP, a bridge port must not have one
  ip link set "$p" master br0
  ip link set "$p" up
done
for p in $ISOLATED_PORTS; do
  bridge link set dev "$p" isolated on
done
[ -n "$VLAN" ] && pvlan vlan add "$VLAN" $PORTS

echo "pvlan-sw ready. Run: docker exec -it <name> sh, then: pvlan help"
exec sleep infinity
