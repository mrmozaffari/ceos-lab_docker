# 🐳 Docker 24.0.6 for the cEOS Lab on Ubuntu

The lab can misbehave with later versions of Docker and Docker Compose.

Newer releases (for example Docker Engine 28.x with Compose 2.35.x) attach a container's networks in a different order. When that happens, `eth0` (Management1) lands on the wrong network, every data-plane port shifts by one, and the management interface cannot reach the outside. The versions below are the ones the lab is known to work with.

| Component | Version |
|---|---|
| Docker Engine | 24.0.6 |
| containerd.io | 1.6.24-1 |
| Docker Compose | 2.22.0 (standalone `docker-compose` command) |

Verified on Ubuntu 20.04 and Ubuntu 24.04, both with kernel 5.4.164. Install the kernel first (see `KERNEL_INSTALLATION.md`).

Run everything as root (`sudo -i`) and in **one terminal session**, because some steps set variables that later steps use.

---

## 💾 Step 0: Stop the Lab and Back Up the Images

Skip this step on a fresh machine.

```bash
cd <your lab folder>
docker-compose down        # or: docker compose down

# Save the cEOS image so you can restore it if anything goes wrong
docker image ls
docker save ceos64:4.36.3.2m | gzip > ~/ceos64-backup.tar.gz
```

> Replace the image name and tag with the one shown by `docker image ls`.

---

## 🛑 Step 1: Stop Docker and Release Any Package Holds

An earlier setup may have put the Docker packages on hold, which blocks the downgrade
(`E: Held packages were changed and -y was used without --allow-change-held-packages`).

```bash
systemctl stop docker docker.socket
apt-mark unhold docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-buildx-plugin docker-compose-plugin
```

On a fresh machine, `Unit docker.service not loaded` and `Unable to locate package` errors here are harmless.

---

## 📦 Step 2: Set Up the Docker APT Repository

```bash
apt update
apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg

# Add Docker's repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

apt update
```

---

## 🔍 Step 3: Pick the Right 24.0.6 Build

The version strings depend on your Ubuntu release (`focal` = 20.04, `jammy` = 22.04, `noble` = 24.04). Docker publishes 24.0.6 for 20.04 and 22.04, but not for 24.04. On 24.04, use the 22.04 (`jammy`) packages. They install and run correctly there, but this is not an officially supported combination.

This block uses your own release when 24.0.6 exists for it, and falls back to `jammy` otherwise:

```bash
CODENAME=$(lsb_release -cs)
REL=$(lsb_release -rs)

if ! apt-cache madison docker-ce | grep -q "5:24.0.6-1~ubuntu.${REL}~${CODENAME}"; then
  echo "No 24.0.6 build for ${CODENAME}: using the jammy (22.04) packages"
  sed -i "s/${CODENAME}/jammy/" /etc/apt/sources.list.d/docker.list
  apt update
  CODENAME=jammy; REL=22.04
fi

SUFFIX="~ubuntu.${REL}~${CODENAME}"
echo "using: ${SUFFIX}"
apt-cache madison docker-ce | grep 24.0.6
apt-cache madison containerd.io | grep 1.6.24
```

Both `madison` lines must print something. If either is empty, stop here.

---

## ⬇️ Step 4: Install Docker 24.0.6

This downgrades in place and keeps your existing images. `--allow-downgrades` is required when a newer version is installed. Pin **every** package, including `docker-ce-rootless-extras`, which otherwise installs at the newest version.

```bash
apt-get install -y --allow-downgrades \
  docker-ce=5:24.0.6-1${SUFFIX} \
  docker-ce-cli=5:24.0.6-1${SUFFIX} \
  docker-ce-rootless-extras=5:24.0.6-1${SUFFIX} \
  containerd.io=1.6.24-1 \
  docker-buildx-plugin=0.11.2-1${SUFFIX} \
  docker-compose-plugin=2.21.0-1${SUFFIX}

systemctl enable --now docker
```

---

## 🔒 Step 5: Prevent Future Upgrades

Without this, a routine `apt upgrade` can move Docker back to a version that breaks the lab.

```bash
apt-mark hold docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-buildx-plugin docker-compose-plugin
```

---

## 🧩 Step 6: Install Docker Compose 2.22.0

The lab host that is known to work uses the standalone Compose v2.22.0 binary, run as `docker-compose` (with the hyphen). Install the same one:

