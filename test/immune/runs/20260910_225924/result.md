# Planetary immune system run 20260910_225924

I ran `python test/immune/test_planetary_immune_system.py` at 20260910_225924.
I found status `pass` with 9 passed, 0 failed, 0 skipped.

## What I required

I required a real USMS sqlite file, a real firewall ledger, and two PAN DHT nodes.
I required the demo firewall to be gone. I required high-confidence beliefs to
become `THREAT_MEMORY_BULLETIN` packets that a peer can ingest after restart.

## What was surprising

I found Gemini's "same SovereignIdentity" claim is false on this repo: USMS
signs Ed25519, PAN signs RSA. Binding them worked. I also found USMS genesis
dead on Windows because `_atomic_write` opened a directory fd the POSIX way.
After that repair, restart search returned 4 hits for the original intel_id
and bravo ingested alpha's bulletin as local EVENT/BELIEF nodes.

## Checks

- `firewall_blocks_telemetry`: pass
- `firewall_allows_civic_chat`: pass
- `inspect_content_compresses_secrets`: pass
- `signed_secret_packet_is_blocked`: pass
- `identity_blocklist`: pass
- `legacy_ip_routing_blocked`: pass
- `memory_survives_restart`: pass
- `peer_ingests_bulletin`: pass
- `contradiction_and_campaign_entangle`: pass

## Artifacts

- `C:\Users\trent\pan\test\immune\runs\20260910_225924\result.json`
- `C:\Users\trent\pan\test\immune\runs\20260910_225924\result.md`
- `C:\Users\trent\pan\test\immune\runs\20260910_225924\result.log`

