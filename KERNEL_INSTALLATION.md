# ⚙️ Kernel Installation

This guide installs kernel **5.4.164** on an Ubuntu VM. Do this **before** the Docker installation (see `DOCKER-INSTALLATION.md`). The lab hosts run this kernel.

> 💡 Take a VM snapshot first. If the new kernel does not boot, you can pick the old one from the GRUB menu (see Troubleshooting).

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

```bash
sudo cp ~/kernel/vmlinuz-5.4.164 /boot/
sudo cp ~/kernel/initrd.img-5.4.164 /boot/
sudo cp ~/kernel/System.map-5.4.164 /boot/
sudo cp ~/kernel/config-5.4.164 /boot/
sudo tar -xzf ~/kernel/modules-5.4.164.tar.gz -C /lib/modules/
```

Check that everything landed:

```bash
ls /boot | grep 5.4.164
ls /lib/modules/
```

You should see the four files in `/boot` and a `5.4.164` directory in `/lib/modules`.

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

Look for the submenu `Advanced options for Ubuntu` and the entry `Ubuntu, with Linux 5.4.164` inside it. Use these names exactly in the next step. There may also be a `(recovery mode)` entry for the same kernel, which is not the one you want.

---

## 5. Set the Default Kernel

Open the GRUB settings:

```bash
sudo nano /etc/default/grub
```

Edit the file and save:

```text
Comment out this line:
#GRUB_DEFAULT=0

And add this:
GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux 5.4.164"
```

The format is `submenu name>entry name`, separated by `>`, with no spaces around it. The name must match what Step 4 printed. Because GRUB looks the entry up by name, it keeps booting 5.4.164 even after Ubuntu installs newer kernels later.

---

## 6. Update GRUB Again

```bash
sudo update-grub
```

---

## 7. Reboot

```bash
sudo reboot
```

---

## 8. Check the Kernel Version

```bash
uname -r
```

Expected output:

```text
5.4.164
```

If it shows a different version, go back to Step 4 and check that the `GRUB_DEFAULT` name matches exactly, then run `sudo update-grub` and reboot again.

---

## 🛠️ Troubleshooting

**The VM still boots the old kernel**
The `GRUB_DEFAULT` text does not match the menu entry. Compare it character by character with the output of Step 4, run `sudo update-grub`, and reboot.

**The new kernel does not boot**
At boot, hold `Shift` (BIOS) or press `Esc` (UEFI) to open the GRUB menu, choose `Advanced options for Ubuntu`, and pick the previous kernel. Once logged in, restore the original line in `/etc/default/grub` (`GRUB_DEFAULT=0`), run `sudo update-grub`, and check that all five files from Step 1 were copied correctly.

**`update-grub` does not list 5.4.164**
The files in `/boot` are missing or misnamed. Re-run Step 2 and check with `ls /boot | grep 5.4.164`.

**Network interface names or modules look wrong after reboot**
Check that `/lib/modules/5.4.164` exists and is not empty. If the archive extracted into a nested folder, move the contents so that the path is exactly `/lib/modules/5.4.164`, then run `sudo depmod 5.4.164`.

---

## ➡️ Next Step

Continue with `DOCKER-INSTALLATION.md`.
