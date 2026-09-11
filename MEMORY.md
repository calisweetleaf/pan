# PAN SDK — Durable Memory

Append durable, evidence-backed findings here. Preserve corrections as new dated
entries instead of erasing historical truth.

## 2026-09-11 — Continuity packet locked to live owners

**Keys:** AGENTS.md · security/AGENTS.md · .cursor/rules · SCOPE.md

**Status:** LANDED (docs/control plane). No new production-code run.

### Durable findings

- Root AGENTS.md now names Windows workspace `C:\Users\trent\pan`, the
  20260911_011502 gate artifact, nation pillars, Thyris vs USMS split, and
  next action qemu+image or `_run_inference`. `core.prompt_bridge` is rejected
  next-work, not a missing owner to pull.
- `security/AGENTS.md` previously described a `somnus_erebus/` QWEN tree
  (`python_production_doctor.py`, `QWEN.md`, `production_doctor_config.yaml`)
  that is not in this repository. Live consumed owners are
  `security/sovereign_firewall.py` and `security/planetary_immune_system.py`.
  `defensive_sovereignty.py`, `reactive_offense.py`, and
  `defensive_offensive_bridge.py` exist on disk and are unconsumed lineage.
- `.cursor/` rules and commands now route to `python test/run_pan_gate.py`
  plus the immune/treasury/email_social/master_db/thyris_memory/thyris_vm
  consumers. memory/**/*.py is in the Code Forge glob. SCOPE.md is closed.
- Erebus cognition is USMS Ed25519 + PAN RSA packets. It is not in-phone AI.

### Evidence

