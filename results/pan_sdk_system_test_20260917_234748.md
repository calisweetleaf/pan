# PAN SDK system scenario 20260917_234748

I ran `python3 test/pan_sdk_system_scenario.py` at 20260917_234748.
I found passed=`True`.

## What I required

I required one civic walkthrough to exercise SovereignTreasury, an explicit
EmailSocialNode, and MasterDatabase on the same PANPersistenceStore. I did not
auto-bind mail onto DHTNode. I used a real TemporaryDirectory sqlite fixture.
I did not mock owners. PoI mint re-executes the bound `_run_inference`
owner. I did not call qemu.

## What I found

I found shared sqlite `/tmp/pan_sdk_system_x521wol5/pan_state.db`.
I found treasury state `MINT_PHASE` with 3 validators and PoI mint 40 leaving balance 240.
I found master_db mint document `{'proposal_id': '215a821dbd79fb5592ad5375a96e1056', 'amount': 40, 'recipient': 'e68f869bc90b2b6b2e48663c7146ff1d7172ce5c55074d8e36de29ebd5bfd472', 'treasury_state': 'MINT_PHASE'}` and inference_cycles `3`.
I found explicit mail packet `f945fad4734aa37bdfabfd68d4467200345e788491f74e158bbe0f69b0143500` and email_not_auto_bound=`True`.

## Operations

```json
{
  "citizen_id": "512a51d4-bbe9-5ef6-a08c-165a67781b6d",
  "developer_id": "3e382ada-da2d-5b98-bb68-d2f20f48552f",
  "app_id": "6d660ba6-50f6-5ed4-99b5-60f5ec722de9",
  "registered_name": "testname",
  "proposal_id": "601f0bd6-eed6-544c-88cc-073df474ade9",
  "treasury_state": "MINT_PHASE",
  "treasury_validators": 3,
  "poi_mint_amount": 40,
  "poi_balance": 240,
  "poi_proposal_id": "215a821dbd79fb5592ad5375a96e1056",
  "mail_packet_id": "f945fad4734aa37bdfabfd68d4467200345e788491f74e158bbe0f69b0143500",
  "social_packet_id": "1b4844decb4736925d780296c9c508ded4539db68e503db2e8248cbee43d0eee",
  "master_db_mint": {
    "proposal_id": "215a821dbd79fb5592ad5375a96e1056",
    "amount": 40,
    "recipient": "e68f869bc90b2b6b2e48663c7146ff1d7172ce5c55074d8e36de29ebd5bfd472",
    "treasury_state": "MINT_PHASE"
  },
  "master_db_cycles": 3,
  "shared_sqlite": "/tmp/pan_sdk_system_x521wol5/pan_state.db",
  "email_explicit": true,
  "email_not_auto_bound": true,
  "peer_identity_hash": "6f5ab9731993474cc8c6c66005f400ba7535780d653d0316cac6b4a458ce0dce",
  "email_relay_component": "email_relay_a0215c74c3d671ff7f608b6bbf4bf5d9c87237ed092ddac59f733e8ad9231042",
  "snapshot_sizes": {
    "dht_data": 12,
    "dht_ledger": 19,
    "economy_accounts": 6,
    "governance_proposals": 1,
    "governance_policies": 2,
    "citizens": 2,
    "applications": 1,
    "name_registry": 1,
    "phone_addresses": 1,
    "treasury_fsm": 1,
    "treasury_validators": 3,
    "treasury_proposals": 1,
    "master_db_docs": 1,
    "master_db_counters": 1,
    "master_db_sets": 1,
    "master_db_meta": 1,
    "email_relay_a0215c74c3d671ff7f608b6bbf4bf5d9c87237ed092ddac59f733e8ad9231042": 2,
    "pending_transactions": 1,
    "usage_metrics": 2,
    "personal_contacts": 1,
    "personal_messages": 1,
    "personal_call_logs": 1,
    "personal_preferences": 10
  }
}
```

## Comparisons

- `dht_data`: MATCH
- `dht_ledger`: MATCH
- `economy_accounts`: MATCH
- `governance_proposals`: MATCH
- `governance_policies`: MATCH
- `citizens`: MATCH
- `applications`: MATCH
- `name_registry`: MATCH
- `phone_addresses`: MATCH
- `treasury_fsm`: MATCH
- `treasury_validators`: MATCH
- `treasury_proposals`: MATCH
- `master_db_docs`: MATCH
- `master_db_counters`: MATCH
- `master_db_sets`: MATCH
- `master_db_meta`: MATCH
- `email_relay_a0215c74c3d671ff7f608b6bbf4bf5d9c87237ed092ddac59f733e8ad9231042`: MATCH
- `pending_transactions`: MATCH
- `usage_metrics`: MATCH
- `personal_contacts`: MATCH
- `personal_messages`: MATCH
- `personal_call_logs`: MATCH
- `personal_preferences`: MATCH
- `treasury_fsm_live`: MATCH
- `master_db_live`: MATCH
- `email_relay_live`: MATCH
- `email_not_auto_bound`: MATCH

## Artifacts

- `/home/daeron/LAB/Experiments/projects/pan-sdk/results/pan_sdk_system_test_20260917_234748.json`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/results/pan_sdk_system_test_20260917_234748.md`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/results/pan_sdk_system_test_20260917_234748.log`

