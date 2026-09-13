# PAN SDK system scenario 20260912_235400

I ran `python3 test/pan_sdk_system_scenario.py` at 20260912_235400.
I found passed=`True`.

## What I required

I required one civic walkthrough to exercise SovereignTreasury, an explicit
EmailSocialNode, and MasterDatabase on the same PANPersistenceStore. I did not
auto-bind mail onto DHTNode. I used a real TemporaryDirectory sqlite fixture.
I did not mock owners. PoI mint re-executes the bound `_run_inference`
owner. I did not call qemu.

## What I found

I found shared sqlite `C:\Users\trent\AppData\Local\Temp\pan_sdk_system_4dzcu9gd\pan_state.db`.
I found treasury state `MINT_PHASE` with 3 validators and PoI mint 40 leaving balance 240.
I found master_db mint document `{'proposal_id': 'c90bc4e901fa31f4a7219057dadb1b95', 'amount': 40, 'recipient': '036c887f4850fefa20155606796c7457e2efdf013d653b0782cee1c41becd763', 'treasury_state': 'MINT_PHASE'}` and inference_cycles `3`.
I found explicit mail packet `107523935ee3b57446dde164142e7265ea875e619a2091f08c8024635e6ea079` and email_not_auto_bound=`True`.

## Operations

```json
{
  "citizen_id": "b154bda7-b3c4-55f6-a1f6-3e6dafdc2446",
  "developer_id": "e4463131-5b85-5ab1-8d1e-147e848d2f31",
  "app_id": "6d660ba6-50f6-5ed4-99b5-60f5ec722de9",
  "registered_name": "testname",
  "proposal_id": "79919f06-a38d-5568-aa49-23dabf6fbff9",
  "treasury_state": "MINT_PHASE",
  "treasury_validators": 3,
  "poi_mint_amount": 40,
  "poi_balance": 240,
  "poi_proposal_id": "c90bc4e901fa31f4a7219057dadb1b95",
  "mail_packet_id": "107523935ee3b57446dde164142e7265ea875e619a2091f08c8024635e6ea079",
  "social_packet_id": "277bfe6ed7bd131503d58ad3492b3c3cec2b10297401b447c5ea4e17d8c14ae2",
  "master_db_mint": {
    "proposal_id": "c90bc4e901fa31f4a7219057dadb1b95",
    "amount": 40,
    "recipient": "036c887f4850fefa20155606796c7457e2efdf013d653b0782cee1c41becd763",
    "treasury_state": "MINT_PHASE"
  },
  "master_db_cycles": 3,
  "shared_sqlite": "C:\\Users\\trent\\AppData\\Local\\Temp\\pan_sdk_system_4dzcu9gd\\pan_state.db",
  "email_explicit": true,
  "email_not_auto_bound": true,
  "peer_identity_hash": "15af51ac2c494ab26d34743ff05f2154a30042e8a709695ebfe4460da1066ca3",
  "email_relay_component": "email_relay_436d93d0522ec1bdd976f7d0ee0b8707dafab7f9bc25987bf36808ebe7e176a2",
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
    "email_relay_436d93d0522ec1bdd976f7d0ee0b8707dafab7f9bc25987bf36808ebe7e176a2": 2,
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
- `email_relay_436d93d0522ec1bdd976f7d0ee0b8707dafab7f9bc25987bf36808ebe7e176a2`: MATCH
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

- `C:\Users\trent\pan\results\pan_sdk_system_test_20260912_235400.json`
- `C:\Users\trent\pan\results\pan_sdk_system_test_20260912_235400.md`
- `C:\Users\trent\pan\results\pan_sdk_system_test_20260912_235400.log`

