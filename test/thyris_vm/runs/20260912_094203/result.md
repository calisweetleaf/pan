# Thyris Android guest boot run 20260912_094203

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260912_094203.
I found status `pass` with 4 passed, 0 failed, 0 skipped.

## What I required

I required qemu-system-x86_64, the official android-x86_64-9.0-r2.iso
(SHA-1 1cc85b5ed7c830ff71aecf8405c7281a9c995aa0), a qcow2 from landed
ISOConverter._create_disk, and SeaBIOS/ISOLINUX on -nographic stdout.
I refused a dummy boot, prompt_bridge, a second disk-create owner, and
a READY-phone claim.

Claim: qemu-system-x86_64 -nographic booted official android-x86_64-9.0-r2.iso far enough for SeaBIOS/ISOLINUX console evidence. Disk came from landed ISOConverter._create_disk. This is not PhoneVMState.READY or ADB userspace.

## Checks

- `qemu_system_resolves`: pass
- `android_iso_authentic`: pass
- `nographic_argv`: pass
- `android_installer_boot`: pass

## Artifacts

- `/workspace/test/thyris_vm/runs/20260912_094203/result.json`
- `/workspace/test/thyris_vm/runs/20260912_094203/result.md`
- `/workspace/test/thyris_vm/runs/20260912_094203/result.log`

