# SOTA_RUN — Thyris ADB userspace READY (not proven)

**Date:** 2026-09-18
**Mode:** EDIT (see SCOPE.md army thyris-adb-userspace-ready)
**Claim:** Not claimed. `phone_ready` and `adb_proven` stay false.
`snapshots/v0.15` is not promoted. STATE.md was not rewritten to READY.

## Attempt B — WHPX livem

`-accel whpx,kernel-irqchip=off` on the same official ISO. Installer
ISOLINUX passed. Live kernel reached `Detecting Android-x86... found at
/dev/sr0` then `console:/ #`. No `adb shell echo thyris_adb_health`.
Consumer FAIL 7/8.

- Run: `test/thyris_vm/runs/20260918_050641/`
- `phone_ready`: false
- `adb_proven`: false

## Attempt D — AUTO_INSTALL=force then disk boot

ISO `install.img` `AUTO_INSTALL=force` onto an 8G qcow from landed
`ISOConverter._create_disk`. Installer dialogs showed Formatting /
Installing Android-x86 / Syncing / Congratulations. Disk boot used
`SRC=/thyris` with no live ISO. Console: `found at /dev/sda1` then
`console:/ #`. No adb shell. Consumer FAIL 7/8.

- Run: `test/thyris_vm/runs/20260918_052020/`
- Python: Windows 3.14 `.venv`, QEMU 11.1.0 WHPX
- No leftover qemu-system-x86_64 or adb after the run
- `phone_ready`: false
- `adb_proven`: false
- Project gate: **not run** this unit

## Commands

```bash
.\.venv\Scripts\python.exe -m py_compile telecom\phone_orchestrator.py test\thyris_vm\test_thyris_android_boot.py
.\.venv\Scripts\python.exe test\thyris_vm\test_thyris_android_boot.py
```

## Artifacts

- `test/thyris_vm/runs/20260918_050641/result.json`
- `test/thyris_vm/runs/20260918_050641/result.md`
- `test/thyris_vm/runs/20260918_050641/result.log`
- `test/thyris_vm/runs/20260918_052020/result.json`
- `test/thyris_vm/runs/20260918_052020/result.md`
- `test/thyris_vm/runs/20260918_052020/result.log`
