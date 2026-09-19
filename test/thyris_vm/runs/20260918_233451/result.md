# Thyris Android guest boot run 20260918_233451

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260918_233451.
I found status `pass` with 9 passed, 0 failed, 0 skipped.

## What I required

I required qemu-system-x86_64, the official android-x86_64-9.0-r2.iso
(SHA-1 1cc85b5ed7c830ff71aecf8405c7281a9c995aa0), a qcow2 from landed
ISOConverter._create_disk, SeaBIOS/ISOLINUX on installer -nographic stdout,
and a disk-install via this ISO's AUTO_INSTALL=force, then a disk boot
with hidden VGA + bidirectional serial chardev (VIRT_WIFI=0, eth0
on qemu user-net 10.0.2.15) that only sets phone_ready after adb
connect + adb shell. Windows install still uses
-accel whpx,kernel-irqchip=off. POSIX disk-boot uses KVM or TCG, not
WHPX. I refused a dummy boot, prompt_bridge,
a second disk-create owner, and READY from ISOLINUX.

Claim: qemu-system-x86_64 live-booted official android-x86_64-9.0-r2.iso via kernel/initrd extracted from that same ISO. Disk came from landed ISOConverter._create_disk. PhoneVMState.READY is claimed only after adb connect + adb shell on the qemu user-net forward.

## Checks

- `qemu_system_resolves`: pass
- `android_iso_authentic`: pass
- `nographic_argv`: pass
- `adb_resolves`: pass
- `extract_live_boot_files`: pass
- `live_argv_forwards_adb`: pass
- `disk_boot_argv`: pass
- `android_installer_boot`: pass
- `android_adb_userspace`: pass

## Artifacts

- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/thyris_vm/runs/20260918_233451/result.json`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/thyris_vm/runs/20260918_233451/result.md`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/thyris_vm/runs/20260918_233451/result.log`

