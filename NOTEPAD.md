# PAN SDK — Active Notebook

Scratch only; current runtime truth belongs in STATE.md.

## 2026-09-18 dispatch v1.2 — WHPX and AUTO_INSTALL FAIL (not READY)

Crowd-internal: [docs/NATION_DISPATCH.md](docs/NATION_DISPATCH.md) v1.2 and
[docs/NATION_DISPATCH_SHORT.md](docs/NATION_DISPATCH_SHORT.md). Unpublished.
No X post. v1.1 in-flight WHPX/qcow paragraph is expired.

- B WHPX livem FAIL: `test/thyris_vm/runs/20260918_050641/` 7/8, 571.3s.
  `-accel whpx,kernel-irqchip=off`. ISOLINUX pass. Detecting `/dev/sr0`
  then `console:/ #`. QEMU rc=`4294967295`. `phone_ready=false`.
  `adb_proven=false`.
- D AUTO_INSTALL=force then disk boot FAIL:
  `test/thyris_vm/runs/20260918_052020/` 7/8, 1428.4s. Install
  Congratulations on sda1 (8G qcow). Disk boot `found at /dev/sda1`
  then the same `console:/ #`. No `thyris_adb_health`.
- Wall: android-x86 9.0-r2 ramdisk init on `-nographic` serial presents
  `console:/ #` (live sr0 AND installed sda1) and never proves TCP adbd.
- Do not flip READY. Do not name a next accelerator. `snapshots/v0.15`
  is not a READY landing.

## 2026-09-18 Thyris ADB READY (still false)

- Option A TCG livem+nosetup exhausted: 20260918_032455 / 20260918_035525.
- Option B WHPX: 20260918_050641. `-accel whpx,kernel-irqchip=off`.
  ISOLINUX pass. Stuck at Detecting /dev/sr0 then `console:/ #`.
  adb_proven false.
- Option D AUTO_INSTALL=force then disk boot: 20260918_052020.
  Install markers Formatting / Installing / Syncing / Congratulations.
  Disk boot found at /dev/sda1 then `console:/ #`. No thyris_adb_health.
- Wall: after "found at", this ISO's ramdisk init presents `console:/ #`
  on -nographic serial and never proves TCP adbd. Do not dummy READY.
  Do not invent a next accel.

## 2026-09-18 Erebus towers

- Landed standing towers + cosine competition at planetary_immune_system.py.
  Immune 20/20 `test/immune/runs/20260918_010347/`. Gate not re-run.
- reference-code MTL/NMCA not imported. Hash embedding ported locally.
- Next at this owner: none required. Next repo action remains ADB userspace.
  Do not wrap defensive_sovereignty. Do not expand bulletin with tower
  allocations without a new protocol decision.

## 2026-09-12 KVM inaccessible → TCG

- `select_qemu_accelerator` now opens `/dev/kvm` before `-enable-kvm`.
  This Linux worker's kvm node exists but is Permission denied; TCG still
  showed ISOLINUX. Did not dummy READY/ADB. Did not redo disk-create/ROE/
  installer-boot design.
- Combined gate 20260912_094045 green 16.853s. Boot 20260912_094201 4/4.

## 2026-09-12 Android-x86 installer boot


- Pulled origin/main `32ea3a9` (immune second-chain retirement). Did not
  touch `security/` or redo ROE/`BlockchainThreatIntelligence`.
- Declared EDIT in SCOPE.md engagement 4. Disk-create stays
  `ISOConverter._create_disk` (`ba05cf4`). Snapshot is v0.11 because v0.10
  is the immune unit.
- Legal ISO: `android_images/android-x86_64-9.0-r2.iso`, SHA-1 matched,
  gitignored.
- Windows QEMU 11.1.0 TCG. `-nographic` stdout showed SeaBIOS + ISOLINUX
  6.03. Consumer 20260912_043438 4/4. `phone_ready` false, `adb_proven`
  false. Not in `run_pan_gate.py`.
- Next: ADB userspace / PhoneVMState.READY. Do not open a second
  disk-create chain. Do not reopen the retired second threat chain.

## 2026-09-12 retire second chain

- Rebased onto origin/main `ba05cf4`. Discarded uncommitted mesh-strand /
  usms_linkage work so those trails were not invented.
- EDIT: BlockchainThreatIntelligence construction fails loud; detector and
  monitor bind PlanetaryImmuneSystem. Immune 12/12. Gate FAIL only qemu-img
  missing on this worker.
- Next: qemu worker / Android image / adb. Do not dummy inference. Do not
  publish.

## 2026-09-12 qemu disk-create + ROE DAG


- Declared EDIT in SCOPE.md. qemu-img 8.2.2 and qemu-system-x86_64 installed
  on this Linux worker. `ISOConverter._create_disk` fail-loud. Consumer wrote
  probe.qcow2 (196624 bytes, virtual 1G). adb still missing. No Android ISO.
  Phones not booted.
- Immune: ROE flags on USMS BELIEF; bridge MEDIUM → deceive persisted across
  reopen; L4 deny without human auth. D/O package imports now
  `security.defensive_sovereignty` / `security.reactive_offense`.
- Gate 20260912_091538 green 16.705s. Snapshot v0.9.
- `core-directive.md` not found in repo. Colony Erebus trail claimed mesh-strand
  / usms_linkage work that is not in this working tree.
- Next: Android image + adb, or retire BlockchainThreatIntelligence.

## 2026-09-11 continuity packet lock

- Operator packet, security/AGENTS.md, and `.cursor/` now match live owners.
- Killed stale claims: somnus_erebus/QWEN doctor tree as live security layout;
  prompt_bridge as next action; memory_system as a missing package; AIPC
  in-phone AI as Thyris.
- SCOPE.md closed on the unbind unit. Do not reopen it to pull prompt files.
- Next imperative remains qemu host tools + Android image, or real
  `_run_inference`. schemas.session is leftover AIPC session-memory and is
  not a Thyris blocker.

## 2026-09-11 AIPC prompt unbound from Thyris

- Daeron: phones no longer have AI inside them. Thyris is telecommunications.
  Old VM supervisor prompt hook was AIPC, not Thyris. Do not pull
  `core.prompt_bridge`. Do not invent an Erebus prompt layer.
- Removed `_load_prompt_bridge`, `_initialize_prompt_system`,
  `generate_vm_prompt`, `_vm_prompt_systems` from `telecom/vm_supervisor.py`.
- Phone orchestrator host-tool contract is qemu-system / qemu-img / adb.
- USMS + planetary_immune_system have no prompt_bridge; they already bind
  Ed25519 USMS to RSA PAN packets.
- Gate 20260911_011502 green. QEMU boot was not attempted.
- Remaining foreign owner with evidence: `schemas.session` from
  `memory.memory_integration` (unconsumed AIPC session memory).

## Next imperative

ADB userspace / `PhoneVMState.READY` is blocked on this Windows
`-nographic` host. TCG live, WHPX livem (`20260918_050641`), and
AUTO_INSTALL-then-disk (`20260918_052020`) all stop at `console:/ #`
without TCP adbd. Do not dummy READY. Do not name a next accelerator
here. Do not pull prompt files. Do not post the dispatch.
