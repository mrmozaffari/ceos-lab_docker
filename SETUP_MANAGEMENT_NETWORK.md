# 🐳 Configuring a Macvlan Management Network for cEOS Lab

This guide explains how to create a **macvlan** Docker network (e.g., `a-135`) tied to a specific host interface and use it as the management network in your cEOS lab.

---

## 📋 Why?

The cEOS lab script assumes an existing external management network (default: `a-135`).  
If you want to use a **macvlan** network instead — for example to put containers directly on your physical LAN — you need to create it first.

---

## MacVlan creation using script

### 📝 Workflow

1️⃣ During execution of `python3 generate-lab.py topology.yml`, the script checks for any existing macvlan Docker network.  
2️⃣ If none are found, it will prompt you and walk you through creating one.  
3️⃣ If macvlan networks are found, it will list them and let you pick one.  
4️⃣ If you select or create a network **other than `a-135`**, the script automatically updates your `topology.yml` with the chosen network name and informs you.  
5️⃣ The script then proceeds to generate the final `docker-compose.yml` file.

---

## 🟦 🐳 Optional: Manual MacVlan Network Creation

### Check if you currently have any macvlan docker network and if the network currently associated with an interface

From the bash of the host run following commands:

```bash
docker network ls
```

Your output might be different, here is an example:
```
NETWORK ID     NAME        DRIVER    SCOPE
3e5cf2...      bridge      bridge    local
b7e34a...      host        host      local
e4b5e7...      none        null      local
1d4e5b...      a-135       macvlan   local
9c6f1a...      a-150       bridge    local
```

👉 If you don’t see any macvlan network listed, proceed to the 🔷 [Step-by-Step](#step-by-step) section below to create one.


### Check macvlan network association with host interface

Run this command to inspect the network:


```bash
docker network inspect a-135
```

You should see an output like this:

```
[
    {
        "Name": "a-135",
        "Id": "1d4e5b...",
        "Driver": "macvlan",
        "Scope": "local",
        "IPAM": {
            "Config": [
                {
                    "Subnet": "10.240.135.0/24",
                    "Gateway": "10.240.135.1"
                }
            ]
        },
        "Options": {
            "parent": "ens192" // 👈 host interface used
        }
    }
]

```

Here, "parent": "ens192" shows which host interface the macvlan is bound to.



---

## 🔷 Step-by-Step

### 1️⃣ Create a macvlan network
If you prefer to create a macvlan network manually (instead of letting the script handle it), run this command:

```bash
docker network create -d macvlan \
  --subnet=10.240.135.0/24 \
  --gateway=10.240.135.1 \
  -o parent=ens192 \
  a-135
```

Replace:

- 10.240.135.0/24 → with your desired subnet
- 10.240.135.1 → with your desired gateway
- ens192 → with your host interface
- a-135 → with your desired network name