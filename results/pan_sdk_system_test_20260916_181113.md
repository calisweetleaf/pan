# PAN SDK system scenario 20260916_181113

I ran `python3 test/pan_sdk_system_scenario.py` at 20260916_181113.
I found passed=`True`.

## What I required

I required one civic walkthrough to exercise SovereignTreasury, an explicit
EmailSocialNode, and MasterDatabase on the same PANPersistenceStore. I did not
auto-bind mail onto DHTNode. I used a real TemporaryDirectory sqlite fixture.
I did not mock owners. PoI mint re-executes the bound `_run_inference`
owner. I did not call qemu.

## What I found

I found shared sqlite `/tmp/pan_sdk_system_i94m8w6j/pan_state.db`.
I found treasury state `MINT_PHASE` with 3 validators and PoI mint 40 leaving balance 240.
I found master_db mint document `{'proposal_id': 'd9ba0f732377608a0ae8044ed6f64b1f', 'amount': 40, 'recipient': 'e17d80e1843cceac6dd39dc893b2172c8a1a5639c6a696d762de4907509906ee', 'treasury_state': 'MINT_PHASE'}` and inference_cycles `3`.
I found explicit mail packet `1575006523e080a0cab133d8938cd8d3fd9ad44ea8d72c61dbd44b35c8cdfce2` and email_not_auto_bound=`True`.

## Operations

```json
{
  "citizen_id": "f75385e9-5509-5b2b-93b1-e55456e6c05a",
  "developer_id": "19a624bc-05d9-542f-b1f6-40a5c13dc93a",
  "app_id": "6d660ba6-50f6-5ed4-99b5-60f5ec722de9",
  "registered_name": "testname",
  "proposal_id": "69373e40-86db-5cf6-9cf0-a08f67dc3266",
  "treasury_state": "MINT_PHASE",
  "treasury_validators": 3,
  "poi_mint_amount": 40,
  "poi_balance": 240,
  "poi_proposal_id": "d9ba0f732377608a0ae8044ed6f64b1f",
  "mail_packet_id": "1575006523e080a0cab133d8938cd8d3fd9ad44ea8d72c61dbd44b35c8cdfce2",
  "social_packet_id": "a1c90482a3caee7e11f14d37bad3d40cc74e6d362a4aa280dac5a7ee3770bb7b",
  "master_db_mint": {
    "proposal_id": "d9ba0f732377608a0ae8044ed6f64b1f",
    "amount": 40,
    "recipient": "e17d80e1843cceac6dd39dc893b2172c8a1a5639c6a696d762de4907509906ee",
    "treasury_state": "MINT_PHASE"
  },
  "master_db_cycles": 3,
  "shared_sqlite": "/tmp/pan_sdk_system_i94m8w6j/pan_state.db",
  "email_explicit": true,
  "email_not_auto_bound": true,
  "peer_identity_hash": "0675be6ea60ba14ca95c41b0ce9022643351318ae726a3c3ec2a4a83c1f57e21",
  "email_relay_component": "email_relay_8e351937b2d1bea06dbe328bf2afebe49e8f4d5ea65be38007ae893d2268b98e",
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
    "email_relay_8e351937b2d1bea06dbe328bf2afebe49e8f4d5ea65be38007ae893d2268b98e": 2,
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
- `email_relay_8e351937b2d1bea06dbe328bf2afebe49e8f4d5ea65be38007ae893d2268b98e`: MATCH
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

- `/home/daeron/LAB/Experiments/projects/pan-sdk/results/pan_sdk_system_test_20260916_181113.json`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/results/pan_sdk_system_test_20260916_181113.md`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/results/pan_sdk_system_test_20260916_181113.log`

