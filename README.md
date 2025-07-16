
# 🚀 Docker Topology Generator for cEOS

This Python script generates a `docker-compose.yml` and per-device configuration files for a cEOS lab topology based on an input YAML topology file.  
It also detects existing `ceos` Docker images and allows the user to pick one interactively.

---

## 📋 Features

- Parses a YAML topology file describing devices and connections.
- Detects the MacVlan networks on docker host
- Interact with user to create docker network (MacVlan)
- Automatically assigns **non-overlapping** subnets to each link.
- Detects existing Docker networks(subnets) to avoid conflicts.
- Lists available `ceos`/`ceos64` Docker images and lets the user choose which one to use.
- Generates:
  - `docker-compose.yml` to deploy the topology.
  - `devices/<device>/ceos-config` and `EosIntfMapping.json` for each device.

---

## 📂 Directory Structure

After running the script:

```text
.
├── docker-compose.yml
├── devices/
│   ├── device1/
│   │   ├── ceos-config
│   │   └── EosIntfMapping.json
│   ├── device2/
│   │   ├── ceos-config
│   │   └── EosIntfMapping.json
│   └── ...
```

---

## 🔧 Requirements

- Python 3
- Docker installed & running
- At least one cEOS Docker image (`ceos` or `ceos64`) pulled

If you don’t already have a cEOS image, you can download it from the [Arista support portal](https://www.arista.com/en/support/software-download).  
Once downloaded (typically as a `.tar.xz` file), import it into Docker using:

```bash
docker import cEOS64-lab-4.34.1F.tar.xz ceos64:4.34.1F
```

Replace the filename and tag with the version you downloaded.

---

### 📡 Management Network

⚠️ **Important:**

By default, the script assumes there is an existing external Docker network called `a-135` for management.  
If you want to create a custom macvlan management network (e.g., `a-150`) tied to a specific host interface, follow the steps in the dedicated guide below:

📄 [Setup Management Network](SETUP_MANAGEMENT_NETWORK.md)


---

## 📝 Usage

### Input Topology File

This is an example of `topology.yml` file. You can create and craft your own topology:

```yaml
management_network: a-135
subnet_pool: 172.16.0.0/16
connections:
  - { device1: SPINE1, intf1: Ethernet1/1,  device2: LEAF1,  intf2: Ethernet1 }
  - { device1: SPINE1, intf1: Ethernet1/2,  device2: LEAF1,  intf2: Ethernet2 }
  - { device1: SPINE1, intf1: Ethernet1/3,  device2: LEAF2,  intf2: Ethernet1 }
  - { device1: SPINE1, intf1: Ethernet1/4,  device2: LEAF2,  intf2: Ethernet2 }
  - { device1: LEAF1,  intf1: Ethernet97/1, device2: LEAF2,  intf2: Ethernet97/1 }
  - { device1: LEAF1,  intf1: Ethernet98/1, device2: LEAF2,  intf2: Ethernet98/1 }
```

### Run the Script

```bash
python3 generate-lab.py topology.yml
```

---

## 👨‍💻 Workflow

1️⃣ Reads the topology file and parses devices & connections.  
2️⃣ Lists all local Docker networks and reserves available `/24` subnets for each link.  
3️⃣ Lists all local Docker images whose repository starts with `ceos` or `ceos64`.  
4️⃣ Prompts the user to pick one of the available images.  
5️⃣ Generates:

- Per-device directories in `devices/` with:
  
  - `ceos-config`: device serial number, MAC address, and TFA version.
  
  - `EosIntfMapping.json`: management and ethernet interface mappings.
  
- A `docker-compose.yml` with all devices, configured volumes, networks, and the chosen Docker image.


### 🔷  What is `TFA_VERSION=2`?

Starting with later versions of **cEOS-lab**, the **TFA v2 format** was introduced.  

In **TFA v2**:
- The EOS container image already **includes the required persistent file system inside the image itself**, so you no longer need a separate `ceos-config` tarball to boot.
- This **simplifies deployment**, because you only deal with the container image.

The `TFA_VERSION=2` variable is simply a marker in scripts or configurations that tells the cEOS-lab tooling:

> Use the newer single-file image with integrated persistent filesystem (TFA v2), not the old two-file setup.

---

## 📦 Example Output

When run, the script will print something like:

```
📋 Available ceos images:
  1. ceos64:4.34.1F
  2. ceos:4.32.4M
  3. ceos:4.30.3m

👉 Enter the number of the image you want to use: 2

✅ Subnets assigned to links:
  link01: sw1 (eth1) <--> sw2 (eth1) => 172.16.0.0/24
  link02: sw2 (eth2) <--> sw3 (eth1) => 172.16.1.0/24
```

---

## 📄 Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Docker Compose file to spin up the lab |
| `devices/<device>/ceos-config` | Per-device config with MAC & serial |
| `devices/<device>/EosIntfMapping.json` | Maps Docker interfaces to EOS interfaces |

---

## 🔄 Entropy and cEOS

### Why does entropy matter?

Entropy in Linux systems is the randomness collected from hardware sources, used to generate secure random numbers (e.g., for SSH keys, TLS sessions).  
When entropy is low, operations that depend on random numbers can block or fail, which may result in:
- Long boot times for cEOS containers.
- Services like SSH hanging on startup.
- Reduced security of cryptographic operations if weak random numbers are used.

### How to solve low entropy?

One solution is to run a userspace entropy daemon such as **haveged** (Haveged) which generates random numbers using CPU jitter and feeds the kernel entropy pool.  
However, haveged is not always enabled in the cEOS image by default.

---

## 🐳 Run with Docker

From the directory or folder of project where the `docker-compose.yml` file resides run  

```bash
docker-compose up -d
```

---

## 🛑 Tear Down the Lab

To stop and remove all containers, networks, and volumes created by this stack, from the same directory where the `docker-compose.yml` file resides run:   

```bash
docker-compose down
```

---

## 🧰 Enabling Haveged in cEOS

This script copies two helper files into `/mnt/flash` of each container:
- `setup_entropy.sh`
- `enable_entropy.sh`

When the container is running, you can attach to it and enable entropy:

```bash
docker exec -it <container-name> bash
cd /mnt/flash
./enable_entropy.sh
```

This starts haveged inside the cEOS container, increasing entropy and avoiding stalls.   
   
Optional: The `setup_entropy.sh` installs the latest Haveged in cEOS, for that you would need to configure mgmt with IP address, default gateway or static route and DNS on your cEOS so it can communicate with Internet.

---

## 🛑 Notes

- The script assumes the management network (`a-135` by default) already exists as an **external Docker network**. 
- Subnet pool defaults to `172.16.0.0/16` if not specified in the topology file.
- If no `ceos`/`ceos64` images are found locally, the script exits with an error.

---

## 📚 Extending

You can enhance this script by:
- Adding validation of the topology file.
- Supporting other image tags or platforms.
- Automatically creating the management network if missing.
- Adding command-line options to skip prompts (for automation).

---
