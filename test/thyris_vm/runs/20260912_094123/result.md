# Thyris Android guest boot run 20260912_094123

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260912_094123.
I found status `fail` with 3 passed, 1 failed, 0 skipped.

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
- `android_installer_boot`: fail
  - error: `CheckFailure: Android installer boot failed loud: QEMU exited rc=1 before Android ISO boot evidence. stderr='Could not access KVM kernel module: Permission denied\nqemu-system-x86_64: failed to initialize kvm: Permission denied\n' console=''`

## Artifacts

- `/workspace/test/thyris_vm/runs/20260912_094123/result.json`
- `/workspace/test/thyris_vm/runs/20260912_094123/result.md`
- `/workspace/test/thyris_vm/runs/20260912_094123/result.log`

