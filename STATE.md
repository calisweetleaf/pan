# STATE.md — What Is True Right Now

> Updated 2026-09-09 (Kubuntu lab). Canon lock: `PLAN.md` + `docs/research/Building a Sovereign Digital Nation.md` remain the north star. No core-logic rewrites without Daeron order. This file records runtime truth only.

## What exists

- `sdk/PAN_SDK.py` (2367 lines, monolith) + `sdk/__init__.py`, `sdk_adapter.py`, `API.py`, `API.server.py`, `citizen_simulator.py`, `personal_data.py`, `sovereign_firewall.py`
- `telecom/phone_orchestrator.py`, `telecom/phone_integration.py` (Thyris V1 per whitepaper §2)
- `test/`: `pan_sdk_system_scenario.py` (current version includes personal-data + phone sweep), `test_pan_persistence.py`, `test_pan_manifest.py`, `test_phone_orchestrator.py`
- `tools/pan_viz.py` (tkinter visualizer, stale import path)
- `docs/research/Building a Sovereign Digital Nation.md` (whitepaper, canon)
- `PLAN.md` (operator brain-dump transcript, canon, needs expanding — not replacing)
- `results/pan_sdk_system_test_20251002_005512.txt` (last evidence run, Windows, 2025-10-02)
- `archives/*.zip` (3), empty `reference-code/` (dead weight)

## What is implemented (per last evidence + code reading, not re-verified live)

- SovereignIdentity, DHTNode store, hashchain ledger, PANCitizenRegistry (citizens + apps), PANEconomicEngine (mint/transfer/usage), governance council (members/proposals/votes/finalize), policy registry, constitution articles, name registry — all exercised in scenario Phase 1 and logged.
- Current `test/pan_sdk_system_scenario.py` additionally sweeps personal_data (contacts/messages/calls/prefs) and phone registry — **this sweep has no results evidence yet**.

## What currently passes / fails

- **Gate is RED on Kubuntu, verified 2026-09-09:**
  - `python3 -m py_compile sdk/PAN_SDK.py` → `IndentationError` at `sdk/PAN_SDK.py:1034` (`def load_name_from_db`), caused by `sdk/PAN_SDK.py:1025` (`def persist_name`) sitting at column 0 inside a class body.
  - `import sdk` → same `IndentationError` (via `sdk/__init__.py:4`).
  - `from PAN_SDK import ...` (as tests do) → `ModuleNotFoundError: No module named 'PAN_SDK'` — no top-level `PAN_SDK/` package exists, only `sdk/`.
- **Last Windows run (2025-10-02, `results/...005512.txt`): 6/9 slices verified, 3 mismatched:**
  - VERIFIED: `data_store`, `accounts`, `usage_metrics`, `proposals`, `policies`, `applications`
  - MISMATCH `ledger` — in-memory vs reloaded snapshot differ (exact diff truncated in log, lines 116-117)
  - MISMATCH `pending_transactions` — reloaded entry for `proposal_bond_return` lost nested `data.timestamp` (`2025-10-02T05:55:12.734736+00:00` present in original, absent in reloaded)
  - MISMATCH `citizens` — permissions order only: `["validate","mint_tokens","moderate","governance"]` vs `["validate","governance","mint_tokens","moderate"]` (serialization order, not semantic)
  - Also logged: `Proposal a26a4588-366 not found for voting` (WARNING) then vote recorded + finalized ACCEPTED — governance lookup inconsistency, needs investigation without rewriting logic.
  - That run's snapshot has NO `personal_*` / `phone_addresses` keys — it predates the current test file's personal-data sweep. Old scenario ≠ current scenario.

## What is incomplete

- `SPEC.md`, `MEMORY.md`, `CONTEXT.md`, `BRAINSTORM.md`, `ANTITHESIS.md` do not exist yet.
- `filetree.md` (generated 9/9/2026) does not yet list `STATE.md` / `NOTEPAD.md` — regenerate via extension.
- No `requirements.txt` / `pyproject.toml`; system pip only.
- No Kubuntu results run yet.

## Active frontier

1. Get an honest gate on Kubuntu without touching core logic (needs Daeron decisions below).
2. Expand `PLAN.md` brain-dump into structured notes aligned to the whitepaper — no architecture invention.

## Blocked (needs Daeron order — do NOT freelance)

1. **Syntax blocker:** `sdk/PAN_SDK.py:1025` indent fix. One-line indent, but it unblocks every import — still a code change, awaiting explicit order per canon lock.
2. **Import-layout decision:** tests + `tools/pan_viz.py:12` expect top-level `PAN_SDK`, repo has `sdk/`. Options: rename `sdk/` → `PAN_SDK/`, add shim, or set `PYTHONPATH`. Daeron picks.
3. **Test-compare strictness:** `citizens` order-only mismatch and `pending_transactions` timestamp-drop need a ruling: canonicalize comparisons vs fix serializers. Serializer fixes are logic changes — on hold.

## What changed most recently

- 2026-09-09: `AGENTS.md` §6 filled with real runtime (Python 3.14.4, no venv, pytest present, quirks recorded); Authority root locked to `PLAN.md` + whitepaper; `STATE.md` + `NOTEPAD.md` created. No `sdk/`/`telecom/`/`test/` code touched.

## Next justified action

- Daeron rules on blockers 1–3 above. Until then: docs-only work (expand PLAN notes, draft SPEC outline from whitepaper headings, no code edits).
