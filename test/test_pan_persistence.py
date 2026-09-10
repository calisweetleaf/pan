import sys
import tempfile
from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PAN_SDK import (
    PANPersistenceStore,
    DHTNode,
    SovereignIdentity,
    SovereignPipeline
)
# Ensure registry classes from separate module are loaded so DHTNode._initialize_registries
# can find and instantiate them automatically during tests.
import PAN_SDK.citizen_simulator  # side-effect: registers PANCitizenRegistry in module globals


def test_pan_persistence_round_trip():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)
        node_identity = SovereignIdentity("PersistenceNode")

        persistence_one = None
        persistence_two = None
        try:
            persistence_one = PANPersistenceStore(base_path=storage_path)
            node_one = DHTNode(node_identity, persistence=persistence_one)

            node_one.store("name:alice", {"record": "value"}, require_consensus=False)
            node_one.economic_engine.mint_tokens(node_identity.identity_hash, 50, "bootstrap")
            node_one.governance_council.register_member(node_identity.identity_hash, role="admin", voting_power=3)

            proposal = node_one.governance_council.submit_proposal(
                proposer_id=node_identity.identity_hash,
                title="Adopt Open Policy",
                proposal_type="policy",
                content={"body": "Policy text"},
            )
            node_one.governance_council.cast_vote(proposal.proposal_id, node_identity.identity_hash, "YES")
            node_one.governance_council.finalize_proposal(proposal.proposal_id, force=True)

            # Snapshot authoritative persisted state (avoid transient in-memory diffs)
            data_snapshot = persistence_one.load_component('dht_data')
            ledger_snapshot = persistence_one.load_component('dht_ledger')
            accounts_snapshot = persistence_one.load_component('economy_accounts')
            proposals_snapshot = persistence_one.load_component('governance_proposals')
            policies_snapshot = persistence_one.load_component('governance_policies')

            # Close the first persistence before reopening for verification
            if persistence_one:
                persistence_one.close()

            persistence_two = PANPersistenceStore(base_path=storage_path)
            node_two = DHTNode(node_identity, persistence=persistence_two)

            # Load authoritative persisted state from the reopened persistence instance
            data_reloaded = persistence_two.load_component('dht_data')
            ledger_reloaded = persistence_two.load_component('dht_ledger')
            accounts_reloaded = persistence_two.load_component('economy_accounts')
            proposals_reloaded = persistence_two.load_component('governance_proposals')
            policies_reloaded = persistence_two.load_component('governance_policies')

            assert data_reloaded == data_snapshot
            assert ledger_reloaded == ledger_snapshot
            assert accounts_reloaded == accounts_snapshot
            assert proposals_reloaded == proposals_snapshot
            assert policies_reloaded == policies_snapshot

        finally:
            # Ensure persistence handles are closed even if assertions fail
            try:
                if persistence_one:
                    persistence_one.close()
            except Exception:
                pass
            try:
                if persistence_two:
                    persistence_two.close()
            except Exception:
                pass
            # Give Windows a moment to release file handles (helps avoid WinError 32 on tempdir cleanup)
            try:
                import time as _time, gc as _gc
                _time.sleep(0.05)
                _gc.collect()
            except Exception:
                pass
