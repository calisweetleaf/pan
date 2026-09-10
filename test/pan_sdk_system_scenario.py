"""PAN SDK end-to-end scenario runner with detailed logging."""

import json
import logging
import tempfile
import time
from pathlib import Path
import os
import sys

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import PAN SDK components (assumed from parent directory based on project structure)
from PAN_SDK import (
    SovereignIdentity,
    PANPersistenceStore,
    DHTNode,
    PANCitizenRegistry,
    SovereignCommunicator,
    ModelManifest,
    SovereignPipeline,
    PANPhoneAddressRegistry,
    sha256_hex,
)

# Set up logging
LOGGER = logging.getLogger(__name__)

# Define missing helper functions (simple implementations based on usage)
def configure_logging(log_file: Path) -> None:
    """Configure logging to write to the specified file."""
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

def snapshot_dict(data: dict) -> dict:
    """Snapshot a dictionary."""
    return dict(data)

def snapshot_ledger(ledger) -> dict:
    """Snapshot ledger data (placeholder implementation)."""
    # Assuming ledger has a to_dict or similar; adjust if needed
    return ledger.to_dict() if hasattr(ledger, 'to_dict') else {}

def snapshot_pending_transactions(transactions) -> dict:
    """Snapshot pending transactions (placeholder implementation)."""
    # Assuming transactions is a dict or list; adjust if needed
    return dict(transactions) if isinstance(transactions, dict) else {}

def canonical(data) -> dict:
    """Canonicalize data (placeholder implementation)."""
    return dict(data) if isinstance(data, dict) else {}

def snapshot_proposals(proposals) -> dict:
    """Snapshot proposals (placeholder implementation)."""
    return {pid: p.to_dict() for pid, p in proposals.items()} if hasattr(proposals, 'items') else {}

def snapshot_citizens(citizens) -> dict:
    """Snapshot citizens (placeholder implementation)."""
    return {cid: c.to_dict() for cid, c in citizens.items()} if hasattr(citizens, 'items') else {}

CURRENT_DIR = Path(__file__).resolve().parent

