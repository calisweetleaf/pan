# Sovereign inference run 20260918_015456

I ran `python test/inference/test_sovereign_inference.py` at 20260918_015456.
I found status `pass` with 7 passed, 0 failed, 0 skipped.

## What I required

I required a real on-disk PANLIN01 weight file, fail-loud load on missing
or mismatched bytes, bit-identical re-execution by a second engine, prompt
and temperature divergence, and process_request to call that same owner.
I rejected the old canned simulation strings.

## Checks

- `missing_model_fails_loud`: pass
- `hash_mismatch_fails_loud`: pass
- `corrupt_header_fails_loud`: pass
- `reexecution_matches`: pass
- `prompt_and_temperature_diverge`: pass
- `process_request_uses_owner`: pass
- `illegal_args_fail_loud`: pass

## Artifacts

- `C:\Users\trent\pan\test\inference\runs\20260918_015456\result.json`
- `C:\Users\trent\pan\test\inference\runs\20260918_015456\result.md`
- `C:\Users\trent\pan\test\inference\runs\20260918_015456\result.log`

