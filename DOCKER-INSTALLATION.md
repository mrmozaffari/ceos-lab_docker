# 🐳 Downgrade Docker to 24.0.6 on Ubuntu

The lab can misbehave with later versions of Docker and Docker Compose.

Newer releases (for example Docker Engine 28.x with Compose 2.35.x) attach a container's networks in a different order. When that happens, `eth0` (Management1) lands on the wrong network, every data-plane port shifts by one, and the management interface cannot reach the outside. The versions below are the ones the lab is known to work with.

| Component | Version |
|---|---|
| Docker Engine | 24.0.6 |
| containerd.io | 1.6.24-1 |
| Docker Compose | 2.22.0 (standalone `docker-compose` command) |

Tested on Ubuntu 20.04 (focal) with kernel 5.4.164. Install the kernel first (see `KERNEL_INSTALLATION.md`).

---

## 💾 Step 0: Stop the Lab and Back Up the Images

Skip this step on a fresh machine.

```bash
cd <your lab folder>
docker compose down        # or: docker-compose down

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
sudo systemctl stop docker docker.socket
sudo apt-mark unhold docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

---

## 📦 Step 2: Set Up the Docker APT Repository (If Not Already Done)

```bash
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker's repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
```

---

## 🔍 Step 3: Find the Available Versions

The version strings depend on your Ubuntu release (`focal` = 20.04, `jammy` = 22.04). Set them once and reuse them in the next step:

```bash
CODENAME=$(lsb_release -cs)
REL=$(lsb_release -rs)
SUFFIX="~ubuntu.${REL}~${CODENAME}"

apt-cache madison docker-ce | grep 24.0.6
apt-cache madison containerd.io | grep 1.6.2
```

You should see a line similar to this (on Ubuntu 20.04):

```
 docker-ce | 5:24.0.6-1~ubuntu.20.04~focal | https://download.docker.com/linux/ubuntu focal/stable amd64 Packages
```

If `24.0.6` does not appear, the repository from Step 2 is missing or does not match your Ubuntu release.

---

## ⬇️ Step 4: Install Docker 24.0.6

This downgrades in place and keeps your existing images. `--allow-downgrades` is required when a newer version is installed.

```bash
sudo apt-get install -y --allow-downgrades \
  docker-ce=5:24.0.6-1${SUFFIX} \
  docker-ce-cli=5:24.0.6-1${SUFFIX} \
  containerd.io=1.6.24-1 \
  docker-buildx-plugin=0.11.2-1${SUFFIX} \
  docker-compose-plugin=2.21.0-1${SUFFIX}

sudo systemctl start docker
```

> If `containerd.io=1.6.24-1` is not offered for your release, pick the closest 1.6.x version from the `apt-cache madison containerd.io` output.

---

## 🔒 Step 5: Prevent Future Upgrades

Without this, a routine `apt upgrade` can move Docker back to a version that breaks the lab.

```bash
sudo apt-mark hold docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

---

## 🧩 Step 6: Install Docker Compose 2.22.0

The lab host that is known to work uses the standalone Compose v2.22.0 binary, run as `docker-compose` (with the hyphen). Install the same one:

```bash
sudo curl -L https://github.com/docker/compose/releases/download/v2.22.0/docker-compose-linux-x86_64 \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
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

docker image ls
```

If your images are missing, restore the backup from Step 0:

```bash
docker load -i ~/ceos64-backup.tar.gz
```

---

## 🌐 Step 8: Management Network and Interface Order Check

Each cEOS node needs its management interface (`eth0`, Management1) on the network that reaches your LAN. In this lab that is a macvlan network on the host's physical NIC. Create it **before** starting the lab. Replace the values with your own LAN details:

```bash
docker network create -d macvlan \
  --subnet 10.240.136.0/25 \
  --gateway 10.240.136.1 \
  --ip-range 10.240.136.96/27 \
  -o parent=ens3 \
  a-135
```

- `parent` is the host NIC that is connected to the LAN (check with `ip -br addr`).
- `--ip-range` limits the placeholder addresses Docker hands out, so they never collide with real hosts. It needs at least as many addresses as you have nodes (a /27 holds 30). Keep the management IPs you configure inside EOS outside this block.
- With a macvlan network, the Docker host itself cannot reach the containers' management addresses. Other machines on the LAN can.

Start the lab and check that every node has the management network as `eth0`:

```bash
docker-compose up -d

for c in $(docker ps --format '{{.Names}}'); do
  printf '%s  ' "$c"; docker exec "$c" ip -br link show eth0 | awk '{print $1}'
done
```

Every line must end in `eth0@if<N>`, where N is the index of the parent NIC (for example `eth0@if2` when the parent is `ens3`, which you can see with `ip -o link`). A large number means `eth0` is on a bridge link network instead, and the interface order is wrong.

To compare the order for one node:

```bash
C=<container name>
docker exec $C ip -br link | grep -E '^eth'
docker inspect $C --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{$v.MacAddress}}{{"\n"}}{{end}}'
```

`eth0` must carry the MAC of the management network, and `eth1`, `eth2`, ... must follow the order of the links in `docker-compose.yml`. This is what `EosIntfMapping.json` expects (`eth0` is Management1, `eth1` is the first Ethernet port, and so on).

---

## 🛠️ Troubleshooting

**`E: Held packages were changed and -y was used without --allow-change-held-packages`**
The packages are on hold. Run the `apt-mark unhold` command from Step 1, install, then hold them again (Step 5).

**`Version '5:24.0.6-...' was not found`**
The repository is missing, or the version string does not match your Ubuntu release. Re-run Step 2 and check Step 3.

**Docker does not start after the downgrade**
Run `sudo journalctl -u docker -n 50 --no-pager` and read the last error. A leftover `/etc/docker/daemon.json` from a newer setup is a common cause.

**A container stays in `Created` and `docker start` says `no available IPv4 addresses on this network's address pools`**
The management network ran out of addresses. A small subnet or a narrow `--ip-range` cannot hold all the nodes. Take the lab down (`docker-compose down`), remove the network (`docker network rm a-135`), and recreate it with a larger range as in Step 8.

**Management1 cannot reach the gateway (ARP stays incomplete)**
First check the interface order from Step 8. If `eth0` is correct, the hypervisor may be dropping frames from the containers' extra MAC addresses. On VMware, enable promiscuous mode and forged transmits for the VM's port group. On other platforms, disable port security or MAC filtering for that vNIC. As a fallback, create the network with `-d ipvlan -o ipvlan_mode=l2` instead of macvlan, which reuses the host's MAC.

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

---

## 🧹 Optional: Clean Reinstall

If the in-place downgrade fails and you do not need the existing containers or images (you can restore images from the Step 0 backup), remove Docker completely and start over from Step 2:

```bash
sudo apt-mark unhold docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo apt remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo apt purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo rm -rf /var/lib/docker
```

> ⚠️ This deletes every image, container, network and volume on the host.
