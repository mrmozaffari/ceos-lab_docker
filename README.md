
# 🚀 Docker Topology Generator for cEOS

This Python script generates a `docker-compose.yml` and per-device configuration files for a cEOS lab topology based on an input YAML topology file.  
It also detects existing `ceos` Docker images and allows the user to pick one interactively.

---

## 📑 Table of Contents

- [🚀 Docker Topology Generator for cEOS](#-docker-topology-generator-for-ceos)
  - [📑 Table of Contents](#-table-of-contents)
  - [🛑 Before you Begin](#-before-you-begin)
    - [📝 Available Options](#-available-options)
  - [📋 Features](#-features)
  - [📂 Directory Structure](#-directory-structure)
  - [🔧 Requirements](#-requirements)
    - [📡 Management Network](#-management-network)
  - [📝 Usage](#-usage)
    - [Input Topology File](#input-topology-file)
    - [Command Line Options](#command-line-options)
    - [Example Commands](#example-commands)
    - [Run the Script](#run-the-script)
  - [👨‍💻 Workflow](#-workflow)
  - [📦 Example Output](#-example-output)
  - [📄 Key Files Generated](#-key-files-generated)
    - [🔷  What is `TFA_VERSION=2`?](#--what-is-tfa_version2)
  - [🐳 Run the lab with Docker](#-run-the-lab-with-docker)
    - [🔬🧪 Name of the Lab (Important)](#-name-of-the-lab-important)
  - [🛑 Tear Down the Lab](#-tear-down-the-lab)
  - [🔄 Entropy and cEOS](#-entropy-and-ceos)
    - [Why does entropy matter?](#why-does-entropy-matter)
  - [🧰 Enabling Haveged in cEOS](#-enabling-haveged-in-ceos)
  - [🛑 Notes](#-notes)
  - [Change the MTU and Allow LLDP (lab-helper.py)](#change-the-mtu-and-allow-lldp-lab-helperpy)
    - [Change the MTU](#change-the-mtu)
    - [Allow LLDP](#allow-lldp)
  - [📚 Extending](#-extending)

---

## 🛑 Before you Begin

It’s important to run this lab on a host that already supports LLDP and LACP. You might be able to enable LLDP (using lab-helper.py), which can also adjust the MTU on bridge interfaces. However, on most Linux machines, LACP cannot be enabled simply by changing the group_fwd_mask.  

### 📝 Available Options

- Use a Linux with custom kernel to allow LLDP, LACP (Advance)
- Use available Linux version used for iOU, EVE-NG, Containcer-Lab

---

## 📋 Features

- Parses a YAML topology file describing devices and connections.
- Validates topology file structure & contents.
- Detects existing macvlan networks and lets you pick one.
- Or guides you through creating a new macvlan tied to a physical host interface.
- Automatically updates `topology.yml` with the chosen management network.
- Detects existing Docker networks (subnets) to avoid conflicts.
- Automatically assigns non-overlapping subnets to each link.
- Lists available `ceos` / `ceos64` Docker images and lets you choose.
- Generates:
  - `docker-compose.yml` to deploy the topology.
  - `devices/<device>/ceos-config` and `EosIntfMapping.json` for each device.
- Supports:
  - 📝 Dry-run mode (`--dry-run`)
  - 🤖 Automation-friendly mode (`--auto`)
  - 🪵 Verbose logging (`--verbose`)

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
- At least one cEOS Docker image (`ceos` or `ceos64`) imported

If you don’t already have a cEOS image, you can download it from the [Arista support portal](https://www.arista.com/en/support/software-download).  
Once downloaded (typically as a `.tar.xz` file), import it into Docker using:

```bash
docker import cEOS64-lab-4.34.1F.tar.xz ceos64:4.34.1F
```

Replace the filename and tag with the version you downloaded.

---

### 📡 Management Network

⚠️ **Important:**

The script now fully manages the Docker macvlan network used for management.
If no macvlan network exists, or if you want to use a different one, the script will:

- Detect all existing macvlan networks and let you pick one.
- Or guide you through creating a new macvlan tied to a physical host interface.
- Automatically update `topology.yml` with the chosen network name.
  
You no longer need to manually create or configure the management network beforehand — the script handles it for you interactively or in `--auto` mode.  

If you still prefer to create a macvlan network manually or want to learn more, see:

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

---

### Command Line Options

| Option          | Short         | Default        | Description                                                        |
|-----------------|---------------|----------------|--------------------------------------------------------------------|
| `filename.yml`  | *positional*  | `topology.yml` | The topology YAML file to use as input                            |
| `--auto`        |               | `False`        | Run in **non-interactive mode**, automatically selecting defaults |
| `--dry-run`     |               | `False`        | Simulate the run: validate & show actions, but make **no changes**|
| `--verbose`     |               | `False`        | Enable detailed logging to `generate-lab.log`                     |
| `-h`, `--help`  |               |                | Show usage instructions and exit                                  |

### Example Commands

| Command                                    | What it does                                        |
|-------------------------------------------|-----------------------------------------------------|
| `python3 generate-lab.py`                | Run interactively with prompts                     |
| `python3 generate-lab.py --auto`        | Run without prompts, pick defaults                 |
| `python3 generate-lab.py --dry-run`     | Simulate interactive run, don’t change anything    |
| `python3 generate-lab.py --auto --dry-run` | Simulate fully-automatic run, don’t change anything |
| `python3 generate-lab.py mytopo.yml`    | Run on a specific topology file interactively      |
| `python3 generate-lab.py -h`            | Show help & exit                                   |

---

### Run the Script

```bash
python3 generate-lab.py topology.yml
```

---

## 👨‍💻 Workflow

1️⃣ Reads the topology file and parses devices & connections.  
2️⃣ Lists all local Docker networks and reserves available `/24` subnets for each link. Detects or creates macvlan mgmt network.  
3️⃣ Lists all local Docker images whose repository starts with `ceos` or `ceos64`.  
4️⃣ Prompts the user to pick one of the available images.  
5️⃣ Generates:  

- Per-device directories in `devices/` with:
  
  - `ceos-config`: device serial number, MAC address, and TFA version.
  - `EosIntfMapping.json`: management and ethernet interface mappings.
- A `docker-compose.yml` with all devices, configured volumes, networks, and the chosen Docker image.

## 📦 Example Output

```text

root@docker:/ceos-lab_docker# python3 generate-lab.py

📋 Existing macvlan networks:
  1. a-135 → ens192
👉 Choose one or [C]reate new: 1

📋 Available ceos images:
  1. ceos64:4.34.1F
  2. ceos:4.32.4M
  3. ceos:4.30.3m

👉 Enter the number of the image you want to use: 2

✅ Subnets assigned to links:
  link01: sw1 (eth1) <--> sw2 (eth1) => 172.16.0.0/24
  link02: sw2 (eth2) <--> sw3 (eth1) => 172.16.1.0/24

✅ docker-compose.yml generated successfully. 🎉
👉 To start your lab:
   docker-compose up -d

👉 To tear it down:
   docker-compose down

```

## 📄 Key Files Generated

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Docker Compose file to spin up the lab |
| `devices/<device>/ceos-config` | Per-device config with MAC & serial |
| `devices/<device>/EosIntfMapping.json` | Maps Docker interfaces to EOS interfaces |

---

### 🔷  What is `TFA_VERSION=2`?

Starting with later versions of **cEOS-lab**, the **TFA v2 format** was introduced.  

In **TFA v2**:

- The EOS container image already **includes the required persistent file system inside the image itself**, so you no longer need a separate `ceos-config` tarball to boot.
- This **simplifies deployment**, because you only deal with the container image.

The `TFA_VERSION=2` variable is simply a marker in scripts or configurations that tells the cEOS-lab tooling:

> Use the newer single-file image with integrated persistent filesystem (TFA v2), not the old two-file setup.

---

## 🐳 Run the lab with Docker

From the directory or folder of project where the `docker-compose.yml` file resides run  

```bash
docker-compose up -d

root@docker:/home/ceos/repo/ceos-lab_docker# docker-compose up -d
[+] Building 0.0s (0/0)                                                                              docker:default
[+] Running 4/4
 ✔ Network ceos-lab_docker_link01      Created                                                                 0.3s
 ✔ Network ceos-lab_docker_link02      Created                                                                 0.3s
 ✔ Container ceos-lab_docker-LEAF1A-1  Started                                                                 1.8s
 ✔ Container ceos-lab_docker-SPINE1-1  Started                                                                 1.8s
```

### 🔬🧪 Name of the Lab (Important)

If you use docker-compose the name of the lab will be your last folder you have docker-compose.yml and generated your lab. You will need the lab name to run the **lab-helper.py** to allow LLDP or change the MTU for the links. Click here for [Change the MTU, Allow LLDP](#change-the-mtu-and-allow-lldp-lab-helperpy)

---

## 🛑 Tear Down the Lab

To stop and remove all containers, networks, and volumes created by this stack, from the same directory where the `docker-compose.yml` file resides run:  

```bash
docker-compose down
```

---

## 🔄 Entropy and cEOS

### Why does entropy matter?

Low entropy on Linux systems can cause SSH, key generation, and boot to hang or fail.
To solve it inside cEOS containers:  

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

- The script detects or creates the management network interactively as needed.
- Subnet pool defaults to `172.16.0.0/16` if not specified in the topology file.
- If no `ceos`/`ceos64` images are found locally, the script exits with an error.

---

## Change the MTU and Allow LLDP (lab-helper.py)

To fix the lldp and change the MTU for the lab network you can use lab-helper.py, you need to know you lab name 👆
Here the examples:

```bash
root@docker:/home/ceos/repo/ceos-lab_docker# python3 lab-helper.py -h
usage: fix-lab.py [-h] [-f] [-m MTU] lab_name

Manage network settings for a lab

positional arguments:
  lab_name           Name of the lab - Get the lab name from Portainer's Stacks page

optional arguments:
  -h, --help         show this help message and exit
  -f, --fix-lldp     Enable LLDP
  -m MTU, --mtu MTU  Change MTU size (1-65535)
```

### Change the MTU

```bash
root@docker:/home/ceos/repo/ceos-lab_docker# python3 lab-helper.py -m 9000 ceos-lab_docker
docker container: ceos-lab_docker_link01 with bridge_id: br-392c27666e71
docker container: ceos-lab_docker_link02 with bridge_id: br-abf4379ebc48
MTU change to 9000 on veth921a13e
MTU change to 9000 on vethe8ebee6
MTU change to 9000 on veth170b520
MTU change to 9000 on vethcb3b52e
```

### Allow LLDP

```bash
root@docker:/home/ceos/repo/ceos-lab_docker# python3 lab-helper.py -f ceos-lab_docker
docker container: ceos-lab_docker_link01 with bridge_id: br-392c27666e71
docker container: ceos-lab_docker_link02 with bridge_id: br-abf4379ebc48
Enabling LLDP on br-392c27666e71
Enabling LLDP on br-abf4379ebc48
```

---

## 📚 Extending

Ideas to improve:

- Add more validations & tests
- Parallel deployment & scaling

---
