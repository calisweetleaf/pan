# PAN SDK system scenario 20260912_091540

I ran `python3 test/pan_sdk_system_scenario.py` at 20260912_091540.
I found passed=`True`.

## What I required

I required one civic walkthrough to exercise SovereignTreasury, an explicit
EmailSocialNode, and MasterDatabase on the same PANPersistenceStore. I did not
auto-bind mail onto DHTNode. I used a real TemporaryDirectory sqlite fixture.
I did not mock owners. PoI mint re-executes the bound `_run_inference`
owner. I did not call qemu.

## What I found

I found shared sqlite `/tmp/pan_sdk_system_10a2b_34/pan_state.db`.
I found treasury state `MINT_PHASE` with 3 validators and PoI mint 40 leaving balance 240.
I found master_db mint document `{'proposal_id': '10d20ac40af1aef147707896bb805063', 'amount': 40, 'recipient': '2319c98cf0b3b63cf35792326eb0cb262e5f4cfd29e4584732a8a34fe8a85105', 'treasury_state': 'MINT_PHASE'}` and inference_cycles `3`.
I found explicit mail packet `91107e278eec67ad823899a562574ec5164ba648994d3a9d6386f529892881bd` and email_not_auto_bound=`True`.

## Operations

```json
{
  "citizen_id": "c2f2db0c-726d-5e48-9508-d3e6f494c872",
  "developer_id": "015dbca2-f72e-5973-b078-f4e50e1943b5",
  "app_id": "6d660ba6-50f6-5ed4-99b5-60f5ec722de9",
  "registered_name": "testname",
  "proposal_id": "551e644b-658c-5c12-a2ab-a2d86e3929e2",
  "treasury_state": "MINT_PHASE",
  "treasury_validators": 3,
  "poi_mint_amount": 40,
  "poi_balance": 240,
  "poi_proposal_id": "10d20ac40af1aef147707896bb805063",
  "mail_packet_id": "91107e278eec67ad823899a562574ec5164ba648994d3a9d6386f529892881bd",
  "social_packet_id": "6913d8af95387f5a5151c8f9e8e5e6261f1b065dad8e6397ce2a634473ee7e6b",
  "master_db_mint": {
    "proposal_id": "10d20ac40af1aef147707896bb805063",
    "amount": 40,
    "recipient": "2319c98cf0b3b63cf35792326eb0cb262e5f4cfd29e4584732a8a34fe8a85105",
    "treasury_state": "MINT_PHASE"
  },
  "master_db_cycles": 3,
  "shared_sqlite": "/tmp/pan_sdk_system_10a2b_34/pan_state.db",
  "email_explicit": true,
  "email_not_auto_bound": true,
  "peer_identity_hash": "abc64231ac85ca57dd2db102407f6c29c847978e5c35f79055318d50b5f4f57a",
  "email_relay_component": "email_relay_2274d89ff89af9d0cd16d2c2dd652584c9fd3c864ffb1823351f2a7cb606a824",
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
    "email_relay_2274d89ff89af9d0cd16d2c2dd652584c9fd3c864ffb1823351f2a7cb606a824": 2,
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
- `email_relay_2274d89ff89af9d0cd16d2c2dd652584c9fd3c864ffb1823351f2a7cb606a824`: MATCH
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

- `/workspace/results/pan_sdk_system_test_20260912_091540.json`
- `/workspace/results/pan_sdk_system_test_20260912_091540.md`
- `/workspace/results/pan_sdk_system_test_20260912_091540.log`

