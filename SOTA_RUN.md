# SOTA_RUN — Real SovereignInferenceEngine._run_inference owner

**Date:** 2026-09-11
**Mode:** EDIT (see SCOPE.md)
**Claim:** `_run_inference` loads PANLIN01 integer weights from disk, verifies
SHA-256 against `ModelManifest.model_hash`, and emits a deterministic latin-1
decode. Treasury `verify_proof_of_inference` re-runs that owner before mint.
This is not a claim that `API.server.py` is the owner, that QEMU VMs boot, or
that PANLIN01 is a neural LLM.

## Commands

```bash
python3 test/inference/test_sovereign_inference.py
python3 test/treasury/test_sovereign_treasury.py
python3 test/run_pan_gate.py
```

- Inference consumer: **PASS**, 7/7 checks
- Treasury consumer (focused): **PASS**, 7/7 checks
- Treasury consumer (gate slice): **PASS**, 7/7 checks
- Project gate: **PASS**, exit 0, 14.016s
- Python: 3.12.3 (Linux)

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
| planetary_immune_system | PASS |
| sovereign_treasury | PASS (7/7 including forged-output reject) |
| email_social | PASS |
| master_db | PASS |
| thyris_memory | PASS |
| thyris_vm | PASS |

## Artifacts

- Latest complete inference run: `test/inference/runs/20260911_085509/`
  - `result.json`
  - `result.md`
  - `result.log`
- Focused treasury run: `test/treasury/runs/20260911_085523/`
- Gate treasury slice: `test/treasury/runs/20260911_085647/`
- Gate: `results/pan_gate_20260911_085638.json`
- Gate: `results/pan_gate_20260911_085638.md`
- Snapshot: `snapshots/v0.8/manifest.json`

## Ledger counts (latest complete inference result.json)

The latest complete `result.json` is `test/inference/runs/20260911_085509/result.json`:

- status: pass
- pass_count: 7
- fail_count: 0
- skip_count: 0

Gate treasury `test/treasury/runs/20260911_085647/result.json`:

- status: pass
- pass_count: 7
- fail_count: 0
- skip_count: 0

## Skipped / not proven

- QEMU / Android image / in-VM boot. Host tools still missing on this Linux worker.
- `PAN_SDK/API.server.py` `_run_inference_async` remains an unconsumed sleep-and-string subclass. It is not this owner.
- `SovereignPipeline.create_download_package` still ships simulated model bytes.
- `memory/memory_integration.py` still needs `schemas.session`
- Orama dashboard / 1536-d vector spaces
- USMS as a whole is not claimed SOTA++ (pre-existing broad `except Exception`)
- Thyris pulled modules are not claimed SOTA++
