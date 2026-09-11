# PAN SDK — Current State

**Updated:** 2026-09-10
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
- Direct project gate: `python test/run_pan_gate.py` (immune, treasury,
  email_social, master_db slices).
- Historical lineage: reference-code/, archives/, and the 2025-10-02 Windows
  result under results/ (append-only; not rewritten).

## Verified baseline

- **GREEN, 2026-09-10:** `python test/run_pan_gate.py` exited 0 in 13.515s on
  Windows Python 3.14.4. Slices: compile, import, persistence, name_registry,
  manifest, personal_data, system_scenario, planetary_immune_system,
  sovereign_treasury, email_social, master_db. Artifacts:
  `results/pan_gate_20260910_235116.json`,
  `results/pan_gate_20260910_235116.md`.
- **GREEN, 2026-09-10:** treasury 5/5
  `test/treasury/runs/20260910_235125/`.
- **GREEN, 2026-09-10:** email_social 5/5
  `test/email_social/runs/20260910_235128/`.
- **GREEN, 2026-09-10:** master_db 4/4
  `test/master_db/runs/20260910_235129/`.
- **GREEN, 2026-09-10:** immune 9/9 (gate slice)
  `test/immune/runs/20260910_235124/`.
- **GREEN:** `from PAN_SDK import DHTNode, PANNameRegistry, PANPersistenceStore,
  SovereignTreasury, EmailSocialNode, MasterDatabase` succeeds from repo root.
- **SKIPPED (named, not hidden):** compile of
  `telecom/phone_orchestrator.py` — missing Thyris `vm_supervisor` /
  `memory_system` owners.

## Active frontier

1. Thyris phone VM owners (`vm_supervisor`, `memory_system`) so
   `telecom/phone_orchestrator.py` can import without dummies.
2. Agnostic model inference service. `SovereignInferenceEngine._run_inference`
  is still a placeholder. Treasury PoI re-executes a deterministic commitment
  until that owner exists.
3. Orama dashboard / vector memory spaces named in whitepaper section 6.2.
4. Regenerate `filetree.md` with FileTree Pro after the pillar additions.
   Do not hand-edit it.

## Known decision boundaries

- Package layout `PAN_SDK/` is resolved by the consumed contract. Do not re-open
  it with a shim, PYTHONPATH hack, or second package.
- PAN `SovereignIdentity` (RSA) and USMS `SovereignIdentity` (Ed25519) are
  different cryptography. The immune system binds them; do not collapse them
  into one class without a new evidence-backed decision.
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

`filetree.md` is structurally stale (still shows `sdk/`, omits `.cursor/`,
SCOPE.md, SOTA_RUN.md, probes, memory/, security firewall move, treasury,
email_social, master_db). Regenerate with FileTree Pro.

## Next justified action

Bring Thyris `vm_supervisor` / `memory_system` owners into this repository so
`telecom/phone_orchestrator.py` can import, or implement the real
`_run_inference` owner so Proof-of-Inference can leave deterministic
commitment re-execution. Do not invent a microservice around either gap.
