# SOTA_RUN — Thyris ADB userspace READY (Envy KVM)

**Date:** 2026-09-18
**Mode:** EDIT (see SCOPE.md army thyris-adb-userspace-ready)
**Claim:** Proven on `daeron-hpenvyx3602in1laptop15ey0xxx`. `phone_ready`
and `adb_proven` are true only after host `adb shell echo thyris_adb_health`
returned the guest token. Windows nographic remains exhausted.

## Attempt Envy — AUTO_INSTALL then disk-boot chardev + VIRT_WIFI=0

Official ISO SHA-1 `1cc85b5ed7c830ff71aecf8405c7281a9c995aa0`. Disk from
landed `ISOConverter._create_disk`. AUTO_INSTALL=force then disk-boot
`SRC=/thyris` with hidden VGA, bidirectional serial unix chardev under
`/tmp` (USB VFAT cannot bind AF_UNIX), `VIRT_WIFI=0` so eth0 keeps qemu
user-net `10.0.2.15`.

- Run: `test/thyris_vm/runs/20260918_233451/` (and `20260918_234216/` from main())
- Python: Linux 3.12 `.venv`, QEMU 10.2.1 KVM
- `HOST_CMD: adb -s 127.0.0.1:44451 shell echo thyris_adb_health`
- guest: `thyris_adb_health`
- Android 9, `boot_mode=installed_disk`, `internal_ip=10.0.2.15`
- `phone_ready`: true
- `adb_proven`: true
- `vm_state`: ready
- Consumer: 9/9 in 444.7s
- USB bind failure that forced `/tmp` chardev: `test/thyris_vm/runs/20260918_232743/`

## Prior Windows attempts (not READY)

- WHPX livem: `test/thyris_vm/runs/20260918_050641/` — `console:/ #`, no adbd
- AUTO_INSTALL then nographic disk: `test/thyris_vm/runs/20260918_052020/` — same

## Commands

```bash
.venv/bin/python -m py_compile telecom/phone_orchestrator.py test/thyris_vm/test_thyris_android_boot.py
PYTHONUNBUFFERED=1 .venv/bin/python -u test/thyris_vm/test_thyris_android_boot.py
```

## Artifacts

- `test/thyris_vm/runs/20260918_233451/result.json`
- `test/thyris_vm/runs/20260918_233451/result.md`
- `test/thyris_vm/runs/20260918_233451/result.log`
- `snapshots/v0.17/manifest.json`
