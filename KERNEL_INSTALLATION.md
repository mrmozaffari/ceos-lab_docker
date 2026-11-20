# ⚙️ Kernel Installation

This guide installs kernel **5.4.164** on an Ubuntu VM. Do this **before** the Docker installation (see `DOCKER-INSTALLATION.md`). The lab hosts run this kernel.

Verified on:

- Ubuntu 20.04 (the lab hosts).
- Ubuntu 24.04 (BIOS boot, virtio disk, root filesystem on LVM). This is an unusual combination (a 2020 kernel with a 2024 userspace), so follow the pre-checks and the one-time test boot below.

> 💡 Take a VM snapshot (checkpoint) first. If the new kernel does not boot, you can pick the old one from the GRUB menu or restore the snapshot.

Run everything as root (`sudo -i`).

---

## 🔎 Step 0: Pre-Checks

```bash
lsb_release -ds
uname -r
[ -d /sys/firmware/efi ] && echo UEFI || echo BIOS
mokutil --sb-state 2>/dev/null
findmnt /boot
lsblk -f
cat /proc/cmdline
```

How to read the result:

- **BIOS or UEFI.** On BIOS, nothing more to do. On UEFI, Secure Boot must be **disabled**, because this kernel is not signed. (`EFI variables are not supported` from `mokutil` also means BIOS.)
- **`findmnt /boot`.** If the VM has a separate `/boot` partition (a small ext4 partition, usually 1 to 2 GB), this command must print it. If it prints nothing while `lsblk` shows an unmounted ext4 partition, **stop and fix it first** (Step 0b). Otherwise the kernel files would be copied to the wrong place and GRUB would never see them.
- **`/proc/cmdline`.** Look for `ipv6.disable=1`. The lab does not work with it (see Step 4).

---

## 🧱 Step 0b: Fix a `/boot` Partition That Is Not Mounted (only if Step 0 showed the problem)

Typical cause: `/etc/fstab` refers to `/dev/sda2`, but on this VM the disk is `vda` (or the other way round), so the entry never matches. Mount it by UUID instead.

```bash
blkid                                   # find the UUID of the small ext4 boot partition
cp /etc/fstab /etc/fstab.bak
nano /etc/fstab                         # change the /boot line to:
                                        # UUID=<the-uuid> /boot ext4 defaults 0 1
```

If `/boot` currently contains files (they live on the root volume, not on the partition), move them aside **only while `/boot` is not mounted**. Moving files out of a mounted `/boot` empties the real boot partition and the VM will not boot.

```bash
if mountpoint -q /boot; then
  echo "/boot is already mounted: do NOT move anything"
else
  mkdir -p /root/boot-rootfs-backup
  mv /boot/* /root/boot-rootfs-backup/ 2>/dev/null
  systemctl daemon-reload
  mount /boot
fi

findmnt /boot
ls /boot/grub                           # must exist now
```

Any kernel files that ended up in the backup folder (for example from a kernel update installed while `/boot` was unmounted) are not in GRUB's menu. Leave them there unless you want that kernel.

---

## 1. Download the Kernel Folder

Download the `kernel` folder into your Ubuntu VM and point a variable at it (adjust the path):

```bash
K=/root/ceos-lab_docker/kernel
ls -l $K
```

It must contain:

```text
vmlinuz-5.4.164
initrd.img-5.4.164
System.map-5.4.164
config-5.4.164
modules-5.4.164.tar.gz
```

---

## 2. Check That the Kernel Has Your VM's Drivers

This kernel was built for the lab hosts. It must contain the driver for **this** VM's disk and network card, and the initrd must be able to find the root disk. Otherwise the VM will not boot, or will boot with no network.

```bash
# Drivers this VM uses
for d in /sys/block/*/device/driver; do echo "$d -> $(readlink $d)"; done
for n in /sys/class/net/*; do echo "$n: $(readlink $n/device/driver 2>/dev/null)"; done

# What the new kernel provides
grep -E '^CONFIG_(VIRTIO_BLK|VIRTIO_PCI|VIRTIO_NET|HYPERV|HYPERV_STORAGE|HYPERV_NET|BLK_DEV_DM|EXT4_FS|BLK_DEV_INITRD|RD_GZIP)=' $K/config-5.4.164
tar -tzf $K/modules-5.4.164.tar.gz | grep -E '/(virtio_blk|virtio_pci|virtio_net|hv_vmbus|hv_storvsc|hv_netvsc|dm-mod|ext4)\.ko'

# What the initrd contains
lsinitramfs $K/initrd.img-5.4.164 | grep -E 'virtio_blk|lvm' | head
```

Every driver your VM uses must be `=y` (built in) or `=m` with its `.ko` file in the tarball. If the root filesystem is on LVM (`lsblk -f` shows `LVM2_member`), the initrd must contain an `lvm` binary and the disk driver module. If the initrd from the download lacks them, build a new one after Step 3:

```bash
mkinitramfs -c gzip -o /boot/initrd.img-5.4.164 5.4.164
```

(Use `gzip`: a 5.4 kernel cannot unpack the zstd compression that newer Ubuntu releases use by default.)

---

## 3. Copy the Kernel Files and Update GRUB

Every step is chained, so it stops at the first failure.

