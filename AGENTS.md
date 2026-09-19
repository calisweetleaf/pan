# PAN SDK — Operator Packet

**Repository:** C:\Users\trent\pan (Windows operator workspace). Same product as
the historical Linux path /home/daeron/LAB/Experiments/projects/pan-sdk; that
path is not a second layout.
**Classification:** internal research; offline-first, SQLite-backed
**Product thesis:** the Planetary Autonomous Network is a sovereign digital-country substrate. It is not a generic web application, microservice estate, or adapter collection.
**Packet updated:** 2026-09-12
**Current runtime state:** STATE.md
**Latest verified gate:** results/pan_gate_20260912_235357.json (Windows Python 3.14 `.venv`, exit 0, 37.862s)

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
- Existing production topology is authoritative: PAN_SDK/, telecom/, security/, memory/, test/, and tools/. Do not relocate it merely to fit an external template.
- Work directly at the stable owning seam. A wrapper is allowed only when a real external implementation and a narrow, durable adaptation boundary already exist.
- Never create a wrapper, shim, proxy, compatibility layer, parallel implementation, or alternate package merely to avoid editing the owned module. A wrapper that duplicates domain logic is rejected.
- When a direct production edit is justified, use it and preserve provenance. Do not call a thin or incomplete artifact production-ready.
- The control plane may use scoped .cursor/ rules and commands; that is execution infrastructure, not a product-service decomposition.
- Thyris is telecommunications (phone orchestration, VMs as phones/relays). It is not AIPC. Phones do not contain in-device AI. Do not pull or invent `core.prompt_bridge`.
- USMS (`memory.unified_memory_system`) is the immune Ed25519 DAG. Thyris VM memory is `memory.memory_core` / `memory.system_cache`. They coexist in `memory/`. Do not create a `memory_system` package.
- Nation pillars already exist as consumed owners: `PAN_SDK/treasury.py`, `PAN_SDK/email_social.py`, `PAN_SDK/master_db.py`.

## Production Python contract — Somnus Code Forge

All changes to PAN_SDK/**/*.py, telecom/**/*.py, security/**/*.py, memory/**/*.py, or tools/**/*.py use the Somnus Code Forge loop.

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
| PAN_SDK/PAN_SDK.py | PAN monolith: identity, ledger, citizens, economy, governance, policy, persistence. `SovereignInferenceEngine._run_inference` is the PANLIN01 integer decoder. Civic wire: `docs/CIVIC_INFERENCE_POI.md` |
| PAN_SDK/treasury.py | Fed FSM: PoI mint, quorum execute, contract rejection. Same civic-wire doc |
| PAN_SDK/email_social.py | Nostr-inspired sealed mail / social relays over UnifiedDataPacket |
| PAN_SDK/master_db.py | Offline-first CRDT pool on PANPersistenceStore |
| PAN_SDK/personal_data.py | local personal-data surface |
| memory/unified_memory_system.py | signed Ed25519 memory DAG (USMS; immune-system memory) |
| memory/memory_core.py | Thyris VM MemoryManager / MemoryConfiguration |
| memory/system_cache.py | Thyris SomnusCache |
| memory/memory_integration.py | unconsumed AIPC session-memory leftover; imports absent `schemas.session`. Not a Thyris blocker |
| security/sovereign_firewall.py | fail-closed packet border (security-owned) |
| security/planetary_immune_system.py | USMS EVENT/BELIEF + PAN threat bulletins. Erebus cognition. No prompt_bridge |
| security/planetary_highway.py | Sealed USMS itinerary on UnifiedDataPacket / StatelessRelay. Packet fabric, not immune cognition. Not a second internet |
| security/defensive_sovereignty.py, reactive_offense.py, defensive_offensive_bridge.py | compile + immune-imported lineage. WAN SMTP/webhook/feeds/whois/deauth fail loud. Live immune path is planetary_immune_system.py |
| telecom/vm_supervisor.py | VMSupervisor, CustomVMManager, CustomNetworkManager, VMState, ResourceProfile. AIPC prompt hook unbound |
| telecom/vm_image_manager.py | VMImageManager, OSFamily |
| telecom/phone_orchestrator.py | Thyris V1 phone orchestration; android-x86 installer boot proven via `-nographic` SeaBIOS/ISOLINUX. Envy KVM disk-boot ADB userspace proven (`adb shell echo thyris_adb_health`, snapshots/v0.17). Windows nographic still unproven. |
| telecom/phone_integration.py | browser APK/VNC bridge; not a gate compile target; create_phone_vm still uses livem nographic, not the proven disk-boot ADB owner |
| security/ | defensive sovereignty and ROE-governed security work; see security/AGENTS.md |
| test/ | direct gate, persistence/name/manifest/personal probes, immune/highway/treasury/email_social/master_db/thyris_memory/thyris_vm consumers, system scenario |
| reference-code/ | historical lineage; not imported runtime code |
| archives/, results/ | historical evidence; do not rewrite old artifacts |

