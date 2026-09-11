# PAN SDK — Durable Memory

Append durable, evidence-backed findings here. Preserve corrections as new dated
entries instead of erasing historical truth.

## 2026-09-11 — Package rename, name kv persistence, direct gate

**Keys:** PAN_SDK · persist_name · store_name · name_registry · run_pan_gate.py ·
sdk_adapter

**Status:** LANDED

### Durable findings

- Every consumer already imported `PAN_SDK`. Renaming `sdk/` to `PAN_SDK/`
  matched the filesystem to that contract. A shim/PYTHONPATH proxy remains
  banned.
- `PANNameRegistry.persist_name` belongs on the class. Name records persist via
  existing `kv_state` component `name_registry`, not a new table.
- `DHTNode._hydrate_from_persistence` must call `name_registry.hydrate_from_persistence`
  the same way it hydrates economy/governance/citizens.
- `PANPersonalDataStore` wrote messages and call logs to sqlite but did not
  reload them into memory; hydrate now loads those tables.
- Unused `sdk_adapter.py` was a forbidden identity wrapper. Deleted.
- Project verification is `python3 test/run_pan_gate.py`. Pytest is not the
  gate.

### Evidence

- `python3 test/run_pan_gate.py` exit 0, 2026-09-11, 2.037s.
- `results/pan_gate_20260911_030722.json`
- `results/pan_sdk_system_test_20260911_030723.txt`

### Boundary

- Green civic persistence is not Thyris VM proof and not inference proof.
- filetree.md is generated and now stale.

### Retrieval anchors

- SCOPE.md
- SOTA_RUN.md
- PAN_SDK/PAN_SDK.py
- test/run_pan_gate.py
- STATE.md

## 2026-09-10 — Cursor-native PAN execution control plane

**Keys:** Cursor · .cursor/rules · Somnus Code Forge · direct edit ·
wrapper-drift · SCOPE.md · SOTA_RUN.md

**Status:** LANDED

### Durable findings

- PAN now has a version-controlled Cursor control plane:
  .cursor/rules/00-pan-control-plane.mdc,
  10-python-production.mdc, 20-security.mdc, and
  30-state-and-provenance.mdc, plus recover/implement/verify/handoff commands.
- The root AGENTS.md was reduced from a generic template into a project packet
  that routes Cursor to current state, canon, known blockers, verification, and
  stop conditions.
- Code Forge quality is applied to PAN's existing sdk/, telecom/, security/,
  and tools/ topology. It does not authorize relocating source into a generic
  external layout.
- Existing repository-owned code defaults to EDIT. WRAP requires a concrete
  external owner and stable adaptation seam; wrappers cannot duplicate domain
  logic or avoid an appropriate direct edit.

### Evidence

- .cursor/ was previously present but empty; project rules and commands are now
  tracked control-plane files.
- AGENTS.md now names the active current-state source and concrete validation
  commands.
- No production Python, tests, archives, or historical results were changed.

### Boundary

- This establishes agent execution discipline, not a green PAN runtime.
- The existing syntax blocker and sdk/ versus PAN_SDK package-layout decision
  remain governed by STATE.md.
- filetree.md is generated and must be regenerated through FileTree Pro to
  reflect the new .cursor/ contents and new root documentation.

### Retrieval anchors

- AGENTS.md
- .cursor/rules/10-python-production.mdc
- .cursor/commands/implement.md
- STATE.md
- ANTITHESIS.md

## 2026-09-09 — Kubuntu baseline and canon lock

**Keys:** PAN_SDK.py · persist_name · load_name_from_db · sdk · PAN_SDK · Kubuntu

**Status:** VERIFIED

### Durable findings

- PLAN.md and docs/research/Building a Sovereign Digital Nation.md are the
  directional canon; do not rewrite core logic to fit invented replacement
  architecture.
- sdk/PAN_SDK.py is syntactically blocked around the persist_name /
  load_name_from_db boundary. This prevents import and test collection.
- Tests and tools/pan_viz.py expect a top-level PAN_SDK import while the
  present source layout is sdk/; that choice has material compatibility
  consequences.

### Evidence

- STATE.md records the exact command failures and historical Windows scenario
  limitations.

### Boundary

- A compilation fix is not proof of end-to-end persistence or telecom behavior.
- Historical result logs remain append-only evidence and do not prove current
  Kubuntu behavior.
