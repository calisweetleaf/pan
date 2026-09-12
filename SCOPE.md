# SCOPE — closed: retire BlockchainThreatIntelligence as combat memory

**Status:** CLOSED 2026-09-12 after immune consumer 20260912_092843 (12/12).
**Ledger:** SOTA_RUN.md
**Snapshot:** snapshots/v0.10/manifest.json
**Immune:** test/immune/runs/20260912_092843/
**Gate:** results/pan_gate_20260912_092909.json (immune PASS 12/12; thyris_vm
FAIL only `qemu_img_disk_create` because qemu-img is absent on this worker.
That host-tool gap is pre-existing vs origin `ba05cf4`. This unit did not
install qemu.)

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
  existing ROE/L4 checks.

Choice: **retire construction and call sites** of BlockchainThreatIntelligence.
Rejected: invent mesh-strand/usms_linkage to match a trail that is not in this
tree; merge USMS sqlite into PANPersistenceStore; collapse RSA/Ed25519;
implement ROE Level 4 against external hosts.

## Still out of scope

- Android ISO / QEMU guest boot / adb (qemu-img also missing on this worker)
- inventing DHT `usms_linkage` / `mesh-strand` / `pan_refs`
- `prompt_bridge`, `schemas.session`, `memory_system`
- master_db §6.2 / Orama
- Autonomous ROE Level 4 against external hosts
