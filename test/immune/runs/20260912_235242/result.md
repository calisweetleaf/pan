# Planetary immune system run 20260912_235242

I ran `python test/immune/test_planetary_immune_system.py` at 20260912_235242.
I found status `fail` with 17 passed, 1 failed, 0 skipped.

## What I required

I required a real USMS sqlite file, a real firewall ledger, and two PAN DHT nodes.
I required the demo firewall to be gone. I required high-confidence beliefs to
become `THREAT_MEMORY_BULLETIN` packets that a peer can ingest after restart.
I required ROE DECEIVE/DEGRADE to persist as USMS BELIEF content via the
defensive-offensive bridge, and ROE Level 4 to fail without human authorization.

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
- `roe_ladder_persists_through_bridge`: pass
- `neutralize_requires_human_authorization`: pass
- `second_chain_retired_share_uses_immune`: pass
- `smtp_alert_fails_loud`: pass
- `webhook_alert_fails_loud`: pass
- `threat_feed_fetch_fails_loud`: pass
- `whois_fails_loud`: pass
- `wifi_deauth_fails_loud`: pass
- `bridge_refuses_simulated_authorization`: fail
  - error: `simulated_operator is still present`

## Artifacts

- `C:\Users\trent\pan\test\immune\runs\20260912_235242\result.json`
- `C:\Users\trent\pan\test\immune\runs\20260912_235242\result.md`
- `C:\Users\trent\pan\test\immune\runs\20260912_235242\result.log`

