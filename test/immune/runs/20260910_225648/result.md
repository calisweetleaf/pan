# Planetary immune system run 20260910_225648

I ran `python test/immune/test_planetary_immune_system.py` at 20260910_225648.
I found status `fail` with 6 passed, 3 failed, 0 skipped.

## What I required

I required a real USMS sqlite file, a real firewall ledger, and two PAN DHT nodes.
I required the demo firewall to be gone. I required high-confidence beliefs to
become `THREAT_MEMORY_BULLETIN` packets that a peer can ingest after restart.

## Checks

- `firewall_blocks_telemetry`: pass
- `firewall_allows_civic_chat`: pass
- `inspect_content_compresses_secrets`: pass
- `signed_secret_packet_is_blocked`: pass
- `identity_blocklist`: pass
- `legacy_ip_routing_blocked`: pass
- `memory_survives_restart`: fail
  - error: `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\trent\\AppData\\Local\\Temp\\immune_restart_cmual6bi\\usms\\memory_store\\logs\\unified_sovereign_memory.log'`
- `peer_ingests_bulletin`: fail
  - error: `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\trent\\AppData\\Local\\Temp\\immune_mesh_lh7u3hi3\\alpha\\usms\\memory_store\\logs\\unified_sovereign_memory.log'`
- `contradiction_and_campaign_entangle`: fail
  - error: `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\trent\\AppData\\Local\\Temp\\immune_campaign_00s9qu0h\\usms\\memory_store\\logs\\unified_sovereign_memory.log'`

## Artifacts

- `C:\Users\trent\pan\test\immune\runs\20260910_225648\result.json`
- `C:\Users\trent\pan\test\immune\runs\20260910_225648\result.md`
- `C:\Users\trent\pan\test\immune\runs\20260910_225648\result.log`

