# PAN SDK system scenario 20260916_181316

I ran `python3 test/pan_sdk_system_scenario.py` at 20260916_181316.
I found passed=`True`.

## What I required

I required one civic walkthrough to exercise SovereignTreasury, an explicit
EmailSocialNode, and MasterDatabase on the same PANPersistenceStore. I did not
auto-bind mail onto DHTNode. I used a real TemporaryDirectory sqlite fixture.
I did not mock owners. PoI mint re-executes the bound `_run_inference`
owner. I did not call qemu.

## What I found

I found shared sqlite `/tmp/pan_sdk_system_s79dzcyi/pan_state.db`.
I found treasury state `MINT_PHASE` with 3 validators and PoI mint 40 leaving balance 240.
I found master_db mint document `{'proposal_id': 'b1cc8e1fec7876ef81cf2c0d8e00ca18', 'amount': 40, 'recipient': '4eb72a46f19a3259628b107754dfab4b3b9f2e0aa6a2b493eb9769f994b43308', 'treasury_state': 'MINT_PHASE'}` and inference_cycles `3`.
I found explicit mail packet `d12dc64e048ca0706a0d16e123e55cf20de13f55a05b464e232f9ccb2fe01f6e` and email_not_auto_bound=`True`.

## Operations

```json
{
  "citizen_id": "ab26a4b6-289b-5714-9015-dd794f45a57f",
  "developer_id": "c1a00c3c-5e96-53fb-8bbb-99070a462cec",
  "app_id": "6d660ba6-50f6-5ed4-99b5-60f5ec722de9",
  "registered_name": "testname",
  "proposal_id": "84993aa8-27f2-5a32-8fe6-c885a52b62d5",
  "treasury_state": "MINT_PHASE",
  "treasury_validators": 3,
  "poi_mint_amount": 40,
  "poi_balance": 240,
  "poi_proposal_id": "b1cc8e1fec7876ef81cf2c0d8e00ca18",
  "mail_packet_id": "d12dc64e048ca0706a0d16e123e55cf20de13f55a05b464e232f9ccb2fe01f6e",
  "social_packet_id": "a5955376ba80babdbedeb00389bf2cf99ffe18a3ca9e9487b16a237ae8f3fabc",
  "master_db_mint": {
    "proposal_id": "b1cc8e1fec7876ef81cf2c0d8e00ca18",
    "amount": 40,
    "recipient": "4eb72a46f19a3259628b107754dfab4b3b9f2e0aa6a2b493eb9769f994b43308",
    "treasury_state": "MINT_PHASE"
  },
  "master_db_cycles": 3,
  "shared_sqlite": "/tmp/pan_sdk_system_s79dzcyi/pan_state.db",
  "email_explicit": true,
  "email_not_auto_bound": true,
  "peer_identity_hash": "81bcedee5217cd59ce4fd8b826e209f62248e46f7eaf811bf9703879dde075f8",
  "email_relay_component": "email_relay_9caabfa92c17997c98e6dd7698357b42e47d693fb3d38dabc0276382967b2c17",
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
    "email_relay_9caabfa92c17997c98e6dd7698357b42e47d693fb3d38dabc0276382967b2c17": 2,
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
- `email_relay_9caabfa92c17997c98e6dd7698357b42e47d693fb3d38dabc0276382967b2c17`: MATCH
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

- `/home/daeron/LAB/Experiments/projects/pan-sdk/results/pan_sdk_system_test_20260916_181316.json`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/results/pan_sdk_system_test_20260916_181316.md`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/results/pan_sdk_system_test_20260916_181316.log`

