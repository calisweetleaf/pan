# PAN SDK — Operator Packet

**Repository:** /home/daeron/LAB/Experiments/projects/pan-sdk
**Classification:** internal research; offline-first, SQLite-backed
**Product thesis:** the Planetary Autonomous Network is a sovereign digital-country substrate. It is not a generic web application, microservice estate, or adapter collection.
**Packet updated:** 2026-09-11
**Current runtime state:** STATE.md

## Authority and entry

1. The operator's current instruction.
2. Live code, tests, and command output.
3. PLAN.md and docs/research/Building a Sovereign Digital Nation.md — locked north-star intent.
4. STATE.md — current, verified runtime state.
5. ANTITHESIS.md — rejected transitions and anti-drift boundaries.
6. security/AGENTS.md and security/rules_of_engagement.md for any security-surface work.
7. CONTEXT.md, MEMORY.md, and NOTEPAD.md — continuity, not a substitute for live truth.
8. filetree.md — generated navigation only.

Read in this order for a code task:

1. This packet and STATE.md.
2. The relevant canon section and ANTITHESIS.md.
3. filetree.md, then the owning source and test.
4. CONTEXT.md / MEMORY.md only when their subsystem or history is relevant.
5. NOTEPAD.md for active hypotheses.

Do not bulk-read the repository or create a plan that assumes an unlocated component exists.

## Architecture: preserve the real seams

- The product follows the production-grade monolith doctrine. Do not split it into microservices, introduce distributed infrastructure, or create folder scaffolding to evade integration.
- Existing production topology is authoritative: PAN_SDK/, telecom/, security/, test/, and tools/. Do not relocate it merely to fit an external template.
- Work directly at the stable owning seam. A wrapper is allowed only when a real external implementation and a narrow, durable adaptation boundary already exist.
- Never create a wrapper, shim, proxy, compatibility layer, parallel implementation, or alternate package merely to avoid editing the owned module. A wrapper that duplicates domain logic is rejected.
- When a direct production edit is justified, use it and preserve provenance. Do not call a thin or incomplete artifact production-ready.
- The control plane may use scoped .cursor/ rules and commands; that is execution infrastructure, not a product-service decomposition.

## Production Python contract — Somnus Code Forge

All changes to PAN_SDK/**/*.py, telecom/**/*.py, security/**/*.py, or tools/**/*.py use the Somnus Code Forge loop.

1. Declare **EDIT**, **COMPOSE**, or **WRAP** before code changes in root SCOPE.md.
   - Default for code already owned by this repository: **EDIT**.
   - **WRAP** requires an explicit source owner, a stable adapter boundary, and no duplicated logic. It is not a shortcut around a direct edit.
   - **COMPOSE** is for a new integrated domain, not an empty scaffold.
2. Change one coherent, consumed unit at a time: a function, class, or tightly coupled repair.
3. Preserve strict typing, provenance docstrings, structured errors, stdlib-first imports, and fail-loud behavior. Do not use mocks or silently weaken tests.
4. Verify at the real consumer boundary with real temporary filesystem/SQLite fixtures where relevant. Distinguish a pre-existing baseline failure from a failure introduced by the change.
5. Before promotion, run the applicable Code Forge checks, record the run artifacts and SOTA_RUN.md ledger, and update snapshot provenance when the task activates that lane.
6. Update STATE.md only when current runtime truth changed; promote durable findings to MEMORY.md, relational changes to CONTEXT.md, and active scratch to NOTEPAD.md.

Do not import a foreign directory layout such as tools/native/ into PAN just to satisfy a generic workflow. Apply Code Forge's quality and provenance semantics to the existing PAN topology.

## Current implementation surface

| Surface | Owner / role |
|---|---|
| PAN_SDK/PAN_SDK.py | PAN monolith: identity, ledger, citizens, economy, governance, policy, persistence |
| PAN_SDK/personal_data.py | local personal-data surface |
| telecom/phone_orchestrator.py | Thyris V1 phone orchestration (blocked on missing VM owners) |
| security/ | defensive sovereignty and ROE-governed security work |
| test/ | direct gate, persistence/name/manifest/personal probes, system scenario |
| reference-code/ | historical lineage; not imported runtime code |
| archives/, results/ | historical evidence; do not rewrite old artifacts |

## Known baseline and decision boundaries

- Package directory is `PAN_SDK/`. That is the consumed import contract, not an open layout debate.
- `python3 test/run_pan_gate.py` is the current verified gate; see STATE.md.
- `telecom/phone_orchestrator.py` still cannot import: Thyris `vm_supervisor` / `memory_system` are absent.
- Historical Windows results are not proof of current behavior.

An agent **may** repair a mechanically demonstrated defect that preserves the existing contract, then prove the consumed path. It must stop and present options before choosing among materially different persistence schemas, protocol/service boundaries, publication, deployment, external communications, credential handling, or destructive operations.

## Verification

The project gate is a direct Python runner (not pytest):

    python3 test/run_pan_gate.py

Optional focused consumers:

    python3 test/test_pan_persistence.py
    python3 test/probe_name_registry.py
    python3 test/test_pan_manifest.py
    python3 test/probe_personal_data.py
    python3 test/pan_sdk_system_scenario.py

A green syntax check is structural evidence only. Do not claim a successful PAN integration without the gate artifact. Never mask a known red baseline with skips, changed assertions, or unreported fallback paths.

## Security and operational boundaries

- Offline-first does not mean secrets can be logged, copied, committed, or transmitted.
- Use environment variables and existing secure mechanisms for secrets. Do not print credentials, keys, or tokens.
- Any work under security/ must read security/AGENTS.md and security/rules_of_engagement.md first.
- Do not expose a service, contact an external system, publish, deploy, purchase, register, or perform destructive work without explicit operator authority.
- results/ is append-only evidence. filetree.md is generated; regenerate it through FileTree Pro after structural change and never hand-edit it.

## Persistent surfaces

| Surface | Owns |
|---|---|
| STATE.md | current runtime truth, blockers, latest verification |
| ANTITHESIS.md | rejected architecture and invalid shortcuts |
| BRAINSTORM.md | non-canonical design exploration and open questions |
| MEMORY.md | durable, source-backed findings |
| CONTEXT.md | compressed retrieval index and system relations |
| NOTEPAD.md | active scratch state; not canon |
| SCOPE.md | active production-code engagement declaration, created when needed |
| SOTA_RUN.md | latest production run ledger, created when a Code Forge run begins |

## Handoff

Before ending a substantive implementation turn:

1. Run the relevant consumer-boundary validation.
2. State exactly what passed, failed, and was not run.
3. Update only the persistent surfaces whose semantic truth changed.
4. Preserve original evidence and unrelated working-tree changes.
5. Leave one imperative next action if a real blocker remains.
