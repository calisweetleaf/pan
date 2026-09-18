# Planetary highway run 20260916_181120

I ran `python test/highway/test_planetary_highway.py` at 20260916_181120.
I found status `pass` with 10 passed, 0 failed, 0 skipped.

## What I required

I required identity-hash hops, cargo RSA-sealed to the destination,
blind relays, a real firewall, and no pickle/UDP/ARFS second internet.

## Checks

- `source_has_no_legacy_mesh`: pass
- `requires_explicit_firewall`: pass
- `direct_travel_sealed_cargo`: pass
- `multi_hop_three_nodes`: pass
- `firewall_blocks_telemetry_on_hop`: pass
- `legacy_routing_key_rejected`: pass
- `identity_blocklist_stops_travel`: pass
- `bad_usms_signature_fails_loud`: pass
- `cargo_survives_restart`: pass
- `dht_index_optional_and_unbound_to_firewall`: pass

## Artifacts

- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/highway/runs/20260916_181120/result.json`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/highway/runs/20260916_181120/result.md`
- `/home/daeron/LAB/Experiments/projects/pan-sdk/test/highway/runs/20260916_181120/result.log`

