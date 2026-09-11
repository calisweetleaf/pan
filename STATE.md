# PAN SDK — Current State

**Updated:** 2026-09-11
**Canon lock:** PLAN.md and docs/research/Building a Sovereign Digital Nation.md
remain the north-star direction. Do not replace their architecture with an
invented alternative.

## What exists now

- Production topology: `PAN_SDK/`, telecom/, security/, tools/, and test/.
- `PAN_SDK/PAN_SDK.py` is the central PAN monolith. The package directory is
  named `PAN_SDK` because that is the consumed import contract.
- Name registrations persist through `PANPersistenceStore` kv component
  `name_registry` (`store_name` / `get_name`) and hydrate on `PANNameRegistry`
  / `DHTNode`.
- Direct project gate: `python3 test/run_pan_gate.py`.
- Historical lineage: reference-code/, archives/, and the 2025-10-02 Windows
  result under results/ (append-only; not rewritten).

## Verified baseline

- **GREEN, 2026-09-11:** `python3 test/run_pan_gate.py` exited 0 in 2.037s.
  Slices: compile, import, persistence, name_registry, manifest, personal_data,
  system_scenario. Artifacts:
  `results/pan_gate_20260911_030722.json`,
  `results/pan_gate_20260911_030722.md`,
  `results/pan_sdk_system_test_20260911_030723.txt`.
- **GREEN:** `from PAN_SDK import DHTNode, PANNameRegistry, PANPersistenceStore`
  succeeds from repo root.
- **SKIPPED (named, not hidden):** compile of
  `telecom/phone_orchestrator.py` — missing Thyris `vm_supervisor` /
  `memory_system` owners.
- The 2025-10-02 Windows system result remains historical evidence only.

## Active frontier

1. Thyris phone VM owners (`vm_supervisor`, `memory_system`) so
   `telecom/phone_orchestrator.py` can import without dummies.
2. Agnostic model inference service. `SovereignInferenceEngine._run_inference`
  is still a placeholder and is not claimed as working inference.
3. Regenerate `filetree.md` with FileTree Pro after the `sdk/` → `PAN_SDK/`
   rename. Do not hand-edit it.

## Known decision boundaries

- Package layout `PAN_SDK/` is resolved by the consumed contract. Do not re-open
  it with a shim, PYTHONPATH hack, or second package.
- Cursor must still present evidence before selecting a new persistence
  schema, protocol/service boundary, deployment, publication, or external-action
  direction.
- Do not add a wrapper, proxy package, or parallel implementation merely to bypass
  a direct integration.

## Generated-map status

`filetree.md` is structurally stale (still shows `sdk/`, omits `.cursor/`,
SCOPE.md, SOTA_RUN.md, probes). Regenerate with FileTree Pro.

## Next justified action

Bring the real Thyris VM owners into this repository, or replace
`_run_inference` with the agnostic inference seam named in canon. Do not
revisit the import-layout debate.
