# ⚙️ Kernel Installation

This guide installs kernel **5.4.164** on an Ubuntu VM. Do this **before** the Docker installation (see `DOCKER-INSTALLATION.md`). The lab hosts run this kernel.

> 💡 Take a VM snapshot first. If the new kernel does not boot, you can pick the old one from the GRUB menu (see Troubleshooting).

---

## 0. Prerequisites

- **Secure Boot must be off.** The 5.4.164 kernel is not signed, so a UEFI VM with Secure Boot enabled will refuse to boot it. Check the VM's firmware and boot settings in your hypervisor or cloud platform before you start.
- **Console access.** Make sure you have console access to the VM (the hypervisor console, a serial console, or a cloud provider's console). If the network breaks after the reboot, the console is how you recover.
- **Make the GRUB menu reachable.** Ubuntu cloud images often hide the GRUB menu, so you cannot pick the old kernel at boot. Check the current settings:

```bash
grep -E "GRUB_TIMEOUT|GRUB_TIMEOUT_STYLE" /etc/default/grub /etc/default/grub.d/*.cfg 2>/dev/null
```

If you see `GRUB_TIMEOUT=0` or `GRUB_TIMEOUT_STYLE=hidden`, set these in `/etc/default/grub` (and remove or change the same lines in `/etc/default/grub.d/*.cfg` if they appear there):

```text
GRUB_TIMEOUT_STYLE=menu
GRUB_TIMEOUT=5
```

---

## 1. Download the Kernel Folder

Download the `kernel` folder into your Ubuntu VM so that it ends up at `~/kernel`. It must contain:

```text
vmlinuz-5.4.164
initrd.img-5.4.164
System.map-5.4.164
config-5.4.164
modules-5.4.164.tar.gz
```

Check:

```bash
ls -l ~/kernel
```

---

## 2. Copy the Kernel Files

First check that the modules archive has the right layout. The first lines must start with `5.4.164/`:

```bash
tar -tzf ~/kernel/modules-5.4.164.tar.gz | head -3
```

Then copy everything:

```bash
sudo cp ~/kernel/vmlinuz-5.4.164 /boot/
sudo cp ~/kernel/initrd.img-5.4.164 /boot/
sudo cp ~/kernel/System.map-5.4.164 /boot/
sudo cp ~/kernel/config-5.4.164 /boot/
sudo tar -xzf ~/kernel/modules-5.4.164.tar.gz -C /lib/modules/
sudo depmod -a 5.4.164
```

Check that everything landed:

```bash
ls /boot | grep 5.4.164
ls /lib/modules/
ls /lib/modules/5.4.164 | head
```

You should see the four files in `/boot`, a `5.4.164` directory in `/lib/modules`, and files inside that directory (not empty).

---

## 3. Update GRUB

This makes the new kernel appear in the GRUB menu, which you need for the next step.

```bash
sudo update-grub
```

The output should list `Found linux image: /boot/vmlinuz-5.4.164`.

---

## 4. Find the Exact Menu Entry Name

```bash
grep -E "menuentry '|submenu '" /boot/grub/grub.cfg | cut -d"'" -f2
```

Look for the submenu `Advanced options for Ubuntu` and the entry `Ubuntu, with Linux 5.4.164` inside it. Use these names exactly in the next step.

> ⚠️ You may see extra entries for the same kernel. Ignore them:
> - `Ubuntu, with Linux 5.4.164 (recovery mode)`
> - any entry ending in `(on /dev/sda1)` (these come from `os-prober` and are duplicates)

---

## 5. Optional: Test Boot Once

This boots the new kernel one time only. If it fails, a normal reboot returns to the old kernel. Skip to Step 6 if you prefer to set the default straight away.

Back up the GRUB settings first:

```bash
sudo cp /etc/default/grub /etc/default/grub.bak
```

Set the default to `saved`, update GRUB, and tell it to boot the new kernel next time only:

```bash
sudo sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=saved/' /etc/default/grub
sudo update-grub
sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 5.4.164"
sudo reboot
```

After the reboot, run the checks in Step 9. If everything works, continue with Step 6 to make the kernel permanent. If it does not boot, reboot again and the VM comes up on the old kernel.

---

## 6. Set the Default Kernel

If you did not do Step 5, back up the GRUB settings first:

```bash
sudo cp /etc/default/grub /etc/default/grub.bak
```

Open the GRUB settings:

```bash
sudo nano /etc/default/grub
```

Edit the file and save:

```text
Comment out this line (it may say GRUB_DEFAULT=saved if you did Step 5):
#GRUB_DEFAULT=0

And add this:
GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux 5.4.164"
```

The format is `submenu name>entry name`, separated by `>`, with no spaces around it. The name must match what Step 4 printed. Because GRUB looks the entry up by name, it keeps booting 5.4.164 even after Ubuntu installs newer kernels later.

> 💡 If the entry text ever changes (for example after a distro upgrade), GRUB falls back to the first entry without warning. Run `uname -r` after any kernel update to confirm you are still on 5.4.164.

---

## 7. Update GRUB Again

```bash
sudo update-grub
```

---

## 8. Reboot

```bash
sudo reboot
```

---

## 9. Check the Kernel Version and the Network

```bash
uname -r
```

Expected output:

```text
5.4.164
```

If it shows a different version, go back to Step 4 and check that the `GRUB_DEFAULT` name matches exactly, then run `sudo update-grub` and reboot again.

A new kernel can rename the network interface or miss a driver, so also check:

```bash
ip -br a
lsblk
```

You should see your network interface with its IP address and your disks. If the IP is missing, see Troubleshooting.

---

## 🛠️ Troubleshooting

**The VM still boots the old kernel**
The `GRUB_DEFAULT` text does not match the menu entry. Compare it character by character with the output of Step 4, run `sudo update-grub`, and reboot.

**The new kernel does not boot**
Open the VM console (hypervisor, serial or cloud console). At boot, hold `Shift` (BIOS) or press `Esc` (UEFI) to open the GRUB menu, choose `Advanced options for Ubuntu`, and pick the previous kernel. If the menu does not appear, see Step 0 (GRUB menu timeout). Also check that Secure Boot is off. Once logged in, restore the backup (`sudo cp /etc/default/grub.bak /etc/default/grub`) or set `GRUB_DEFAULT=0`, run `sudo update-grub`, and check that all five files from Step 1 were copied correctly.

**`update-grub` does not list 5.4.164**
The files in `/boot` are missing or misnamed. Re-run Step 2 and check with `ls /boot | grep 5.4.164`.

**Network interface names or modules look wrong after reboot**
Check that `/lib/modules/5.4.164` exists and is not empty. If the archive extracted into a nested folder, move the contents so that the path is exactly `/lib/modules/5.4.164`, then run `sudo depmod -a 5.4.164`. If the interface name changed (for example from `ens3` to `eth0`), update the interface name in your netplan file under `/etc/netplan/`, then run `sudo netplan apply`.

**Undo everything**
Restore the GRUB settings with `sudo cp /etc/default/grub.bak /etc/default/grub`, run `sudo update-grub`, and reboot. The kernel files in `/boot` can stay in place.

---

## ➡️ Next Step

Continue with `DOCKER-INSTALLATION.md`.