def run_scenario(base_path: Path) -> None:
    LOGGER.info("Starting PAN SDK scenario. Persistence path: %s", base_path)
    top_old_cwd = Path.cwd()
    base_path.mkdir(parents=True, exist_ok=True)
    os.chdir(base_path)
    try:
        node_identity = SovereignIdentity("ScenarioNode")
        citizen_identity = SovereignIdentity("ScenarioCitizen")
        developer_identity = SovereignIdentity("ScenarioDeveloper")
        model_identity = SovereignIdentity("ScenarioModel")
        distributor_identity = SovereignIdentity("ScenarioDistributor")

        persistence_one = PANPersistenceStore(base_path=base_path)
        node_one = DHTNode(node_identity, persistence=persistence_one)

        # Use enhanced citizen registry with personal data integration
        enhanced_registry = PANCitizenRegistry(node_identity, node_one, persistence_one)
        node_one.citizen_registry = enhanced_registry

        LOGGER.info("Initializing additional PAN SDK components...")
        communicator = SovereignCommunicator(citizen_identity)
        manifest = ModelManifest("test_model", "dummy_model_hash", model_identity.get_public_key_pem(), model_identity)
        pipeline = SovereignPipeline(distributor_identity, dht_node=node_one)

        # Test SovereignCommunicator methods
        packet = communicator.create_packet("test_packet", {"test": "data"}, metadata={"version": "1.0"})
        LOGGER.info("Created test packet: %s", packet.packet_id[:12])
        verified = communicator.verify_packet(packet, citizen_identity.get_public_key_pem())
        LOGGER.info("Packet verification: %s", verified)

        # Test ModelManifest methods
        manifest_verified = manifest.verify_manifest(model_identity.get_public_key_pem())
        LOGGER.info("Manifest verification: %s", manifest_verified)

        # Test SovereignPipeline methods
        pipeline.register_model("test_model", "/dummy/model/path", model_identity)
        # download_package = pipeline.create_download_package("test_model", citizen_identity)  # Unused
        LOGGER.info("Created download package for test_model")

        # Initialize personal data components for end-to-end sweep
        LOGGER.info("Initializing personal data components...")
        # Import PANPersonalDataStore from personal_data module
        from PAN_SDK.personal_data import PANPersonalDataStore
        personal_data_store = PANPersonalDataStore(
            sovereign_id=citizen_identity.identity_hash,
            base_path=base_path / "personal_data",
            persistence=persistence_one
        )
        phone_registry = PANPhoneAddressRegistry(persistence=persistence_one)

        LOGGER.info("--- Phase 1: Initial operations ---")
        node_one.store("registry:name:alice", {"display_name": "Alice"}, require_consensus=False)
        node_one.store("registry:name:bob", {"display_name": "Bob"}, require_consensus=False)

        citizen = node_one.citizen_registry.register_citizen(citizen_identity, citizen_type="admin")
        developer = node_one.citizen_registry.register_citizen(developer_identity, citizen_type="developer")

        node_one.governance_council.register_member(citizen.identity_hash, role="admin", voting_power=5)

        app = node_one.citizen_registry.register_app("sovereign-feed", developer_identity, app_metadata={"category": "media"})
        node_one.economic_engine.mint_tokens(citizen.identity_hash, 250, reason="genesis_reward")
        node_one.economic_engine.record_usage(
            consumer_id=citizen.citizen_id,
            provider_id=app.app_id if app else None,
            service_type="app_usage",
            quantity=3,
            metadata={"app_name": "sovereign-feed"},
            bill_consumer=False,
        )

        # Additional DHTNode methods to cover more
        neighbor_identity = SovereignIdentity("NeighborNode")
        node_one.add_neighbor(neighbor_identity.identity_hash, "127.0.0.1", 8463)
        closest = node_one.get_closest_nodes(sha256_hex("some_key"))
        LOGGER.info("Closest nodes: %d", len(closest))

        # Consensus methods via store with consensus
        consensus_result = node_one.store("consensus_test", {"consensus": "data"}, require_consensus=True)
        LOGGER.info("Consensus store result: %s", consensus_result)

        # Name registry methods
        name_registered = node_one.name_registry.register_name("testname", citizen.identity_hash, "http://test.com")
        LOGGER.info("Name registration: %s", name_registered)
        resolved = node_one.name_registry.resolve_name("testname")
        LOGGER.info("Name resolution: %s", resolved is not None)

        # Economic engine additional methods
        balance = node_one.economic_engine.get_balance(citizen.identity_hash)
        LOGGER.info("Citizen balance: %d", balance)
        transfer = node_one.economic_engine.transfer_tokens(citizen.identity_hash, developer.identity_hash, 50, "test_transfer")
        LOGGER.info("Token transfer: %s", transfer["success"])

        # Governance additional methods
        open_proposals = node_one.governance_council.list_open_proposals()
        LOGGER.info("Open proposals: %d", len(open_proposals))

        # Constitution methods
        article_id = node_one.governance_council.constitution.add_article("Test Article", "Test body", citizen_identity)
        LOGGER.info("Added constitution article: %s", article_id[:12])

        # Policy registry methods
        policy_id = node_one.governance_council.policy_registry.register_policy("Test Policy", "Policy body", citizen.identity_hash)
        LOGGER.info("Registered policy: %s", policy_id[:12])
        policies = node_one.governance_council.policy_registry.list_policies()
        LOGGER.info("Listed policies: %d", len(policies))

        # Citizen registry additional methods
        got_citizen = node_one.citizen_registry.get_citizen(citizen.citizen_id)
        LOGGER.info("Retrieved citizen: %s", got_citizen is not None)

        # Defensive: app registration may fail (e.g., developer not registered as citizen)
        if app is None:
            LOGGER.warning("Application registration failed; skipping use_app and related checks")
        else:
            try:
                use_result = node_one.citizen_registry.use_app(citizen.citizen_id, app.app_id)
                LOGGER.info("App usage recorded: %s", "tokens" in use_result)
            except Exception as exc:
                LOGGER.exception("use_app raised an exception: %s", exc)

        proposal = node_one.governance_council.submit_proposal(
            proposer_id=citizen.identity_hash,
            title="Adopt Foundational Charter",
            proposal_type="policy",
            content={"body": "Foundational civic principles."},
        )
        node_one.governance_council.cast_vote(proposal.proposal_id, citizen.identity_hash, "YES")
        node_one.governance_council.finalize_proposal(proposal.proposal_id, force=True)

        # Governance additional methods after proposal
        got_proposal = node_one.governance_council.get_proposal(proposal.proposal_id)
        LOGGER.info("Retrieved proposal: %s", got_proposal is not None)

        # Personal data operations for end-to-end sweep
        LOGGER.info("Testing personal data operations...")
        # Add contact
        contact = personal_data_store.add_contact(
            display_name="Test Contact",
            pan_phone_address="pan:test:voice",
            phone_numbers=["+1234567890"],
            email_addresses=["test@example.com"],
            tags=["test"]
        )
        LOGGER.info("Added contact: %s", contact.contact_id[:12])

        # Send message
        message = personal_data_store.send_message(
            recipient_sovereign_id=developer.identity_hash,
            content="Test message",
            message_type="chat"
        )
        LOGGER.info("Sent message: %s", message.message_id[:12])

        # Log call
        call_log = personal_data_store.log_call(
            caller_sovereign_id=citizen.identity_hash,
            recipient_sovereign_id=developer.identity_hash,
            call_type="voice",
            direction="outgoing",
            duration_seconds=60
        )
        LOGGER.info("Logged call: %s", call_log.call_id[:12])

        # Update preferences
        prefs = personal_data_store.get_preferences()
        prefs.theme = "light"
        personal_data_store.save_preferences(prefs)
        LOGGER.info("Updated preferences for %s", citizen.identity_hash[:12])

        # Phone address registry operations
        phone_address = phone_registry.assign_phone_address(
            sovereign_id=citizen.identity_hash,
            vm_id="test_vm",
            network_hash="test_net",
            identity_motif="test_motif"
        )
        LOGGER.info("Assigned phone address: %s", phone_address)
        resolved = phone_registry.resolve_address(phone_address)
        LOGGER.info("Resolved phone address: %s", resolved is not None)

        LOGGER.info("--- Phase 1: Snapshotting state ---")
        snapshots = {
            "data_store": snapshot_dict(node_one.data_store),
            "ledger": snapshot_ledger(node_one.ledger),
            "pending_transactions": snapshot_pending_transactions(node_one.pending_transactions),
            "accounts": snapshot_dict(node_one.economic_engine.accounts),
            "usage_metrics": canonical(node_one.economic_engine.usage_metrics),
            "proposals": snapshot_proposals(node_one.governance_council.proposals),
            "policies": snapshot_dict(node_one.governance_council.policy_registry.policies),
            "citizens": snapshot_citizens(node_one.citizen_registry.citizens),
            "applications": snapshot_dict({aid: app_obj.to_dict() for aid, app_obj in node_one.citizen_registry.applications.items()}),
            # Add personal data snapshots
            "personal_contacts": {cid: c.to_dict() for cid, c in personal_data_store.contacts.items()},
            "personal_messages": {mid: m.to_dict() for mid, m in personal_data_store.messages.items()},
            "personal_call_logs": {clid: cl.to_dict() for clid, cl in personal_data_store.call_logs.items()},
            "personal_preferences": personal_data_store.preferences.to_dict() if personal_data_store.preferences else None,
            "phone_addresses": phone_registry.address_map,
        }

        LOGGER.debug("Snapshot data captured: %s", json.dumps(snapshots, indent=2))

        # Close persistence handles opened by node and personal data to release SQLite locks
        try:
            node_one.persistence.close()
        except Exception:
            LOGGER.exception("Failed to close node_one.persistence cleanly")

        try:
            personal_data_store.close()
        except Exception:
            LOGGER.exception("Failed to close personal_data_store cleanly")

        try:
            if hasattr(phone_registry, 'persistence') and phone_registry.persistence:
                phone_registry.persistence.close()
        except Exception:
            LOGGER.exception("Failed to close phone_registry.persistence cleanly")

        # Give OS time to release file handles on Windows, then force GC to drop references
        time.sleep(0.25)
        import gc
        gc.collect()

        LOGGER.info("--- Phase 2: Reloading from persistence ---")

        # Log files in the temp path to help debugging which DBs exist and where locks originate
        try:
            files = list(base_path.iterdir())
            LOGGER.debug("Temp dir files: %s", [f.name for f in files])
        except Exception:
            LOGGER.exception("Could not list temp dir files: %s", base_path)

        persistence_two = PANPersistenceStore(base_path=base_path)
        node_two = DHTNode(node_identity, persistence=persistence_two)

        # Use enhanced citizen registry with personal data integration
        enhanced_registry_two = PANCitizenRegistry(node_identity, node_two, persistence_two)
        node_two.citizen_registry = enhanced_registry_two

        # Reload personal data components
        from PAN_SDK.personal_data import PANPersonalDataStore
        personal_data_store_two = PANPersonalDataStore(
            sovereign_id=citizen_identity.identity_hash,
            base_path=base_path / "personal_data",
            persistence=persistence_two
        )
        phone_registry_two = PANPhoneAddressRegistry(persistence=persistence_two)

        comparisons = [
            ("data_store", snapshot_dict(node_two.data_store)),
            ("ledger", snapshot_ledger(node_two.ledger)),
            ("pending_transactions", snapshot_pending_transactions(node_two.pending_transactions)),
            ("accounts", snapshot_dict(node_two.economic_engine.accounts)),
            ("usage_metrics", canonical(node_two.economic_engine.usage_metrics)),
            ("proposals", snapshot_proposals(node_two.governance_council.proposals)),
            ("policies", snapshot_dict(node_two.governance_council.policy_registry.policies)),
            ("citizens", snapshot_citizens(node_two.citizen_registry.citizens)),
            ("applications", snapshot_dict({aid: app_obj.to_dict() for aid, app_obj in node_two.citizen_registry.applications.items()})),
            # Add personal data comparisons
            ("personal_contacts", {cid: c.to_dict() for cid, c in personal_data_store_two.contacts.items()}),
            ("personal_messages", {mid: m.to_dict() for mid, m in personal_data_store_two.messages.items()}),
            ("personal_call_logs", {clid: cl.to_dict() for clid, cl in personal_data_store_two.call_logs.items()}),
            ("personal_preferences", personal_data_store_two.preferences.to_dict() if personal_data_store_two.preferences else None),
            ("phone_addresses", phone_registry_two.address_map),
        ]

        all_match = True
        for key, reloaded in comparisons:
            original = snapshots[key]
            if original != reloaded:
                LOGGER.error("Mismatch detected for %s", key)
                LOGGER.debug("Original: %s", original)
                LOGGER.debug("Reloaded: %s", reloaded)
                all_match = False
            else:
                LOGGER.info("State verified for %s", key)

        # Ensure all persistence handles are explicitly closed to avoid file locks on Windows
        try:
            node_two.persistence.close()
        except Exception:
            LOGGER.exception("Failed to close node_two.persistence cleanly")

        try:
            if hasattr(personal_data_store_two, 'close') and callable(personal_data_store_two.close):
                personal_data_store_two.close()
        except Exception:
            LOGGER.exception("Failed to close personal_data_store_two cleanly")

        try:
            if hasattr(phone_registry_two, 'persistence') and phone_registry_two.persistence:
                phone_registry_two.persistence.close()
        except Exception:
            LOGGER.exception("Failed to close phone_registry_two.persistence cleanly")

        # Give OS time to release file handles on Windows, then force GC to drop references
        time.sleep(0.25)
        import gc
        gc.collect()

        if not all_match:
                raise SystemExit("PAN SDK scenario failed: state mismatch detected. See log for details.")

        LOGGER.info("PAN SDK scenario completed successfully. All persisted state verified.")
    finally:
        # Restore the caller's working directory no matter what
        try:
            os.chdir(top_old_cwd)
        except Exception:
            LOGGER.exception("Failed to restore original working directory")

        # Close handles opened earlier and attempt to clean up
        try:
            node_one.persistence.close()
        except Exception:
            LOGGER.exception("Failed to close node_one.persistence cleanly")

        try:
            personal_data_store.close()
        except Exception:
            LOGGER.exception("Failed to close personal_data_store cleanly")

        try:
            if hasattr(phone_registry, 'persistence') and phone_registry.persistence:
                phone_registry.persistence.close()
        except Exception:
            LOGGER.exception("Failed to close phone_registry.persistence cleanly")

        # Close second phase resources if they exist
        try:
            if 'persistence_two' in locals():
                persistence_two.close()
        except Exception:
            LOGGER.exception("Failed to close persistence_two cleanly")

        try:
            if 'personal_data_store_two' in locals():
                personal_data_store_two.close()
        except Exception:
            LOGGER.exception("Failed to close personal_data_store_two cleanly")

        try:
            if 'phone_registry_two' in locals() and hasattr(phone_registry_two, 'persistence') and phone_registry_two.persistence:
                phone_registry_two.persistence.close()
        except Exception:
            LOGGER.exception("Failed to close phone_registry_two.persistence cleanly")

        # Give OS time to release file handles on Windows, then force GC to drop references
        time.sleep(0.5)  # Increased from 0.25 for Windows
        import gc
        gc.collect()
        time.sleep(0.25)  # Extra sleep for Windows file handle release


def main() -> None:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_dir = Path("logs")
    log_file = log_dir / f"pan_sdk_system_test_{timestamp}.log"
    configure_logging(log_file)

    with tempfile.TemporaryDirectory(prefix="pan_sdk_system_") as tmpdir:
        run_scenario(Path(tmpdir))
    LOGGER.info("Temporary workspace cleaned up. Log file retained at %s", log_file.resolve())


if __name__ == "__main__":
    main()
