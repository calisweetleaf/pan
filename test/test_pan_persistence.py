"""Direct persistence round-trip probe for PAN civic state."""

from __future__ import annotations

import gc
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Dict

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PAN_SDK import DHTNode, PANPersistenceStore, SovereignIdentity


COMPONENTS = (
    "dht_data",
    "dht_ledger",
    "economy_accounts",
    "governance_proposals",
    "governance_policies",
)


def _snapshot(store: PANPersistenceStore) -> Dict[str, Any]:
    return {component: store.load_component(component) for component in COMPONENTS}


def run() -> Dict[str, Any]:
    print("=== persistence round-trip ===")
    details: Dict[str, Any] = {"components": list(COMPONENTS), "matches": {}}
    persistence_one = None
    persistence_two = None
    try:
        with tempfile.TemporaryDirectory(prefix="pan_persist_") as tmpdir:
            storage_path = Path(tmpdir)
            print(f"storage={storage_path}")
            node_identity = SovereignIdentity("PersistenceNode")
            persistence_one = PANPersistenceStore(base_path=storage_path)
            node_one = DHTNode(node_identity, persistence=persistence_one)

            stored = node_one.store("name:alice", {"record": "value"}, require_consensus=False)
            print(f"dht.store name:alice -> {stored}")
            minted = node_one.economic_engine.mint_tokens(node_identity.identity_hash, 50, "bootstrap")
            print(f"mint_tokens -> {minted}")
            node_one.governance_council.register_member(node_identity.identity_hash, role="admin", voting_power=3)
            proposal = node_one.governance_council.submit_proposal(
                proposer_id=node_identity.identity_hash,
                title="Adopt Open Policy",
                proposal_type="policy",
                content={"body": "Policy text"},
            )
            node_one.governance_council.cast_vote(proposal.proposal_id, node_identity.identity_hash, "YES")
            node_one.governance_council.finalize_proposal(proposal.proposal_id, force=True)
            print(f"proposal={proposal.proposal_id[:12]} status={proposal.status}")

            first = _snapshot(persistence_one)
            for name, payload in first.items():
                print(f"snapshot {name}: {len(payload)} keys")
            persistence_one.close()
            persistence_one = None

            persistence_two = PANPersistenceStore(base_path=storage_path)
            node_two = DHTNode(node_identity, persistence=persistence_two)
            second = _snapshot(persistence_two)
            all_match = True
            for name in COMPONENTS:
                matched = first[name] == second[name]
                details["matches"][name] = matched
                print(f"compare {name}: {'MATCH' if matched else 'MISMATCH'}")
                if not matched:
                    all_match = False
                    print(f"  original_keys={sorted(first[name])}")
                    print(f"  reloaded_keys={sorted(second[name])}")
            in_memory_accounts = node_two.economic_engine.accounts
            print(f"hydrated accounts={len(in_memory_accounts)} proposals={len(node_two.governance_council.proposals)}")
            if not all_match:
                raise AssertionError("persistence round-trip mismatch")
            details["account_count"] = len(in_memory_accounts)
            details["proposal_count"] = len(node_two.governance_council.proposals)
            persistence_two.close()
            persistence_two = None
        return {"name": "persistence", "passed": True, "details": details}
    except Exception as exc:
        print(f"FAIL persistence: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return {"name": "persistence", "passed": False, "error": f"{type(exc).__name__}: {exc}", "details": details}
    finally:
        for handle in (persistence_one, persistence_two):
            if handle is None:
                continue
            try:
                handle.close()
            except Exception:
                traceback.print_exc()
        time.sleep(0.05)
        gc.collect()


if __name__ == "__main__":
    result = run()
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
