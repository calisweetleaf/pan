# SOTA_RUN — qemu-img disk-create + immune ROE DAG

**Date:** 2026-09-12
**Mode:** EDIT (see SCOPE.md)
**Claim:** `ISOConverter._create_disk` fails loud without qemu-img and writes a
real qcow2 when qemu-img is present. `PlanetaryImmuneSystem` persists ROE
OBSERVE/DECEIVE/DEGRADE as USMS BELIEF content with neighbor-weighted DAG
activation; `DefensiveOffensiveBridge.process_threat_event` writes through that
owner. ROE Level 4 without human authorization fails loud and is not an
external-host action. This is not a claim that phones boot, that an Android
image exists, or that `BlockchainThreatIntelligence` was retired.

## Commands

```bash
python3 test/thyris_vm/test_thyris_vm.py
python3 test/immune/test_planetary_immune_system.py
python3 test/run_pan_gate.py
```

- Thyris VM consumer: **PASS**, 7/7 including `qemu_img_disk_create`
- Immune consumer: **PASS**, 11/11 including ROE persist + L4 deny
- Project gate: **PASS**, exit 0, 16.705s
- Python: 3.12.3 (Linux)
- qemu-img 8.2.2 (`/usr/bin/qemu-img`)
- qemu-system-x86_64 8.2.2 (`/usr/bin/qemu-system-x86_64`)
- adb: missing

## Slices

| Slice | Result |
|---|---|
| compile | PASS (includes D/O lineage files) |
| import | PASS |
| persistence | PASS |
| name_registry | PASS |
| manifest | PASS |
| personal_data | PASS |
| system_scenario | PASS |
| planetary_immune_system | PASS (11/11) |
| sovereign_treasury | PASS |
| email_social | PASS |
| master_db | PASS |
| thyris_memory | PASS |
| thyris_vm | PASS (7/7, disk-create proven) |

## Artifacts

- Thyris focused: `test/thyris_vm/runs/20260912_091429/`
- Immune focused: `test/immune/runs/20260912_091516/`
- Gate: `results/pan_gate_20260912_091538.json`
- Gate: `results/pan_gate_20260912_091538.md`
- Snapshot: `snapshots/v0.9/manifest.json`

## Skipped / not proven

- QEMU guest boot / Android image / adb
- `PAN_SDK/API.server.py` remains an unconsumed sleep-and-string subclass
- `BlockchainThreatIntelligence` still exists in `defensive_sovereignty.py`
- `memory/memory_integration.py` still needs `schemas.session`
- Orama dashboard / 1536-d vector spaces
