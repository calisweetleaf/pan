# PAN SDK — Context Index

Compact retrieval surface for the live repository. It is not a substitute for
source inspection or STATE.md.

## Current authority map

- PLAN.md — operator narrative and directional product intent.
- docs/research/Building a Sovereign Digital Nation.md — sovereign-digital-
  nation and production-monolith direction.
- STATE.md — current verified runtime state and active blockers.
- AGENTS.md — repository entry and execution routing.
- ANTITHESIS.md — rejected transitions and anti-drift boundaries.
- filetree.md — generated navigation map.
- MEMORY.md — durable, chronological findings.
- NOTEPAD.md — current scratch, non-canonical.
- security/AGENTS.md + security/rules_of_engagement.md — security lane.

## 2026-09-10 — Cursor control plane established

**Keys:** Cursor · .cursor/rules · Somnus Code Forge · AGENTS.md ·
SCOPE.md · SOTA_RUN.md

- **State:** Root AGENTS.md is now a PAN-specific execution packet; scoped
  Cursor rules and commands exist under .cursor/.
- **Authority:** AGENTS.md; .cursor/rules/00-pan-control-plane.mdc.
- **Boundary:** The control plane does not alter production Python or resolve
  the known syntax/import-layout blockers.
- **Evidence:** source-only control-plane review; no production code changed.
- **Then inspect:** STATE.md, .cursor/rules/10-python-production.mdc,
  .cursor/commands/implement.md.
- **Open:** regenerate filetree.md through FileTree Pro after this structural
  addition; do not hand-edit the generated map.

## 2026-09-09 — Kubuntu baseline blocked before test collection

**Keys:** PAN_SDK.py · persist_name · load_name_from_db · PAN_SDK import · pytest

- **State:** sdk/PAN_SDK.py has an indentation blocker, and tests expect an
  unlocated top-level PAN_SDK package while runtime code is under sdk/.
- **Authority:** STATE.md.
- **Boundary:** Mechanical syntax repair and package-layout choice are distinct
  work items; historical Windows evidence does not prove present behavior.
- **Evidence:** python3 -m py_compile sdk/PAN_SDK.py; import attempts recorded
  in STATE.md.
- **Then inspect:** sdk/PAN_SDK.py:1025-1034, sdk/__init__.py,
  test/test_pan_persistence.py, tools/pan_viz.py.

## System jump table

| Key | Current meaning | Owner |
|---|---|---|
| PAN monolith | identity, ledger, citizen, economy, governance, policy, persistence | sdk/PAN_SDK.py |
| personal data | local personal records surface | sdk/personal_data.py |
| Thyris V1 | phone orchestration lane | telecom/phone_orchestrator.py |
| security | ROE-governed defensive lane | security/ |
| lineage | non-runtime historical designs | reference-code/, archives/, results/ |

## Active hazards

- syntax-baseline — no current import/test proof until PAN_SDK.py syntax is
  repaired.
- import-layout — do not silently add a package shim, rename sdk/, or mutate
  PYTHONPATH without a justified decision.
- old-results — Windows result is historical evidence, not a current run.
- wrapper-drift — do not use adapters or parallel layouts to evade direct
  integration.
