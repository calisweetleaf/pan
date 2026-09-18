# Thyris Android guest boot run 20260918_020146

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260918_020146.
I found status `fail` with 7 passed, 1 failed, 0 skipped.

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
- `live_argv_forwards_adb`: pass
- `android_installer_boot`: pass
- `android_adb_userspace`: fail
  - error: `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\trent\\AppData\\Local\\Temp\\thyris_adb_tknlfptc\\phones\\pan_phone_registry\\pan_state.db'`

## Artifacts

- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_020146\result.json`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_020146\result.md`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_020146\result.log`