```bash
curl -L https://github.com/docker/compose/releases/download/v2.22.0/docker-compose-linux-x86_64 \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

> From here on, start and stop the lab with `docker-compose up -d` and `docker-compose down`.
> The `docker compose` plugin (2.21.0) installed in Step 4 is close, but the exact version used on the working host is 2.22.0.

---

## ✅ Step 7: Confirm the Versions

```bash
docker -v
# Docker version 24.0.6, build ...

docker-compose version
# Docker Compose version v2.22.0

dpkg -l | grep -E 'docker|containerd' | awk '{print $2, $3}'
docker run --rm hello-world | head -3
docker image ls
```

If your images are missing, restore the backup from Step 0:

```bash
docker load -i ~/ceos64-backup.tar.gz
```

---

## 🖥️ Step 8: Host Requirements for cEOS

Check these before starting the lab. Each one has caused a cEOS node to boot only halfway.

```bash
# 1. IPv6 must be enabled in the kernel
tr ' ' '\n' < /proc/cmdline | grep -E 'ipv6|cgroup' || echo "no ipv6/cgroup options"
[ -d /proc/sys/net/ipv6 ] && echo "IPv6 enabled" || echo "IPv6 DISABLED (remove ipv6.disable=1, see KERNEL_INSTALLATION.md Step 4)"

# 2. Kernel modules
for m in overlay macvlan br_netfilter veth; do modprobe -n -v $m >/dev/null 2>&1 && echo "$m ok" || echo "$m MISSING"; done

# 3. cgroup version
docker info --format 'cgroup={{.CgroupVersion}}/{{.CgroupDriver}}'
```

- **IPv6** must be on. With `ipv6.disable=1` on the kernel command line, the cEOS nodes start only partly (see Troubleshooting).
- **cgroup.** The working lab hosts (Ubuntu 20.04) use cgroup v1 with the `cgroupfs` driver. Ubuntu 24.04 defaults to cgroup v2. The lab was verified on 24.04 running cgroup v1; cgroup v2 was not tested with cEOS. To match the working hosts on 24.04:

  ```bash
  sed -i 's/^GRUB_CMDLINE_LINUX="/GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=0 /' /etc/default/grub
  update-grub && reboot
  docker info --format '{{.CgroupVersion}}'     # should print 1
  ```

---

## 🌐 Step 9: Management Network and Interface Order Check

Each cEOS node needs its management interface (`eth0`, Management1) on the network that reaches your LAN. In this lab that is a macvlan network on the host's physical NIC, named `a-135`. It must exist **before** the lab starts.

> If your lab folder has `mgmt_network.py` and `SETUP_MANAGEMENT_NETWORK.md`, use that procedure to create the network. The manual commands below are for labs without such a script.

```bash
docker network create -d macvlan \
  --subnet 10.240.136.0/25 \
  --gateway 10.240.136.1 \
  --ip-range 10.240.136.96/27 \
  -o parent=ens3 \
  a-135
```

Replace the values with your own LAN details:

- `parent` is the host NIC that is connected to the LAN (check with `ip -br addr`, for example `ens3` or `enp3s0`).
- `--ip-range` limits the placeholder addresses Docker hands out, so they never collide with real hosts. It needs at least as many addresses as you have nodes (a /27 holds 30). Keep the management IPs you configure inside EOS outside this block.
- With a macvlan network, the Docker host itself cannot reach the containers' management addresses. Other machines on the LAN can.

Start the lab and check that every node has the management network as `eth0`:

```bash
docker-compose up -d

for c in $(docker ps --format '{{.Names}}'); do
  printf '%s  ' "$c"; docker exec "$c" ip -br link show eth0 | awk '{print $1}'
