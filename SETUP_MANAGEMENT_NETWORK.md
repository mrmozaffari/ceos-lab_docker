# 🐳 Configuring a Macvlan Management Network for cEOS Lab

This guide explains how to create a **macvlan** Docker network (e.g., `a-150`) tied to a specific host interface and use it as the management network in your cEOS lab.

---

## 📋 Why?

The cEOS lab script assumes an existing external management network (default: `a-135`).  
If you want to use a **macvlan** network instead — for example to put containers directly on your physical LAN — you need to create it first.

---

## Check if you currently have any macvlan docker network and if the network currently associated with an interface

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

As you can see there is a network name with macvlan called a-135, if you don't see proceed to [Step-by-Step](#step-by-step)

---

## 🔷 Step-by-Step

### 1️⃣ Create a macvlan network

Run this command on the Docker host:

```bash
docker network create -d macvlan \
  --subnet=192.168.150.0/24 \
  --gateway=192.168.150.1 \
  -o parent=ens192 \
  a-150
```