## Known baseline and decision boundaries

- Package directory is `PAN_SDK/`. That is the consumed import contract, not an open layout debate.
- `python test/run_pan_gate.py` is the current verified Windows gate; see STATE.md. It includes immune, highway, treasury, email_social, master_db, thyris_memory, and thyris_vm slices. POSIX spelling is `python3 test/run_pan_gate.py`.
- Security owns `security/sovereign_firewall.py`. PAN RSA identity and USMS Ed25519 identity are bound, not collapsed.
- Thyris VM memory (`memory.memory_core`) and USMS (`memory.unified_memory_system`) coexist in `memory/` and must not be collapsed. Do not create a `memory_system` package.
- `telecom/phone_orchestrator.py` imports. Android-x86 9.0-r2 installer boot is proven via `-nographic` ISOLINUX on this Windows host; the ISO is gitignored and is not in the project gate. `PhoneVMState.READY` / ADB remain unproven. AIPC `core.prompt_bridge` is rejected for Thyris telecom (phones have no in-device AI). Do not list prompt_bridge as next work. Do not duplicate `ISOConverter._create_disk`. Do not redo `BlockchainThreatIntelligence` retirement (`32ea3a9`).
- The stale `somnus_erebus/` / QWEN.md tree described in older security notes is not this repository's layout. Live security owners are in security/AGENTS.md.
- Historical 2025-10-02 Windows results remain historical evidence only. The 2026-09-12 Windows gate (`results/pan_gate_20260912_235357.json`) is current.

An agent **may** repair a mechanically demonstrated defect that preserves the existing contract, then prove the consumed path. It must stop and present options before choosing among materially different persistence schemas, protocol/service boundaries, publication, deployment, external communications, credential handling, or destructive operations.

## Verification

The project gate is a direct Python runner (not pytest). Latest verified Windows command:

    python test/run_pan_gate.py

POSIX equivalent: `python3 test/run_pan_gate.py`.

Optional focused consumers:

    python test/test_pan_persistence.py
    python test/probe_name_registry.py
    python test/test_pan_manifest.py
    python test/probe_personal_data.py
    python test/pan_sdk_system_scenario.py
    python test/immune/test_planetary_immune_system.py
    python test/highway/test_planetary_highway.py
    python test/treasury/test_sovereign_treasury.py
    python test/email_social/test_email_social.py
    python test/master_db/test_master_db.py
    python test/memory_core/test_memory_core.py
    python test/thyris_vm/test_thyris_vm.py
    python test/thyris_vm/test_thyris_android_boot.py

A green syntax check is structural evidence only. Do not claim a successful PAN integration without the gate artifact. Never mask a known red baseline with skips, changed assertions, or unreported fallback paths.

## Next justified action

Envy KVM proved `PhoneVMState.READY` after host `adb shell echo thyris_adb_health`
(`test/thyris_vm/runs/20260918_233451/`, snapshots/v0.17). Stay on this Envy
host. Do not use Trents-Laptop. Trent-Desktop is allowed for other units, not
a reason to hop. Disk-create is already landed (`ba05cf4`). Android-x86 9.0-r2
installer boot is already landed (ISOLINUX on `-nographic` stdout).
`BlockchainThreatIntelligence` construction is already retired (`32ea3a9`).
Do not open a second `qemu-img create` owner. Do not reopen the second threat
chain. `create_phone_vm` still launches isolinux livem `-nographic` rather
than the proven AUTO_INSTALL then disk-boot owner.

Do not pull or invent `core.prompt_bridge`. Do not dummy `_run_inference` (that owner is landed; see `docs/CIVIC_INFERENCE_POI.md`). Do not claim READY phones from ISOLINUX installer evidence. Do not open a second civic wire or reconnect the public internet. `schemas.session` / `memory.memory_integration` is leftover AIPC session-memory and is not a Thyris blocker.

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
5. Leave one imperative next action if a real blocker remains. Civic inference is landed (`docs/CIVIC_INFERENCE_POI.md`). Remaining host-tool frontier is ADB / `PhoneVMState.READY`. Never `prompt_bridge`.
