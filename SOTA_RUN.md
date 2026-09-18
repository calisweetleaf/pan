# SOTA_RUN — Thyris ADB userspace READY (not proven)

**Date:** 2026-09-18
**Mode:** EDIT (see SCOPE.md army thyris-adb-userspace-ready)
**Claim:** Not claimed. `phone_ready` and `adb_proven` stay false.
`snapshots/v0.15` is not promoted. STATE.md was not rewritten.

Live kernel/initrd from official android-x86 9.0-r2, isolinux.cfg `DEBUG=2 SRC= DATA=`,
leftover qemu/adb killed, `PhoneVMState.READY` only after `adb shell echo
thyris_adb_health`. Consumer failed loud: connect failed / devices offline
after 900s. Guest did reach Android `init` / `healthd` on TCG. That is not READY.

## Commands

```bash
.\.venv\Scripts\python.exe -m py_compile telecom\phone_orchestrator.py test\thyris_vm\test_thyris_android_boot.py
.\.venv\Scripts\python.exe test\thyris_vm\test_thyris_android_boot.py
```

- Boot consumer: **FAIL**, 7 passed / 1 failed (`android_adb_userspace`)
- Run: `test/thyris_vm/runs/20260918_025416/`
- Python: Windows 3.14 `.venv`, QEMU 11.1.0 TCG
- Leftover adb PID 26304 killed before retry; no leftover qemu-system-x86_64
- `phone_ready`: false
- `adb_proven`: false
- Project gate: **not run** this unit

## Artifacts

- `test/thyris_vm/runs/20260918_025416/result.json`
- `test/thyris_vm/runs/20260918_025416/result.md`
- `test/thyris_vm/runs/20260918_025416/result.log`
