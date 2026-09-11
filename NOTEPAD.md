# PAN SDK — Active Notebook

Scratch only; current runtime truth belongs in STATE.md.

## 2026-09-10 nation pillars landed

- Treasury FSM, email/social relays, and master_db CRDT are consumed and
  gate-green with the immune slice.
- EmailSocialNode is explicit+firewall; do not bind it onto DHTNode.
- MasterDatabase shares PANPersistenceStore; do not open a second sqlite.
- PoI still re-executes sha256(canonical({prompt,output})) until real inference.

## Next imperative

Bring Thyris `vm_supervisor` / `memory_system` into this repository so
`telecom/phone_orchestrator.py` can import, or replace
`SovereignInferenceEngine._run_inference` with a real model owner.

Regenerate filetree.md with FileTree Pro when that tool is available.
