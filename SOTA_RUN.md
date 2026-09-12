# SOTA_RUN — Android-x86 installer boot via nographic console

**Date:** 2026-09-12
**Mode:** EDIT (see SCOPE.md engagement 4)
**Claim:** `ThyrisPhoneOrchestrator.boot_android_installer` starts a real
`qemu-system-x86_64` guest from the official `android-x86_64-9.0-r2.iso`
(SHA-1 `1cc85b5ed7c830ff71aecf8405c7281a9c995aa0`) and fails loud unless
ISOLINUX appears on `-nographic` stdout. The qcow2 comes from landed
`ISOConverter._create_disk` (`ba05cf4`). This is not a claim that
`PhoneVMState.READY` or ADB userspace was proven. Disk-create was not
reimplemented. Immune/ROE/`BlockchainThreatIntelligence` stay `32ea3a9`.

## Commands

```bash
python test/thyris_vm/test_thyris_android_boot.py
```

- Android boot consumer: **PASS**, 4/4 including `android_installer_boot`
- Tree: `32ea3a9` + this unit
- Python: 3.14.4 (Windows, `.venv`)
- qemu-system-x86_64 11.1.0 (`C:\Program Files\qemu\qemu-system-x86_64.exe`)
- qemu-img 11.1.0 on PATH via `ensure_windows_qemu_on_path`
- accelerator: `-accel tcg` (never `-enable-kvm` on Windows)
- ISO: `android_images/android-x86_64-9.0-r2.iso` (965,738,496 bytes, gitignored)
- SHA-1 matched android-x86.org 9.0-r2
- Console markers: SeaBIOS, Booting from DVD, ISOLINUX, isolinux
- `phone_ready`: false
- `adb_proven`: false

`32ea3a9` immune retirement remains landed (`snapshots/v0.10`). This boot
consumer is **not** in `test/run_pan_gate.py`.

## Slices

| Slice | Result |
|---|---|
| qemu_system_resolves | PASS |
| android_iso_authentic | PASS |
| nographic_argv | PASS |
| android_installer_boot | PASS (ISOLINUX required) |

## Artifacts

- Boot focused: `test/thyris_vm/runs/20260912_043438/`
- Snapshot: `snapshots/v0.11/manifest.json`
- Prior immune snapshot: `snapshots/v0.10/manifest.json`
- Prior disk-create snapshot: `snapshots/v0.9/manifest.json`
- Prior gate (immune, not this boot): `results/pan_gate_20260912_092909.json`

## Skipped / not proven

- PhoneVMState.READY / ADB userspace / in-guest Android desktop
- `PAN_SDK/API.server.py` remains an unconsumed sleep-and-string subclass
- DHT `usms_linkage` / `mesh-strand` / signed `pan_refs` (not in this tree; not invented)
- `memory/memory_integration.py` still needs `schemas.session`
- Orama dashboard / 1536-d vector spaces
