# NOTEPAD.md — External Working Memory (scratch, not canon)

> 2026-09-09 setup session. Canon: PLAN.md + whitepaper. No core-logic rewrites. Code untouched this session.

## Current hypotheses

- `results/...005512.txt` mismatches are canonicalization/serializer asymmetries, not consensus failure: citizens = order-only; pending_transactions = nested timestamp dropped on reload; ledger = snapshot-source difference (in-memory vs persisted component). Needs diff with canonical JSON to confirm, not a rewrite.
- `sdk/PAN_SDK.py:1025` looks like a dedent typo (`def persist_name` at col 0, body indented as method). `py_compile` points at 1034 but root is 1025. One-indent fix would green the syntax gate — HELD for operator order.
- Import mismatch (`PAN_SDK` vs `sdk/`) suggests repo was renamed or extracted from a zip (`archives/*.zip`?) without updating imports. Check zip contents before proposing rename — read-only `unzip -l`, no extraction yet.

## Evidence pointers

- Syntax: `sdk/PAN_SDK.py:1025-1034`, `sdk/__init__.py:4`
- Imports: `test/pan_sdk_system_scenario.py:11-27`, `test/test_pan_persistence.py:9-17`, `tools/pan_viz.py:11-16`
- Results: `results/pan_sdk_system_test_20251002_005512.txt:114-128` (mismatches), `:49` (proposal-not-found warning), `:63-108` (snapshot has no personal_* keys vs current test file which does)
- Runtime: `python3 --version` → 3.14.4, no `.venv`, pytest 9.0.2 / crypto 46.0.5 / psutil 7.1.0 present; `git log` = single commit `03b46df`
- Whitepaper anchors: §1 monolith doctrine, §2 Thyris V1→V2 + hotswap, §4 treasury.py FSM + Fed Chair, §5 email_social.py Nostr-overlay, §6 CRDT SQLite pooling

## Dead ends / do-not-do

- Do NOT "fix" tests by loosening asserts silently, do NOT reformat serializers, do NOT rename `sdk/` — all need Daeron call.
- Do NOT hand-edit `filetree.md` (generated). Regenerate via extension after STATE/NOTEPAD land.
- Do NOT rewrite old `results/*.txt` — append-only evidence.

## Candidate next moves (smallest first, docs-only until unblocked)

1. `unzip -l archives/*.zip` (read-only) — see if a top-level `PAN_SDK/` layout lived there; informs import decision.
2. Diff current `test/pan_sdk_system_scenario.py` vs the version that produced the 2025-10-02 log (git? only 1 commit — so diff = personal-sweep additions). List which snapshot keys are new.
3. Draft SPEC outline mirroring whitepaper §§1-7 with pointers to current `sdk/` symbols — headings + file:line only, no behavior invention.
4. After Daeron orders indent fix + import ruling: `py_compile` → focused pytest → full scenario → new `results/` run on Kubuntu.
5. Then distill durable bits → MEMORY.md / CONTEXT.md.

## Reminders

- Leave `sdk/`, `telecom/`, `test/`, `tools/` untouched until operator orders.
- `filetree.md` now stale (missing STATE.md/NOTEPAD.md) — regeneration needed, not hand-edit.
- Handoff line: awaiting Daeron ruling on STATE.md blockers 1-3.
