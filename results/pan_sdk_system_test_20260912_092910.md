# PAN SDK system scenario 20260912_092910

I ran `python3 test/pan_sdk_system_scenario.py` at 20260912_092910.
I found passed=`True`.

## What I required

I required one civic walkthrough to exercise SovereignTreasury, an explicit
EmailSocialNode, and MasterDatabase on the same PANPersistenceStore. I did not
auto-bind mail onto DHTNode. I used a real TemporaryDirectory sqlite fixture.
I did not mock owners. PoI mint re-executes the bound `_run_inference`
owner. I did not call qemu.

## What I found

I found shared sqlite `/tmp/pan_sdk_system_hsefkid1/pan_state.db`.
I found treasury state `MINT_PHASE` with 3 validators and PoI mint 40 leaving balance 240.
I found master_db mint document `{'proposal_id': '877fbc458128d30d9824dc02138d7024', 'amount': 40, 'recipient': '7dc6cb8eefccd99a2f0eb50fee5782c30dd4921ee99df57c93d0c3808eff2cc4', 'treasury_state': 'MINT_PHASE'}` and inference_cycles `3`.
I found explicit mail packet `c575a29bdcebd45ec2732a1ac995aab25feea9b93dfd35948b2135f93936a3b9` and email_not_auto_bound=`True`.

## Operations

```json
{
  "citizen_id": "8db5607e-d625-5d28-bb71-61e670c7d785",
  "developer_id": "68ab6257-b6be-5f55-b785-38139d16c98a",
  "app_id": "6d660ba6-50f6-5ed4-99b5-60f5ec722de9",
  "registered_name": "testname",
  "proposal_id": "bc328314-53ca-5e20-b25d-8aa4d832c94c",
  "treasury_state": "MINT_PHASE",
  "treasury_validators": 3,
  "poi_mint_amount": 40,
  "poi_balance": 240,
  "poi_proposal_id": "877fbc458128d30d9824dc02138d7024",
  "mail_packet_id": "c575a29bdcebd45ec2732a1ac995aab25feea9b93dfd35948b2135f93936a3b9",
  "social_packet_id": "2a86879331726de642007f6c1db00bbc5abee5c20d4d56a2ab23afc2f4b7a9ef",
  "master_db_mint": {
    "proposal_id": "877fbc458128d30d9824dc02138d7024",
    "amount": 40,
    "recipient": "7dc6cb8eefccd99a2f0eb50fee5782c30dd4921ee99df57c93d0c3808eff2cc4",
    "treasury_state": "MINT_PHASE"
  },
  "master_db_cycles": 3,
  "shared_sqlite": "/tmp/pan_sdk_system_hsefkid1/pan_state.db",
  "email_explicit": true,
  "email_not_auto_bound": true,
  "peer_identity_hash": "cd1a0db9e20a88079d44c743c727dc5b47f656002a48afa46446904ea66c91c6",
  "email_relay_component": "email_relay_70f2c57594fb606242afcda7fd18e61ec404f72d3f804f667badf16a0a18ffe2",
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
    "email_relay_70f2c57594fb606242afcda7fd18e61ec404f72d3f804f667badf16a0a18ffe2": 2,
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
- `email_relay_70f2c57594fb606242afcda7fd18e61ec404f72d3f804f667badf16a0a18ffe2`: MATCH
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

- `/workspace/results/pan_sdk_system_test_20260912_092910.json`
- `/workspace/results/pan_sdk_system_test_20260912_092910.md`
- `/workspace/results/pan_sdk_system_test_20260912_092910.log`