- Live files: security/*.py listing; test/run_pan_gate.py COMPILE_TARGETS;
  results/pan_gate_20260911_011502.json; STATE.md next-action section.

### Boundary

- Continuity text is not a qemu boot proof and not an inference proof.
- Do not hand-edit filetree.md.

### Retrieval anchors

- AGENTS.md
- security/AGENTS.md
- .cursor/rules/00-pan-control-plane.mdc
- STATE.md
- ANTITHESIS.md

## 2026-09-11 — AIPC prompt_bridge unbound from Thyris telecom

**Keys:** VMSupervisor · ThyrisPhoneOrchestrator · PromptSystemBridge (rejected)
· UnifiedMemorySystem · PlanetaryImmuneSystem

**Status:** LANDED (unbind). QEMU boot is NOT landed.

### Durable findings

- `core.prompt_bridge` / `PromptSystemBridge` was leftover AIPC in-VM prompt
  generation. It was imported only from `telecom.vm_supervisor._load_prompt_bridge`
  and called from `_initialize_prompt_system` / `generate_vm_prompt` /
  `create_ai_computer`. It was not an import-time dependency of
  `phone_orchestrator`, `memory_core`, `system_cache`, USMS, or Erebus.
- Daeron rejected pulling it: Thyris is telecommunications; phones no longer
  have AI inside them. The old VM supervisor was AIPC, not Thyris.
- The fail-loud ImportError was itself the wrong contract: it treated a missing
  AIPC prompt owner as a Thyris blocker. The hook is deleted, not dummy-filled.
- USMS/Erebus did not need it. `security/planetary_immune_system.py` already
  binds Ed25519 `memory.unified_memory_system` to RSA `UnifiedDataPacket`.
  Neither file names prompt_bridge.
- Thyris host-tool fail-loud is `qemu-system-x86_64`, `qemu-img`, `adb`.

### Evidence

- `python test/run_pan_gate.py` exit 0, 8.871s, 2026-09-11
- `results/pan_gate_20260911_011502.json`
- `test/thyris_vm/runs/20260911_011511/result.json` (6/6)
- `snapshots/v0.7/manifest.json`

### Boundary

- Do not pull or invent `core/` prompt files.
- Do not claim Thyris VMs boot.
- Do not collapse USMS into MemoryManager.

### Retrieval anchors

- SCOPE.md
- SOTA_RUN.md
- ANTITHESIS.md (AIPC prompt layer rejected)
- telecom/vm_supervisor.py
- telecom/phone_orchestrator.py
- STATE.md

## 2026-09-11 — Thyris owners landed in memory/ and telecom/

**Keys:** MemoryManager · MemoryConfiguration · SomnusCache · VMSupervisor ·
CustomVMManager · VMImageManager · ThyrisPhoneOrchestrator

**Status:** LANDED (import/construct). QEMU boot is NOT landed.

### Durable findings

- Thyris VM memory is `memory.memory_core` / `memory.system_cache`. Immune
  memory remains `memory.unified_memory_system`. They coexist. A `memory_system`
  package is forbidden.
- `telecom.phone_orchestrator` imports `MemoryManager` from `memory.memory_core`
  and `SomnusCache` from `memory.system_cache`. `CustomVMManager`,
  `CustomNetworkManager`, `VMState`, and `ResourceProfile` live on
  `telecom.vm_supervisor`.
- `core.prompt_bridge` was still absent at import time; dummy PromptSystemBridge
  fallbacks had been removed. That fail-loud-as-blocker stance was later
  rejected (see 2026-09-11 unbind entry above).
- `memory.memory_integration` still needs `schemas.session`. Do not dummy it.
- Offline initialize uses `LocalHashEmbeddingModel` and `SimpleLocalVectorDB`
  when sentence-transformers / chromadb are absent. That is not transformer
  semantic search.

### Evidence

- `python test/run_pan_gate.py` exit 0, 12.820s, 2026-09-11
- `results/pan_gate_20260911_004035.json`
- `test/memory_core/runs/20260911_004047/result.json` (3/3)
- `test/thyris_vm/runs/20260911_004047/result.json` (5/5)

### Boundary

- Do not claim Thyris VMs boot.
- `_run_inference` still a placeholder.

### Retrieval anchors

- SCOPE.md
- SOTA_RUN.md
- memory/memory_core.py
- telecom/vm_supervisor.py
- telecom/phone_orchestrator.py
- STATE.md

## 2026-09-10 — Nation pillars: treasury FSM, email/social relays, CRDT master_db

**Keys:** SovereignTreasury · ProofOfInference · EmailSocialNode · StatelessRelay ·
MasterDatabase · CRDT

**Status:** LANDED

### Durable findings

- Treasury is a rigid FSM, not a contract VM. Forbidden solidity/evm/wasm keys
  fail at submit. Genesis requires three validators. Quorum is `(n+1)//2 + 1`
  (ceil(n/2)+1). Mint requires deterministic PoI re-execution until a real
  `_run_inference` owner exists. `burn_tokens` lives on `PANEconomicEngine`
  so the Fed cannot own a second supply ledger.
- Email/social addresses by `pan:id:<identity_hash>`. Relays verify signatures
  and stay blind. Mail is AES-256-GCM plus RSA-OAEP. `open_sealed` is on
  `SovereignIdentity` because only that object holds the RSA private key.
  `SovereignCommunicator.verify_packet` ignores a False return from
  `verify_signature`; overlay verification uses `verify_overlay_packet` and
  does not trust that helper.
- EmailSocialNode is constructed explicitly with a firewall. Binding it onto
  every DHTNode would open a second sqlite handle and break Windows
  TemporaryDirectory cleanup.
- MasterDatabase LWW documents, G-counters, and OR-sets join through
  PANPersistenceStore. Page hashes skip identical replicas. DHTNode binds it
  on the same connection.

### Evidence

- `python test/run_pan_gate.py` exit 0, 13.515s, 2026-09-10
- `results/pan_gate_20260910_235116.json`
- `test/treasury/runs/20260910_235125/result.json` (5/5)
- `test/email_social/runs/20260910_235128/result.json` (5/5)
- `test/master_db/runs/20260910_235129/result.json` (4/4)
- `verify_sota.py` PASS on treasury.py, email_social.py, master_db.py

### Boundary

- Thyris VM owners still absent.
- `_run_inference` still a placeholder.
- Orama / vector spaces not implemented.
- USMS as a file is not SOTA++ (pre-existing broad Exception handlers).

### Retrieval anchors

- SCOPE.md
- SOTA_RUN.md
- PAN_SDK/treasury.py
- PAN_SDK/email_social.py
- PAN_SDK/master_db.py
- STATE.md

## 2026-09-10 — Planetary immune system: USMS + firewall + PAN bulletins

**Keys:** PlanetaryImmuneSystem · SovereignFirewall · USMS · THREAT_MEMORY_BULLETIN ·
ThreatIntelligenceCoordinator

**Status:** LANDED

### Durable findings

- Gemini's memory keystone is correct in function and wrong in one fact: USMS
  and PAN do **not** share the same `SovereignIdentity` cryptography. USMS is
  Ed25519; PAN is RSA-2048. The immune system binds both and signs bulletins
  twice.
- `ThreatIntelligenceCoordinator` is now `PlanetaryImmuneSystem`. Ephemeral
  `intelligence_database` RAM is gone. Restart recovers EVENT/BELIEF nodes.
- Security owns the firewall at `security/sovereign_firewall.py`. The demo
  `PAN_SDK/sovereign_firewall.py` (print + mock .lacka size string) was deleted,
  not wrapped. inspect_content may compress-then-sign; inspect_packet never
  mutates a signed packet.
- PAN_MESH lane lets threat bulletins name adversaries. EGRESS_LEGACY still
  drops tracker dictionary/regex hits, secret plaintext, and ISP routing keys.
- High-confidence beliefs (>= 0.75) wrap as `THREAT_MEMORY_BULLETIN`, pass the
  firewall, store on DHTNode, and a second node ingests after both signature
  checks.
- Failed countermeasures write a CONTRADICTION-linked EVENT. Three campaign
  vectors quantum-entangle.
- USMS `BinaryStorageManager._atomic_write` used POSIX directory fds. That is
  a mechanical Windows defect (`os.open(dir, O_RDONLY)` -> Permission denied).
  File fsync + `os.replace` is kept; directory fsync is POSIX-only.

### Evidence

- `python test/immune/test_planetary_immune_system.py` 9/9 PASS
- `python test/run_pan_gate.py` exit 0, 6.730s, 2026-09-10
- `test/immune/runs/20260910_225924/result.json`
- `results/pan_gate_20260910_225918.json`
- `verify_sota.py` PASS on firewall and immune modules

### Boundary

- treasury.py / email_social.py / master_db.py landed later the same day;
  see the 2026-09-10 nation-pillars entry.
- USMS as a file is not SOTA++ (pre-existing broad Exception handlers).
- Offensive ROE Level 4 against external hosts was not implemented and is not
  authorized by this landing.

### Retrieval anchors

- SCOPE.md
- SOTA_RUN.md
- security/planetary_immune_system.py
- security/sovereign_firewall.py
- memory/unified_memory_system.py
- test/immune/test_planetary_immune_system.py
- STATE.md

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