done
```

Every line must end in `eth0@if<N>`, where N is the index of the parent NIC (usually 2, which you can confirm with `ip -o link`). A large number means `eth0` is on a bridge link network instead, and the interface order is wrong.

To compare the order for one node:

```bash
C=<container name>
docker exec $C ip -br link | grep -E '^eth'
docker inspect $C --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{$v.MacAddress}}{{"\n"}}{{end}}'
```

`eth0` must carry the MAC of the management network, and `eth1`, `eth2`, ... must follow the order of the links in `docker-compose.yml`. This is what `EosIntfMapping.json` expects (`eth0` is Management1, `eth1` is the first Ethernet port, and so on).

---

## 🩺 Step 10: Health Check of a Running Node

Give the nodes a minute or two to boot, then check one of them:

```bash
C=<container name>
docker exec $C systemctl --failed
docker exec $C ip -br addr
docker exec $C ip -br link | grep -E 'cpu|fabric|fwd0|mirror'
```

and in the EOS CLI: `show interfaces status`.

A **healthy** node looks like this:

- `systemctl --failed` lists nothing.
- The `eth1` and higher interfaces have **no IP address**. Docker assigns addresses on every network when the container starts, and EOS removes them from the Ethernet ports once it takes them over.
- The extra devices `cpu`, `fabric`, `fabric1` to `fabric3`, `fwd0` and `mirror0` to `mirror3` exist.
- The Ethernet ports show `connected` or `notconnect`, never `unknown`.

---

## 🛠️ Troubleshooting

**`E: Held packages were changed and -y was used without --allow-change-held-packages`**
The packages are on hold. Run the `apt-mark unhold` command from Step 1, install, then hold them again (Step 5).

**`Version '5:24.0.6-...' was not found`**
The repository is missing, or the version string does not match your Ubuntu release. Re-run Steps 2 and 3. On Ubuntu 24.04 the `jammy` fallback in Step 3 is required.

**Docker does not start after the downgrade**
Run `journalctl -u docker -n 50 --no-pager` and read the last error. A leftover `/etc/docker/daemon.json` from a newer setup is a common cause.

**Ethernet ports show `unknown`, and the Docker addresses stay on `eth1` and higher**
The node booted only halfway: EOS never took over the ports. Typical signs inside the container:

- `systemctl --failed` lists `EosPreloadPy.service` (exit status `209/STDOUT`).
- `rsyslog.service` restarts in a loop (`/var/log/messages` is full of it).
- `show processes | include Etba|Sfe` shows no forwarding agent.
- `ifconfig` shows no `cpu`, `fabric` or `fwd0` devices, and `lo` has no `inet6 ::1`.

The cause found in this lab was **IPv6 disabled in the host kernel** (`ipv6.disable=1` on the kernel command line, common on hardened images). Remove it as described in `KERNEL_INSTALLATION.md` Step 4, reboot, and run `docker-compose up -d` again. Other differences worth ruling out, in this order: the cEOS image version compared with the working lab (`docker exec <node> cat /etc/Eos-release`), the cgroup version (Step 8), and available memory.

**A container stays in `Created` and `docker start` says `no available IPv4 addresses on this network's address pools`**
The management network ran out of addresses. A small subnet or a narrow `--ip-range` cannot hold all the nodes. Take the lab down (`docker-compose down`), remove the network (`docker network rm a-135`), and recreate it with a larger range as in Step 9.

**Management1 cannot reach the gateway (ARP stays incomplete)**
First check the interface order from Step 9. If `eth0` is correct, the hypervisor may be dropping frames from the containers' extra MAC addresses. On VMware, enable promiscuous mode and forged transmits for the VM's port group. On other platforms, disable port security or MAC filtering for that vNIC. As a fallback, create the network with `-d ipvlan -o ipvlan_mode=l2` instead of macvlan, which reuses the host's MAC.

**`eth0` is on the wrong network even with these versions**
Pin the order explicitly in `docker-compose.yml` so it no longer depends on the Docker or Compose version. Use the map form for each service's networks, with the management network first and the highest priority:

```yaml
    networks:
      a-135:
        priority: 1000
      link01:
        priority: 999
      link02:
        priority: 998
```

**`docker-ce-rootless-extras` shows a newer version than the other packages**
It was not pinned. Reinstall it with the same suffix as the others (`apt-get install --allow-downgrades docker-ce-rootless-extras=5:24.0.6-1${SUFFIX}`) and hold it (Step 5).

---

## 🧹 Optional: Clean Reinstall

If the in-place downgrade fails and you do not need the existing containers or images (you can restore images from the Step 0 backup), remove Docker completely and start over from Step 2:

```bash
apt-mark unhold docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-buildx-plugin docker-compose-plugin
apt remove -y docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-buildx-plugin docker-compose-plugin
apt purge -y docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-buildx-plugin docker-compose-plugin
rm -rf /var/lib/docker
```

> ⚠️ This deletes every image, container, network and volume on the host.
