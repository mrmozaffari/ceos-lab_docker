# 🐳 Downgrade Docker to (24.0.6) on Ubuntu

The lab may experience issues with later version of docker.
This guide explains how to safely downgrade Docker to **24.0.6** on Ubuntu.

---

## 🧼 Step 1: Remove Current Docker Installation

```bash
sudo apt remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo apt purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo rm -rf /var/lib/docker
```

---

## 📦 Step 2: Set Up Docker APT Repository (If Not Already Done)

```bash
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker’s official GPG key
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

## 🔍 Step 3: Find Available Versions

Run this to check if version `24.0.6` is available for your OS:

```bash
apt-cache madison docker-ce
```

Look for a line similar to:

```
 docker-ce | 5:24.0.6-1~ubuntu.22.04~jammy | ...
```

---

## ⬇️ Step 4: Install Docker 24.0.6

Install the required version by specifying the exact version strings:

```bash
sudo apt install -y \
  docker-ce=5:24.0.6-1~ubuntu.22.04~jammy \
  docker-ce-cli=5:24.0.6-1~ubuntu.22.04~jammy \
  containerd.io=1.6.21-1 \
  docker-buildx-plugin=0.11.2-1~ubuntu.22.04~jammy \
  docker-compose-plugin=2.21.0-1~ubuntu.22.04~jammy
```

> ⚠️ **Note**: If you're using a different Ubuntu version (`focal`, `bionic`, etc.), adjust accordingly.

---

## 🔒 Step 5: Prevent Future Upgrades (Optional)

```bash
sudo apt-mark hold docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

---

## ✅ Step 6: Confirm Docker Version

```bash
docker -v
# Output should show: Docker version 24.0.6
```

---

## 🛠️ Troubleshooting

If `24.0.6` doesn't appear in the list, please run:

```bash
apt-cache madison docker-ce
```

---

```