```bash
findmnt /boot || echo "(no separate /boot partition on this VM)"

cp $K/vmlinuz-5.4.164 $K/initrd.img-5.4.164 $K/System.map-5.4.164 $K/config-5.4.164 /boot/ && \
tar -xzf $K/modules-5.4.164.tar.gz -C /lib/modules/ && \
test -d /lib/modules/5.4.164 && \
depmod 5.4.164 && \
update-grub
```

The output must include `Found linux image: /boot/vmlinuz-5.4.164`. If you see an error about `/boot/grub`, go back to Step 0b.

---

## 4. Kernel Command Line: IPv6 Must Be Enabled

The cEOS nodes need IPv6 in the kernel. If the command line contains `ipv6.disable=1` (some hardened images set it), the nodes boot only halfway: ports stay `unknown`, `cpu`/`fabric`/`fwd0` devices never appear, and `EosPreloadPy.service` fails.

```bash
grep -n CMDLINE /etc/default/grub /etc/default/grub.d/* 2>/dev/null
```

If `ipv6.disable=1` is there, remove it:

```bash
cp /etc/default/grub /etc/default/grub.bak
sed -i 's/ipv6.disable=1 *//' /etc/default/grub
grep -n CMDLINE /etc/default/grub
```

> If this VM is hardened by someone else's policy, check that you are allowed to change it.

---

## 5. Find the Exact Menu Entry Name

```bash
update-grub
grep -E "menuentry '|submenu '" /boot/grub/grub.cfg | cut -d"'" -f2
```

You should see the submenu `Advanced options for Ubuntu` and, inside it, `Ubuntu, with Linux 5.4.164` (not the `(recovery mode)` one). Use the names exactly as printed. The path to the entry is `submenu>entry`, for example:

```text
Advanced options for Ubuntu>Ubuntu, with Linux 5.4.164
```

---

## 6. Boot the New Kernel

### 6a. One-time test boot (recommended)

This boots 5.4.164 once. If it fails, the next reboot goes back to the old kernel.

```bash
cp /etc/default/grub /etc/default/grub.bak
sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=saved/' /etc/default/grub
sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=menu/; s/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=5/' /etc/default/grub
grep -E '^GRUB_(DEFAULT|TIMEOUT|TIMEOUT_STYLE)' /etc/default/grub /etc/default/grub.d/* 2>/dev/null
update-grub

grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 5.4.164"
reboot
```

The visible 5 second menu lets you pick an older kernel from the hypervisor console.

### 6b. Make it the default

After the test boot works (Step 7), make it permanent:

```bash
grub-set-default "Advanced options for Ubuntu>Ubuntu, with Linux 5.4.164"
```

Alternatively, without `saved`, put the same string in `/etc/default/grub`:

```text
Comment out this line:
#GRUB_DEFAULT=0

And add this:
GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux 5.4.164"
```

then run `update-grub`. GRUB looks the entry up by name, so it keeps booting 5.4.164 even after Ubuntu installs newer kernels.

---

## 7. Verify After the Reboot

```bash
uname -r                                # 5.4.164
grep -c 'ipv6.disable' /proc/cmdline    # 0
ip -6 addr show lo                      # shows inet6 ::1
ip -br addr                             # your network card has its address
systemctl --failed
```

On Ubuntu 24.04, `systemctl --failed` may list a few units, and a desktop VM may come up without a graphical screen. SSH and the console still work, which is all the lab needs.

---

## 🛠️ Troubleshooting

**The VM still boots the old kernel**
The `GRUB_DEFAULT` text or the `grub-reboot` argument does not match the menu entry. Compare it character by character with the output of Step 5, then run `update-grub` and reboot.

**The new kernel does not boot or hangs**
Open the VM console. At boot, hold `Shift` (BIOS) or press `Esc` (UEFI) if the menu is hidden, choose `Advanced options for Ubuntu`, and pick the previous kernel. With the one-time boot from Step 6a, a reset is enough. To go back for good: `cp /etc/default/grub.bak /etc/default/grub && update-grub`, or restore the snapshot.

**It drops to an `initramfs` prompt or says it cannot find the root device**
The initrd lacks the disk driver or LVM tools. Boot the old kernel and rebuild it (`mkinitramfs -c gzip -o /boot/initrd.img-5.4.164 5.4.164`), then check it with `lsinitramfs /boot/initrd.img-5.4.164 | grep -E 'virtio_blk|lvm'`.

**`update-grub` does not list 5.4.164, or `/boot/grub` does not exist**
Either the files are not in `/boot`, or `/boot` is a different filesystem than the one GRUB uses (Step 0b). Check `findmnt /boot` and `ls /boot`.

**`/boot` is empty after running `mv /boot/*`**
You moved the files out of the mounted boot partition. Do **not** reboot. Copy them back from the backup folder: `cp -a /root/boot-rootfs-backup/. /boot/` (skip any kernel versions you do not want), then check with `ls /boot/grub/grub.cfg`.

**Network interface or modules look wrong after the reboot**
Check that `/lib/modules/5.4.164` exists and is not empty. If the archive extracted into a nested folder, move the contents so the path is exactly `/lib/modules/5.4.164`, then run `depmod 5.4.164`.

---

## ➡️ Next Step

Continue with `DOCKER-INSTALLATION.md`.
