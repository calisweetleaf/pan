# PAN SDK system scenario 20260911_091652

I ran `python3 test/pan_sdk_system_scenario.py` at 20260911_091652.
I found passed=`True`.

## What I required

I required one civic walkthrough to exercise SovereignTreasury, an explicit
EmailSocialNode, and MasterDatabase on the same PANPersistenceStore. I did not
auto-bind mail onto DHTNode. I used a real TemporaryDirectory sqlite fixture.
I did not mock owners. PoI mint re-executes the bound `_run_inference`
owner. I did not call qemu.

## What I found

I found shared sqlite `/tmp/pan_sdk_system_j8vo84f6/pan_state.db`.
I found treasury state `MINT_PHASE` with 3 validators and PoI mint 40 leaving balance 240.
I found master_db mint document `{'proposal_id': '8e518961282fc837dca5ed19922acbf8', 'amount': 40, 'recipient': '3b8c7918acd0597d08e4170aa013c20f3915845d725aab507e645c2b29991ca1', 'treasury_state': 'MINT_PHASE'}` and inference_cycles `3`.
I found explicit mail packet `51a0bd379fcf0ccb1fb8bd0bda737678a369384f51ef12451e2b2c178723a6c4` and email_not_auto_bound=`True`.

## Operations

```json
{
  "citizen_id": "d82d2222-3b02-5db7-9afd-1342337c68a2",
  "developer_id": "be087a98-050c-5e4a-bf6b-96d476d29882",
  "app_id": "6d660ba6-50f6-5ed4-99b5-60f5ec722de9",
  "registered_name": "testname",
  "proposal_id": "a05ca8b1-7956-588f-b682-30ec2781f7bc",
  "treasury_state": "MINT_PHASE",
  "treasury_validators": 3,
  "poi_mint_amount": 40,
  "poi_balance": 240,
  "poi_proposal_id": "8e518961282fc837dca5ed19922acbf8",
  "mail_packet_id": "51a0bd379fcf0ccb1fb8bd0bda737678a369384f51ef12451e2b2c178723a6c4",
  "social_packet_id": "bf9dbbbdc2aa26c475562ae8e49423e18607823dcf99e25a5a7890006397f53b",
  "master_db_mint": {
    "proposal_id": "8e518961282fc837dca5ed19922acbf8",
    "amount": 40,
    "recipient": "3b8c7918acd0597d08e4170aa013c20f3915845d725aab507e645c2b29991ca1",
    "treasury_state": "MINT_PHASE"
  },
  "master_db_cycles": 3,
  "shared_sqlite": "/tmp/pan_sdk_system_j8vo84f6/pan_state.db",
  "email_explicit": true,
  "email_not_auto_bound": true,
  "peer_identity_hash": "b97d010992f5d31d3196385df70f9494e6951c4e3b8b10a9cf4063515dc763c4",
  "email_relay_component": "email_relay_95e15a36945c63e388937a110b3b49e45c04af746d8d5f1123f8d3c6dd9fbe20",
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
    "email_relay_95e15a36945c63e388937a110b3b49e45c04af746d8d5f1123f8d3c6dd9fbe20": 2,
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
- `email_relay_95e15a36945c63e388937a110b3b49e45c04af746d8d5f1123f8d3c6dd9fbe20`: MATCH
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

- `/workspace/results/pan_sdk_system_test_20260911_091652.json`
- `/workspace/results/pan_sdk_system_test_20260911_091652.md`
- `/workspace/results/pan_sdk_system_test_20260911_091652.log`

