# Thyris Android guest boot run 20260918_023707

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260918_023707.
I found status `fail` with 6 passed, 2 failed, 0 skipped.

## What I required

I required qemu-system-x86_64, the official android-x86_64-9.0-r2.iso
(SHA-1 1cc85b5ed7c830ff71aecf8405c7281a9c995aa0), a qcow2 from landed
ISOConverter._create_disk, SeaBIOS/ISOLINUX on installer -nographic stdout,
and a separate live kernel/initrd boot that only sets phone_ready after
adb connect + adb shell. I refused a dummy boot, prompt_bridge, a second
disk-create owner, and READY from ISOLINUX.

Claim: Installer ISOLINUX remains a non-READY proof. ADB userspace was not proven; phone_ready stays false.

## Checks

- `qemu_system_resolves`: pass
- `android_iso_authentic`: pass
- `nographic_argv`: pass
- `adb_resolves`: pass
- `extract_live_boot_files`: pass
- `live_argv_forwards_adb`: fail
  - error: `CheckFailure: live argv is missing isolinux.cfg DEBUG=2 SRC= DATA= append`
- `android_installer_boot`: pass
- `android_adb_userspace`: fail
  - error: `CheckFailure: Android live boot failed before ADB: live ADB argv is missing isolinux.cfg DEBUG=2 SRC= append`

## Artifacts

- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_023707\result.json`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_023707\result.md`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_023707\result.log`

