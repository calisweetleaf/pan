# PAN SDK — Current State

**Updated:** 2026-09-18
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
  `THREAT_MEMORY_BULLETIN` packets carrying ROE and neural_activation. Standing
  Erebus towers persist as USMS META nodes coherence-bound to the identity pair.
  Shares run cosine-weighted DAG activation and softmax tower competition.
  NEUTRALIZE without human authorization fails loud. That is Erebus/USMS
  cognition. It does not use `core.prompt_bridge`.
- `security/defensive_offensive_bridge.py` imports the live
  `security.defensive_sovereignty` / `security.reactive_offense` owners and
  writes threat events through `PlanetaryImmuneSystem.share_intelligence`.
  `ThreatDetectionModule.share_threat_intelligence` and
  `NetworkThreatMonitor` detections bind to that same owner.
  `BlockchainThreatIntelligence` construction fails loud; it is not a live store.
- `memory/memory_core.py` and `memory/system_cache.py` are Thyris VM session
  memory. They coexist with USMS in `memory/` and are not the immune DAG.
- `telecom/vm_supervisor.py` and `telecom/vm_image_manager.py` are the VM owners
  `phone_orchestrator` already imported. `ISOConverter._create_disk` is fail-loud
  and has a real qemu-img consumer (`ba05cf4`). `phone_orchestrator` now also
  boots official android-x86 9.0-r2 via `qemu-system-x86_64`. Installer
  media boot (`-nographic` SeaBIOS/ISOLINUX) is still a non-READY proof.
  On this Envy KVM host (`daeron-hpenvyx3602in1laptop15ey0xxx`),
  AUTO_INSTALL=force then disk-boot `SRC=/thyris` with hidden VGA,
  bidirectional serial chardev under `/tmp`, and `VIRT_WIFI=0` proved
  `adb shell echo thyris_adb_health` (`test/thyris_vm/runs/20260918_233451/`).
  Windows nographic/WHPX still failed loud at `console:/ #`. Disk-create
  stays `ISOConverter._create_disk`. AIPC `PromptSystemBridge` is unbound.
  Thyris does not import or require `core.prompt_bridge`.
- Direct project gate: `python test/run_pan_gate.py` (immune, highway,
  treasury, email_social, master_db, thyris_memory, thyris_vm slices).
- `security/planetary_highway.py` is the packet-fabric itinerary. Kinds
  `HIGHWAY_EMBARK` / `HIGHWAY_HOP` / `HIGHWAY_ARRIVE` / `HIGHWAY_LOCATE`.
  Cargo is RSA-sealed to the destination identity. Intermediate hops
  forward the envelope and cannot decrypt. `SovereignFirewall` is required
  and is never constructed on `DHTNode`. This is not a public-internet
  socket plane.
- Historical lineage: reference-code/, archives/, and the 2025-10-02 Windows
  result under results/ (append-only; not rewritten).

## Verified baseline

- **GREEN, 2026-09-18 (Thyris ADB userspace on Envy KVM):** Linux
  `daeron-hpenvyx3602in1laptop15ey0xxx`, Python 3.12 `.venv`, qemu 10.2.1
  `-enable-kvm`, official android-x86_64-9.0-r2.iso SHA-1
  `1cc85b5ed7c830ff71aecf8405c7281a9c995aa0`. Consumer
  `python test/thyris_vm/test_thyris_android_boot.py` 9/9 in 444.7s.
  `HOST_CMD: adb -s 127.0.0.1:44451 shell echo thyris_adb_health` /
  guest `thyris_adb_health`. Android 9. `boot_mode=installed_disk`.
  `phone_ready` true, `adb_proven` true, `vm_state=ready`. Artifact:
  `test/thyris_vm/runs/20260918_233451/`. Snapshot
  `snapshots/v0.17/manifest.json`. Full `run_pan_gate.py` was not re-run
  this unit. Windows nographic remains exhausted, not READY.

- **GREEN, 2026-09-18 (Erebus towers on USMS):** Windows Python 3.14 `.venv`.
  `.\.venv\Scripts\python.exe test\immune\test_planetary_immune_system.py`
  20/20 including `erebus_towers_bind_usms` and
  `erebus_tower_competition_cosine_field` (first activation 0.90 degrade,
  second cosine-pulled 0.62 deceive; L4 still fail-loud). Artifact:
  `test/immune/runs/20260918_010347/`. Snapshot `snapshots/v0.14/manifest.json`.
  Full `run_pan_gate.py` was not re-run this unit. `phone_ready` and
  `adb_proven` stayed false. Identities stayed two types.
- **GREEN, 2026-09-12 (highway + isolation):** Windows Python 3.14.4 `.venv`.
  `python test/highway/test_planetary_highway.py` 10/10
  (`test/highway/runs/20260912_235119/`).
  `python test/immune/test_planetary_immune_system.py` 18/18 including
  SMTP/webhook/feed/whois/deauth fail-loud and no fake operator
  (`test/immune/runs/20260912_235256/`).
  `.\.venv\Scripts\python.exe test/run_pan_gate.py` exited 0 in 37.862s.
  Artifact: `results/pan_gate_20260912_235357.json`. Snapshot
  `snapshots/v0.13/manifest.json`. `phone_ready` and `adb_proven` stayed
  false. Highway is not the next Thyris unit.
