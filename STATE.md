# PAN SDK — Current State

**Updated:** 2026-09-11
**Canon lock:** PLAN.md and docs/research/Building a Sovereign Digital Nation.md
remain the north-star direction. Do not replace their architecture with an
invented alternative.

## What exists now

- Production topology: `PAN_SDK/`, telecom/, security/, memory/, tools/, and test/.
- `PAN_SDK/PAN_SDK.py` is the central PAN monolith. The package directory is
  named `PAN_SDK` because that is the consumed import contract.
  `SovereignInferenceEngine._run_inference` loads PANLIN01 integer weights and
  runs a deterministic in-process decode. Treasury PoI re-executes that owner.
- `PAN_SDK/treasury.py` is the federal-reserve FSM. Mint/burn/distribute land on
  `PANEconomicEngine`. DHTNode binds `SovereignTreasury`.
- `PAN_SDK/email_social.py` is the Nostr-inspired overlay. Identity hash is the
  address. Relays are blind. The security-owned firewall inspects before send.
- `PAN_SDK/master_db.py` is the offline-first CRDT pool on `PANPersistenceStore`.
  DHTNode binds `MasterDatabase` on the same sqlite connection.
- Name registrations persist through `PANPersistenceStore` kv component
  `name_registry` (`store_name` / `get_name`) and hydrate on `PANNameRegistry`
  / `DHTNode`.
- Security owns the packet border: `security/sovereign_firewall.py`.
- `security/planetary_immune_system.py` binds USMS (Ed25519 memory DAG) to PAN
  DHT/`UnifiedDataPacket` (RSA transport). High-confidence beliefs broadcast as
  `THREAT_MEMORY_BULLETIN` packets. That is Erebus/USMS cognition. It does not
  use `core.prompt_bridge`.
- `memory/memory_core.py` and `memory/system_cache.py` are Thyris VM session
  memory. They coexist with USMS in `memory/` and are not the immune DAG.
- `telecom/vm_supervisor.py` and `telecom/vm_image_manager.py` are the VM owners
  `phone_orchestrator` already imported. AIPC `PromptSystemBridge` is unbound.
  Thyris does not import or require `core.prompt_bridge`.
- Direct project gate: `python test/run_pan_gate.py` (immune, treasury,
  email_social, master_db, thyris_memory, thyris_vm slices).
- Historical lineage: reference-code/, archives/, and the 2025-10-02 Windows
  result under results/ (append-only; not rewritten).

## Verified baseline

- **GREEN, 2026-09-11:** finish-prior combined tree
  (`cursor/finish-prior-wave-d5ba`, PR #5, not merged to main).
  `python3 test/run_pan_gate.py` exited 0 in 12.707s on Linux Python 3.12.3
  after merging packet alignment, civic walkthrough, and the inference owner.
  Civic PoI mint now binds PANLIN01 and re-executes `_run_inference`.
  Artifacts: `results/pan_gate_20260911_091651.json`,
  `results/pan_gate_20260911_091651.md`,
  `results/pan_sdk_system_test_20260911_091638.json`.
- **GREEN, 2026-09-11:** `python3 test/run_pan_gate.py` exited 0 in 14.016s on
  Linux Python 3.12.3 after landing the real `_run_inference` owner. Slices:
  compile, import, persistence, name_registry, manifest, personal_data,
  system_scenario, planetary_immune_system, sovereign_treasury (7/7 including
  forged-output reject), email_social, master_db, thyris_memory, thyris_vm.
  Artifacts: `results/pan_gate_20260911_085638.json`,
  `results/pan_gate_20260911_085638.md`.
- **GREEN, 2026-09-11:** inference consumer 7/7
  `test/inference/runs/20260911_085509/`.
- **GREEN, 2026-09-11:** treasury consumer 7/7
  `test/treasury/runs/20260911_085523/` (focused) and
  `test/treasury/runs/20260911_085647/` (gate slice).
- **GREEN, 2026-09-11 (historical Windows):** `python test/run_pan_gate.py`
  exited 0 in 8.871s on Windows Python 3.14 with `.venv` after unbinding AIPC
  prompt from Thyris. Artifacts: `results/pan_gate_20260911_011502.json`.
  That run still treated `_run_inference` as a placeholder.

## Active frontier

1. QEMU/Android image boot is unproven. Host-tool contract names
   `qemu-system-x86_64`, `qemu-img`, and `adb`. This Linux gate found all three
   missing. Import and construct are proven; Thyris VMs do not boot in this gate.
2. `memory/memory_integration.py` still imports `schemas.session`, which is
   absent. That is leftover AIPC session-memory, not a Thyris telecom
   requirement. Do not scaffold a fake schemas package.
3. `PAN_SDK/API.server.py` `_run_inference_async` is still an unconsumed
   sleep-and-string subclass. It is not the inference owner.
4. Orama dashboard / vector memory spaces named in whitepaper section 6.2.

## Known decision boundaries

- Package layout `PAN_SDK/` is resolved by the consumed contract. Do not re-open
  it with a shim, PYTHONPATH hack, or second package.
- PAN `SovereignIdentity` (RSA) and USMS `SovereignIdentity` (Ed25519) are
  different cryptography. The immune system binds them; do not collapse them
  into one class without a new evidence-backed decision.
- Thyris `MemoryManager` is not USMS. Do not create `memory_system` and do not
  wrap USMS to look like MemoryManager.
- Email/social is not auto-bound onto every DHTNode: a per-node firewall sqlite
  handle would leak on Windows TemporaryDirectory cleanup. Construct
  `EmailSocialNode` with an explicit `SovereignFirewall`.
- Master_db must keep using `PANPersistenceStore`. Do not open a second sqlite
  engine for the CRDT pool.
- Cursor must still present evidence before selecting a new persistence
  schema, protocol/service boundary, deployment, publication, or external-action
  direction.
- Do not add a wrapper, proxy package, or parallel implementation merely to bypass
  a direct integration.
- Ephemeral in-process threat-intelligence dictionaries are rejected. USMS is
  the local cognitive substrate; PAN packets are the mesh.
- Do not pull or invent `core.prompt_bridge`. Thyris is telecommunications.
  Phones do not contain in-device AI. USMS/Erebus already own cognition.

## Control-plane packet

Root AGENTS.md, security/AGENTS.md, and `.cursor/` rules/commands were
reconciled to the Thyris unbind baseline on 2026-09-11. The stale
`somnus_erebus/` QWEN tree is no longer the security packet. The inference
owner landed in snapshots/v0.8; next justified action is qemu
host-tools/images, not `prompt_bridge`.

## Generated-map status

`filetree.md` is operator-owned generated navigation. Continuity-doc turns
must not hand-edit it.

## Next justified action

Prove the Thyris host-tool path: install or locate `qemu-img` and
`qemu-system-x86_64`, obtain an Android image, and run a real disk-create
consumer. Do not claim phones boot until those tools and images are present
and tested. Do not pull prompt files. Do not add a second inference engine
in `API.server.py`.
