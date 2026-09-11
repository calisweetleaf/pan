# Sovereign treasury run 20260911_004043

I ran `python test/treasury/test_sovereign_treasury.py` at 20260911_004043.
I found status `pass` with 5 passed, 0 failed, 0 skipped.

## What I required

I required a rigid FSM, Proof-of-Inference minting, ceil(n/2)+1 quorum,
smart-contract rejection, and sqlite hydrate after reopen.

## Checks

- `genesis_rejects_mint`: pass
- `seal_genesis_and_contract_reject`: pass
- `poi_mint_requires_quorum`: pass
- `distribute_and_burn_and_halts`: pass
- `restart_hydrates_fsm`: pass

## Artifacts

- `C:\Users\trent\pan\test\treasury\runs\20260911_004043\result.json`
- `C:\Users\trent\pan\test\treasury\runs\20260911_004043\result.md`
- `C:\Users\trent\pan\test\treasury\runs\20260911_004043\result.log`

