# PAN SDK — Active Notebook

Scratch only; current runtime truth belongs in STATE.md.

## 2026-09-11 first-run unblock landed

- `sdk/` renamed to `PAN_SDK/`. Import contract matches filesystem.
- `persist_name` is a `PANNameRegistry` method. `store_name`/`get_name` live on
  `PANPersistenceStore` kv component `name_registry`.
- Gate is `python3 test/run_pan_gate.py`. Last run PASS 20260911_030722.
- `sdk_adapter.py` deleted. pytest phone orchestrator mock theater removed.

## Next imperative

Do not reopen package layout. Next real seam is either:

1. Thyris VM owners so `telecom/phone_orchestrator.py` can import, or
2. the agnostic inference replacement for `_run_inference`.

Regenerate filetree.md with FileTree Pro when that tool is available.