- **GREEN, 2026-09-12:** combined `c1bcf6b` tree on a Linux qemu host, plus
  TCG fallback when `/dev/kvm` cannot be opened. `python3 test/run_pan_gate.py`
  exited 0 in 16.853s (immune 12/12 including second-chain retirement;
  thyris_vm disk-create qcow2 1G). `python3 test/thyris_vm/test_thyris_android_boot.py`
  4/4 on qemu 8.2.2 TCG; console showed SeaBIOS plus ISOLINUX 6.03.
  `phone_ready` and `adb_proven` stayed false.
  Artifacts: `results/pan_gate_20260912_094045.json`,
  `test/thyris_vm/runs/20260912_094201/`, `snapshots/v0.12/manifest.json`.
  Windows Python 3.14.4 / QEMU 11.1.0 TCG. Official
  `android-x86_64-9.0-r2.iso` SHA-1
  `1cc85b5ed7c830ff71aecf8405c7281a9c995aa0` matched. Console showed
  SeaBIOS plus ISOLINUX 6.03. Disk came from landed
  `ISOConverter._create_disk`. `phone_ready` and `adb_proven` stayed false.
  Artifacts: `test/thyris_vm/runs/20260912_043438/`,
  `snapshots/v0.11/manifest.json`. Not in `run_pan_gate.py` (ISO is local
  and gitignored). Immune/ROE second-chain retirement was not reopened.
- **GREEN (immune bind), 2026-09-12:** retire in-process second chain
  (`main`, this worker). `python3 test/immune/test_planetary_immune_system.py`
  12/12 including `second_chain_retired_share_uses_immune`.
  `python3 test/run_pan_gate.py` immune slice 12/12; remaining slices PASS
  except `thyris_vm.qemu_img_disk_create` because qemu-img is absent here.
  That qemu miss is a host gap versus origin `ba05cf4`, not an immune
  regression. Identities stayed two types. L4 without human auth still
  fail-loud. Artifacts: `test/immune/runs/20260912_092843/`,
  `test/immune/runs/20260912_092917/`,
  `results/pan_gate_20260912_092909.json`.
- **GREEN, 2026-09-12:** qemu-img disk-create + immune ROE DAG
  `python3 test/run_pan_gate.py` exited 0 in 16.705s on a Linux worker that
  had qemu-img 8.2.2 (`ba05cf4`). `ISOConverter._create_disk` wrote a 1G
  qcow2. Immune 11/11 including ROE persist and L4 deny. This Erebus worker
  does not have those host tools.
  Artifacts: `results/pan_gate_20260912_091538.json`,
  `results/pan_gate_20260912_091538.md`,
  `test/thyris_vm/runs/20260912_091429/`,
  `test/immune/runs/20260912_091516/`.
- **GREEN, 2026-09-11:** finish-prior combined tree merged to main (PR #5).
  `python3 test/run_pan_gate.py` exited 0 in 12.707s on Linux Python 3.12.3
  after merging packet alignment, civic walkthrough, and the inference owner.
  Civic PoI mint now binds PANLIN01 and re-executes `_run_inference`.
  Artifacts: `results/pan_gate_20260911_091651.json`,
  `results/pan_gate_20260911_091651.md`,
  `results/pan_sdk_system_test_20260911_091638.json`.
- **GREEN, 2026-09-11:** `python3 test/run_pan_gate.py` exited 0 in 14.016s on
  Linux Python 3.12.3 after landing the real `_run_inference` owner.
  Artifacts: `results/pan_gate_20260911_085638.json`.
- **GREEN, 2026-09-11 (historical Windows):** `python test/run_pan_gate.py`
  exited 0 in 8.871s on Windows Python 3.14 with `.venv` after unbinding AIPC
  prompt from Thyris. Artifacts: `results/pan_gate_20260911_011502.json`.
  That run still treated `_run_inference` as a placeholder.

## Active frontier

1. Android installer media boots (SeaBIOS/ISOLINUX on `-nographic` stdout)
   remain a non-READY proof. Envy KVM disk-boot ADB userspace is landed
   (`test/thyris_vm/runs/20260918_233451/`, `snapshots/v0.17`). Windows
   TCG/WHPX nographic still died at `console:/ #` without
   `thyris_adb_health`. `create_phone_vm` still launches isolinux livem
   `-nographic`, not the proven AUTO_INSTALL then disk-boot owner.
   Do not dummy READY from ISOLINUX. Do not hop to Trents-Laptop. Do not
   invent a third phone stack.
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
`somnus_erebus/` QWEN tree is not the security packet. Inference owner landed
in snapshots/v0.8. qemu-img disk-create and immune ROE DAG landed in
snapshots/v0.9. Second-chain retirement landed in snapshots/v0.10.
Android-x86 installer boot landed in snapshots/v0.11. KVM-inaccessible TCG
fallback landed in snapshots/v0.12. Highway packet fabric and WAN isolation
landed in snapshots/v0.13. Erebus towers on USMS landed in snapshots/v0.14.
Envy KVM host-guest ADB (`adb shell echo thyris_adb_health`) landed in
snapshots/v0.17.

## Generated-map status

`filetree.md` is operator-owned generated navigation. Continuity-doc turns
must not hand-edit it. Snapshot `v0.14` is a new folder; regenerate filetree
through FileTree Pro.

## Next justified action

Envy KVM proved `PhoneVMState.READY` via host `adb shell echo thyris_adb_health`
(`test/thyris_vm/runs/20260918_233451/`). Stay on this Envy host. Do not
use Trents-Laptop. Trent-Desktop is allowed for other units, not a reason
to hop. `create_phone_vm` still uses isolinux livem `-nographic` rather
than the proven AUTO_INSTALL then disk-boot owner; that bind is the next
Thyris cut if this army continues. Do not dummy READY. Do not pull prompt
files. Do not construct `BlockchainThreatIntelligence`. Do not invent a
third phone stack. Do not reconnect the public internet.
