# SCOPE — EDIT: real SovereignInferenceEngine._run_inference owner

**Status:** OPEN 2026-09-11. Active Code Forge unit.
**Ledger:** SOTA_RUN.md (to be written after the consumer/gate run)
**Snapshot:** snapshots/v0.8/manifest.json

## Engagement Mode

- mode: EDIT
- target_module: PAN_SDK/PAN_SDK.py
- target_module_provenance: PAN monolith SovereignInferenceEngine (placeholder `_run_inference` returned a canned string; treasury PoI re-hashed `{prompt, output}`)
- justification: I am editing the owned inference method in place because wrapping a second engine would duplicate the packet/manifest contract already on SovereignInferenceEngine, and API.server.py is forbidden as a parallel owner. Treasury Proof-of-Inference already calls a commitment helper; that helper cannot stay hash-theater once a local re-executable owner exists. A wrapper around the placeholder would preserve the dummy. Direct edit is the only way for validators to re-run the same decode path the worker ran.
- author: daeron
- date: 2026-09-11

## Runtime options (material choice)

Validators must re-execute the identical deterministic task (whitepaper §4.3). No dummy string. No `prompt_bridge`. No second engine in `PAN_SDK/API.server.py`. No new microservice.

| Option | Runtime | Re-executable by treasury validators? | Decision |
|---|---|---|---|
| A | In-process stdlib integer linear decoder owned by `SovereignInferenceEngine`. Weights live on disk (`PANLIN01`), SHA-256 matches `ModelManifest.model_hash`, decode is integer matvec + argmax. `numpy` is in requirements.txt but unused in this monolith; floats/BLAS would jeopardize bit-identical replay. | Yes. Same file bytes + prompt + temperature_milli + max_tokens => same latin-1 output. | **SELECTED** |
| B | In-process numpy float MLP | Fragile across OS/BLAS; not a bit-identical PoI surface. | Rejected |
| C | torch / llama.cpp / GGUF / remote HTTP model | New runtime, not already the consumed owner, not fail-closed offline, not stdlib. | Rejected |
| D | Keep SHA-256 of a canned `{prompt, output}` pair | Current theater. No model is run. | Rejected |
| E | Implement `_run_inference_async` as a second owner in `API.server.py` | Forbidden parallel engine. API path stays unconsumed. | Rejected |
| F | `core.prompt_bridge` / PromptSystemBridge | Rejected architecture (Thyris/AIPC). | Rejected |

Choice: **Option A**. Treasury `verify_proof_of_inference` binds that same owner and re-runs `infer` before accepting a mint.

## Targets

| Target | Owner | Consumed boundary |
|---|---|---|
| `PAN_SDK/PAN_SDK.py` | `SovereignInferenceEngine._run_inference` plus disk load / integer decode | Local re-executable inference; `process_request` calls this owner |
| `PAN_SDK/treasury.py` | `verify_proof_of_inference` / `build_proof` | PoI mint re-executes the bound engine, not a hash of a claimed string |
| `test/inference/test_sovereign_inference.py` | focused consumer | load fail-loud, replay match, prompt divergence, packet path |
| `test/treasury/test_sovereign_treasury.py` | existing Fed consumer | mint uses real PoI; forged output is rejected |

## Direct-edit justification

The placeholder lived inside the owning class. A WRAP adapter would either call the dummy or copy decode logic beside it. API.server.py already subclasses the engine with a sleep-and-string async path; that file is out of this unit and must not become the owner. Treasury already owns PoI verification; it must call the real engine or mint stays theater.

## Out of scope

- qemu / Android images / Thyris boot
- `prompt_bridge`, `schemas.session`, `memory_system`
- Editing `PAN_SDK/API.server.py` into a second engine
- Orama / vector spaces / master_db §6.2
- Auto-binding EmailSocialNode onto DHTNode
- Publication, deploy, purchase
