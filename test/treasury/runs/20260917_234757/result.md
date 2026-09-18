# Sovereign treasury run 20260917_234757

I ran `python test/treasury/test_sovereign_treasury.py` at 20260917_234757.
I found status `pass` with 7 passed, 0 failed, 0 skipped.

## What I required

I required a rigid FSM, Proof-of-Inference minting against the bound
SovereignInferenceEngine owner, ceil(n/2)+1 quorum, smart-contract
rejection, sqlite hydrate after reopen, forged-output rejection, and
fail-loud mint when no engine is bound.

## Checks

- `genesis_rejects_mint`: pass
- `seal_genesis_and_contract_reject`: pass
- `poi_mint_requires_quorum`: pass
- `distribute_and_burn_and_halts`: pass
- `restart_hydrates_fsm`: pass
- `poi_rejects_forged_output`: pass
- `poi_unbound_engine_fails`: pass

## Artifacts

- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/treasury/runs/20260917_234757/result.json`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/treasury/runs/20260917_234757/result.md`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/treasury/runs/20260917_234757/result.log`

