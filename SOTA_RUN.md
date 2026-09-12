# SOTA_RUN — retire BlockchainThreatIntelligence; bind D/O share to USMS

**Date:** 2026-09-12
**Mode:** EDIT (see SCOPE.md)
**Claim:** `BlockchainThreatIntelligence` construction fails loud.
`ThreatDetectionModule.share_threat_intelligence` requires a bound
`PlanetaryImmuneSystem` and persists through USMS. `NetworkThreatMonitor`
writes firewall detections through that owner. ROE persist and L4 deny remain
the ba05cf4 immune owner; this unit does not re-implement them. PAN RSA and
USMS Ed25519 stay two identity types. This is not a claim that qemu-img is
present on this worker, that phones boot, or that mesh-strand/usms_linkage
exist.

## Commands

```bash
python3 test/immune/test_planetary_immune_system.py
python3 test/run_pan_gate.py
```

- Immune consumer (focused): **PASS**, 12/12 (`test/immune/runs/20260912_092843/`)
- Immune consumer (gate slice): **PASS**, 12/12 (`test/immune/runs/20260912_092917/`)
- Project gate: **FAIL** only `thyris_vm.qemu_img_disk_create` (qemu-img missing
  on this worker). All other slices PASS, including planetary_immune_system.
- Python: 3.12.3 (Linux)
- qemu-img / qemu-system-x86_64 / adb: missing on this worker (not installed)

## Slices

| Slice | Result |
|---|---|
| compile | PASS |
| import | PASS |
| persistence | PASS |
| name_registry | PASS |
| manifest | PASS |
| personal_data | PASS |
| system_scenario | PASS |
| planetary_immune_system | PASS (12/12) |
| sovereign_treasury | PASS |
| email_social | PASS |
| master_db | PASS |
| thyris_memory | PASS |
| thyris_vm | FAIL qemu-img missing (pre-existing host gap vs ba05cf4) |

## Artifacts

- Latest complete immune run: `test/immune/runs/20260912_092917/`
- Focused immune run: `test/immune/runs/20260912_092843/`
- Gate: `results/pan_gate_20260912_092909.json`
- Gate: `results/pan_gate_20260912_092909.md`
- Snapshot: `snapshots/v0.10/manifest.json`

## Skipped / not proven

- QEMU / Android image / in-VM boot on this worker
- ROE Level 4 against external hosts (fail-loud by design on the immune owner)
- DHT `usms_linkage` / `mesh-strand` / signed `pan_refs` (not in this tree; not invented)
- `PAN_SDK/API.server.py` `_run_inference_async` remains an unconsumed sleep-and-string subclass
- `memory/memory_integration.py` still needs `schemas.session`
