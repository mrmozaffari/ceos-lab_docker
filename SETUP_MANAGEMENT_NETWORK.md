# 🐳 Configuring a Macvlan Management Network for cEOS Lab

This guide explains how to create a **macvlan** Docker network (e.g., `a-150`) tied to a specific host interface and use it as the management network in your cEOS lab.

---

## 📋 Why?

The cEOS lab script assumes an existing external management network (default: `a-135`).  
If you want to use a **macvlan** network instead — for example to put containers directly on your physical LAN — you need to create it first.

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