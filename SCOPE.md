# SCOPE — PAN first-run runtime unblock

**Mode:** EDIT
**Packet:** make the live PAN SDK import, persist civic state, reload it, and fail loud
**Date:** 2026-09-11

## Targets

| Target | Owner | Consumed boundary |
|---|---|---|
| `sdk/` → `PAN_SDK/` | package layout already claimed by every consumer | `from PAN_SDK import ...`, `from PAN_SDK.PAN_SDK import ...`, `from PAN_SDK.personal_data import ...` |
| `PAN_SDK/PAN_SDK.py` | `PANPersistenceStore`, `PANNameRegistry`, `DHTNode` | name register → kv `name_registry` → hydrate after reopen |
| `PAN_SDK/personal_data.py` | `PANPersonalDataStore` | contacts, messages, call logs, preferences reload from sqlite |
| `test/run_pan_gate.py` | project gate | real tempdir/SQLite consumers, JSON + Markdown artifacts |

## Direct-edit justification

The consumed import contract is already `PAN_SDK`. The folder name `sdk/` is the defect. Renaming the owned package is a direct edit of the live topology, not a shim, PYTHONPATH hack, or proxy package.

`persist_name` / `load_name_from_db` already call `store_name` / `get_name`. Those methods are missing. Civic engines already persist through `kv_state`. Completing `name_registry` on that store is the same seam, not a new persistence architecture.

`PAN_SDK/sdk_adapter.py` is an unreferenced identity wrapper plus fake API keys. It duplicates `SovereignIdentity` and is the wrapper grammar this repository forbids. It is deleted, not repaired.

## WRAP (existing, unchanged)

`PAN_SDK/API.py` remains the importlib loader for `API.server.py` because a module filename containing a dot is a real import-boundary constraint. It must not grow domain logic.

## Out of scope

- Thyris QEMU / `vm_supervisor` / `memory_system`
- Agnostic model inference service
- Rewriting `PLAN.md`
- `security/` lane
- Rewriting historical `results/pan_sdk_system_test_20251002_005512.txt`
