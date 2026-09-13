# Planetary highway run 20260912_235042

I ran `python test/highway/test_planetary_highway.py` at 20260912_235042.
I found status `fail` with 8 passed, 2 failed, 0 skipped.

## What I required

I required identity-hash hops, cargo RSA-sealed to the destination,
blind relays, a real firewall, and no pickle/UDP/ARFS second internet.

## Checks

- `source_has_no_legacy_mesh`: fail
  - error: `highway source still contains ['pickle', 'Fernet', 'PlanetaryARFSNetwork']`
- `requires_explicit_firewall`: pass
- `direct_travel_sealed_cargo`: pass
- `multi_hop_three_nodes`: pass
- `firewall_blocks_telemetry_on_hop`: fail
  - error: `telemetry hop was published`
- `legacy_routing_key_rejected`: pass
- `identity_blocklist_stops_travel`: pass
- `bad_usms_signature_fails_loud`: pass
- `cargo_survives_restart`: pass
- `dht_index_optional_and_unbound_to_firewall`: pass

## Artifacts

- `C:\Users\trent\pan\test\highway\runs\20260912_235042\result.json`
- `C:\Users\trent\pan\test\highway\runs\20260912_235042\result.md`
- `C:\Users\trent\pan\test\highway\runs\20260912_235042\result.log`

