# SCOPE — closed: Android-x86 installer boot

**Status:** CLOSED 2026-09-12 after `test/thyris_vm/test_thyris_android_boot.py` 4/4
on `32ea3a9`.
**Ledger:** SOTA_RUN.md
**Snapshot:** snapshots/v0.11/manifest.json
**Prior closed units:** snapshots/v0.10 (32ea3a9 second-chain retirement);
snapshots/v0.9 (ba05cf4 qemu-img disk-create + ROE persist)
**Boot consumer:** test/thyris_vm/runs/20260912_043438/result.json
**Gate (immune bind, not this boot):** results/pan_gate_20260912_092909.json

## Engagement 3 — retire the in-process second threat chain (CLOSED)

- mode: EDIT
- target_module: security/defensive_sovereignty.py
- target_symbols: BlockchainThreatIntelligence.__init__,
  ThreatDetectionModule.share_threat_intelligence,
  ThreatDetectionModule.bind_immune_system,
  DistributedDefenseModule.__init__
- coupled: security/defensive_offensive_bridge.py bind of defensive owners;
  test/immune/test_planetary_immune_system.py
- justification: I edited the lineage owner that still constructed an in-process
  PoW chain beside USMS. Combat memory stays PlanetaryImmuneSystem + USMS
  Ed25519 DAG + PAN RSA packets, bound not collapsed. A wrapper that copied
  USMS into BlockchainThreatIntelligence is banned. ROE persist already lives
  on the immune owner (ba05cf4); this unit did not duplicate it. L4 without
  human authorization stays fail-loud on PlanetaryImmuneSystem.
- author: daeron
- date: 2026-09-12
- closed: 2026-09-12 after `second_chain_retired_share_uses_immune` plus the
  existing ROE/L4 checks (32ea3a9). This worker does not reopen that unit.

## Engagement 4 — Android-x86 guest boot (CLOSED)

- mode: EDIT
- target_module: telecom/phone_orchestrator.py
- target_symbols: boot_android_installer, _get_android_iso_path, _start_android_vm
- justification: I edited the owned Android QEMU start path because wrapping
  a second emulator helper would copy argv while leaving -enable-kvm, which
  cannot run on this Windows host. Disk create stays landed
  ISOConverter._create_disk (ba05cf4). Immune/ROE/BlockchainThreatIntelligence
  stay 32ea3a9. This unit only proves a real android-x86_64-9.0-r2.iso guest
  boot via -nographic console evidence.
- author: daeron
- date: 2026-09-12
- closed: 2026-09-12 after `test_thyris_android_boot.py` 4/4 on Windows QEMU
  11.1.0 TCG. Official ISO SHA-1 matched. Console showed SeaBIOS plus
  ISOLINUX 6.03. `phone_ready` and `adb_proven` stayed false. No second
  qemu-img create owner. Not added to `run_pan_gate.py` because the ISO is
  local and gitignored.

## Still out of scope / remaining

- adb userspace / PhoneVMState.READY
- inventing DHT `usms_linkage` / `mesh-strand` / `pan_refs`
- `prompt_bridge`, `schemas.session`, `memory_system`
- master_db §6.2 / Orama
- Autonomous ROE Level 4 against external hosts
- redoing BlockchainThreatIntelligence retirement
