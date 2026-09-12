# SOTA_RUN — KVM-inaccessible Linux falls back to TCG installer boot

**Date:** 2026-09-12
**Mode:** EDIT (see SCOPE.md engagement 5)
**Claim:** `select_qemu_accelerator` opens `/dev/kvm` before passing
`-enable-kvm`. When the node exists but is not writable, QEMU uses `-accel tcg`
and `boot_android_installer` still shows ISOLINUX. `phone_ready` and
`adb_proven` stay false. Disk-create, ROE, and BlockchainThreatIntelligence
were not redone.

## Commands

```bash
python3 test/thyris_vm/test_thyris_android_boot.py
python3 test/run_pan_gate.py
```

- Android boot consumer: **PASS**, 4/4, run `20260912_094201`
- Project gate: **PASS**, exit 0, 16.853s (`results/pan_gate_20260912_094045.json`)
- Python: 3.12.3 (Linux)
- qemu-system-x86_64 8.2.2, qemu-img 8.2.2, adb 1.0.41
- accelerator: `-accel tcg` (KVM Permission denied)
- Console: SeaBIOS, Booting from DVD, ISOLINUX 6.03
- `phone_ready`: false
- `adb_proven`: false

## Artifacts

- Boot: `test/thyris_vm/runs/20260912_094201/`
- Gate: `results/pan_gate_20260912_094045.json`
- Snapshot: `snapshots/v0.12/manifest.json`
