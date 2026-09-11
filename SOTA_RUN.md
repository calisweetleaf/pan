# SOTA_RUN — Thyris owners (memory_core, system_cache, vm_supervisor, vm_image_manager)

**Date:** 2026-09-11
**Mode:** EDIT (see SCOPE.md)
**Claim:** Operator-pulled Thyris files are consumed owners in this repository.
`memory.memory_core` / `memory.system_cache` are Thyris VM memory. USMS remains
the immune Ed25519 DAG. `telecom.vm_supervisor` and `telecom.vm_image_manager`
are the owners `phone_orchestrator` already imported. The phone orchestrator
imports. This is not a claim that QEMU VMs boot, Android images install, or
`core.prompt_bridge` exists. The pulled modules are not claimed SOTA++
(pre-existing broad `except Exception`).

## Commands

```bash
python test/memory_core/test_memory_core.py
python test/thyris_vm/test_thyris_vm.py
python test/run_pan_gate.py
```

- Thyris memory consumer (gate slice): **PASS**, 3/3 checks
- Thyris VM consumer (gate slice): **PASS**, 5/5 checks
- Project gate: **PASS**, exit 0, 12.820s
- Python: 3.14 (Windows) via `.venv`

## Slices

| Slice | Result |
|---|---|
| compile | PASS (includes phone_orchestrator) |
| import | PASS |
| persistence | PASS |
| name_registry | PASS |
| manifest | PASS |
| personal_data | PASS |
| system_scenario | PASS |
| planetary_immune_system | PASS |
| sovereign_treasury | PASS |
| email_social | PASS |
| master_db | PASS |
| thyris_memory | PASS |
| thyris_vm | PASS |

## Artifacts

- Latest thyris_memory run: `test/memory_core/runs/20260911_004047/`
  - `result.json`
  - `result.md`
  - `result.log`
- Latest thyris_vm run: `test/thyris_vm/runs/20260911_004047/`
  - `result.json`
  - `result.md`
  - `result.log`
- Gate: `results/pan_gate_20260911_004035.json`
- Gate: `results/pan_gate_20260911_004035.md`
- Snapshot: `snapshots/v0.6/manifest.json`

## Ledger counts (latest thyris_vm result.json)

The last unit's latest `result.json` is `test/thyris_vm/runs/20260911_004047/result.json`:

- status: pass
- pass_count: 5
- fail_count: 0
- skip_count: 0

Thyris memory latest: status pass, pass_count 3, fail_count 0, skip_count 0.

## Skipped / not proven

- `core.prompt_bridge` is absent; VMSupervisor prompt methods fail loud
- `memory/memory_integration.py` needs `schemas.session`
- QEMU / Android ISO conversion / in-VM agent HTTP
- `SovereignInferenceEngine._run_inference` is still a placeholder
- Orama dashboard / 1536-d vector spaces
- USMS as a whole is not claimed SOTA++ (pre-existing broad `except Exception`)
- Thyris pulled modules are not claimed SOTA++
