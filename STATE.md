# PAN SDK — Current State

**Updated:** 2026-09-11
**Canon lock:** PLAN.md and docs/research/Building a Sovereign Digital Nation.md
remain the north-star direction. Do not replace their architecture with an
invented alternative.

## What exists now

- Production topology: `PAN_SDK/`, telecom/, security/, memory/, tools/, and test/.
- `PAN_SDK/PAN_SDK.py` is the central PAN monolith. The package directory is
  named `PAN_SDK` because that is the consumed import contract.
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
  `THREAT_MEMORY_BULLETIN` packets.
- `memory/memory_core.py` and `memory/system_cache.py` are Thyris VM session
  memory. They coexist with USMS in `memory/` and are not the immune DAG.
- `telecom/vm_supervisor.py` and `telecom/vm_image_manager.py` are the VM owners
  `phone_orchestrator` already imported. `core.prompt_bridge` is still absent
  and fails loud.
- Direct project gate: `python test/run_pan_gate.py` (immune, treasury,
  email_social, master_db, thyris_memory, thyris_vm slices).
- Historical lineage: reference-code/, archives/, and the 2025-10-02 Windows
  result under results/ (append-only; not rewritten).

## Verified baseline

- **GREEN, 2026-09-11:** `python test/run_pan_gate.py` exited 0 in 12.820s on
  Windows Python 3.14 with `.venv`. Slices: compile (includes
  `telecom/phone_orchestrator.py`), import, persistence, name_registry,
  manifest, personal_data, system_scenario, planetary_immune_system,
  sovereign_treasury, email_social, master_db, thyris_memory, thyris_vm.
  Artifacts: `results/pan_gate_20260911_004035.json`,
  `results/pan_gate_20260911_004035.md`.
- **GREEN, 2026-09-11:** thyris_memory 3/3
  `test/memory_core/runs/20260911_004047/`.
- **GREEN, 2026-09-11:** thyris_vm 5/5
  `test/thyris_vm/runs/20260911_004047/`.
- **GREEN:** `from telecom.phone_orchestrator import ThyrisPhoneOrchestrator`
  succeeds from repo root. `from memory.memory_core import MemoryManager` and
  `from memory.system_cache import SomnusCache` succeed. USMS remains
  `memory.unified_memory_system.UnifiedMemorySystem`.
- **GREEN, 2026-09-10:** previous nation-pillar gate remains historical evidence
  (`results/pan_gate_20260910_235116.json`); it is not this run.

## Active frontier

1. `core.prompt_bridge` (PromptSystemBridge) is not in this repository.
   VMSupervisor prompt methods raise ImportError. Do not dummy them.
2. `memory/memory_integration.py` still imports `schemas.session`, which is
   absent. Do not scaffold a fake schemas package.
3. QEMU/Android image boot is unproven. Import and construct are proven;
   Thyris VMs do not boot in this gate.
4. Agnostic model inference service. `SovereignInferenceEngine._run_inference`
   is still a placeholder. Treasury PoI re-executes a deterministic commitment
   until that owner exists.
5. Orama dashboard / vector memory spaces named in whitepaper section 6.2.

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

## Generated-map status

`filetree.md` is operator-owned generated navigation. This turn did not
hand-edit it.

## Next justified action

Pull `core.prompt_bridge` as a real owner if VM prompt generation is the next
consumed path, or implement the real `_run_inference` owner so Proof-of-Inference
can leave deterministic commitment re-execution. Do not dummy either gap. Do not
claim QEMU phones boot until qemu-img/qemu-system and Android images are present
and tested.
