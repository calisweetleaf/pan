"""PAN SDK end-to-end scenario runner with detailed logging and fail-loud comparisons."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PAN_SDK import (
    DHTNode,
    ModelManifest,
    PANCitizenRegistry,
    PANPersistenceStore,
    SovereignCommunicator,
    SovereignIdentity,
    SovereignPipeline,
    sha256_hex,
)
from PAN_SDK.personal_data import PANPersonalDataStore, PANPhoneAddressRegistry

LOGGER = logging.getLogger(__name__)

PERSISTENCE_COMPONENTS = (
    "dht_data",
    "dht_ledger",
    "economy_accounts",
    "governance_proposals",
    "governance_policies",
    "citizens",
    "applications",
    "name_registry",
    "phone_addresses",
)


def configure_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)


def _snapshot_store(store: PANPersistenceStore) -> Dict[str, Any]:
    snapshot = {component: store.load_component(component) for component in PERSISTENCE_COMPONENTS}
    pending = store.read_state("dht_pending_transactions", "pending")
    snapshot["pending_transactions"] = pending if pending is not None else []
    metrics = store.read_state("economy_usage_metrics", "metrics")
    snapshot["usage_metrics"] = metrics if metrics is not None else {}
    return snapshot


def _personal_snapshot(store: PANPersonalDataStore) -> Dict[str, Any]:
    return {
        "personal_contacts": {cid: contact.to_dict() for cid, contact in store.contacts.items()},
        "personal_messages": {mid: message.to_dict() for mid, message in store.messages.items()},
        "personal_call_logs": {cid: call.to_dict() for cid, call in store.call_logs.items()},
        "personal_preferences": store.preferences.to_dict() if store.preferences else None,
    }


def run_scenario(base_path: Path) -> Dict[str, Any]:
    LOGGER.info("Starting PAN SDK scenario. Persistence path: %s", base_path)
    report: Dict[str, Any] = {"operations": {}, "comparisons": {}, "passed": False}
    top_old_cwd = Path.cwd()
    base_path.mkdir(parents=True, exist_ok=True)
    os.chdir(base_path)
    persistence_one = None
    persistence_two = None
    personal_data_store = None
    personal_data_store_two = None
    try:
        node_identity = SovereignIdentity("ScenarioNode")
        citizen_identity = SovereignIdentity("ScenarioCitizen")
        developer_identity = SovereignIdentity("ScenarioDeveloper")
        model_identity = SovereignIdentity("ScenarioModel")
        distributor_identity = SovereignIdentity("ScenarioDistributor")

        persistence_one = PANPersistenceStore(base_path=base_path)
        node_one = DHTNode(node_identity, persistence=persistence_one)
        civic_registry = PANCitizenRegistry(node_identity, node_one, persistence=persistence_one)
        node_one.citizen_registry = civic_registry

        LOGGER.info("Initializing communicator, manifest, and pipeline")
        communicator = SovereignCommunicator(citizen_identity)
        manifest = ModelManifest(
            "test_model",
            "dummy_model_hash",
            model_identity.get_public_key_pem(),
            model_identity,
        )
        pipeline = SovereignPipeline(distributor_identity, dht_node=node_one)

        packet = communicator.create_packet("test_packet", {"test": "data"}, metadata={"version": "1.0"})
        verified = communicator.verify_packet(packet, citizen_identity.get_public_key_pem())
        LOGGER.info("Created test packet %s verified=%s", packet.packet_id[:12], verified)
        if not verified:
            raise AssertionError("packet verification failed")

        manifest_verified = manifest.verify_manifest(model_identity.get_public_key_pem())
        LOGGER.info("Manifest verification: %s", manifest_verified)
        if not manifest_verified:
            raise AssertionError("scenario model manifest failed verification")

        pipeline.register_model("test_model", "/dummy/model/path", model_identity)

        personal_data_store = PANPersonalDataStore(
            sovereign_id=citizen_identity.identity_hash,
            base_path=base_path / "personal_data",
            persistence=persistence_one,
        )
        phone_registry = PANPhoneAddressRegistry(persistence=persistence_one)

        LOGGER.info("--- Phase 1: Initial operations ---")
        if not node_one.store("registry:name:alice", {"display_name": "Alice"}, require_consensus=False):
            raise AssertionError("failed to store alice registry record")
        if not node_one.store("registry:name:bob", {"display_name": "Bob"}, require_consensus=False):
            raise AssertionError("failed to store bob registry record")

        citizen = node_one.citizen_registry.register_citizen(citizen_identity, citizen_type="admin")
        developer = node_one.citizen_registry.register_citizen(developer_identity, citizen_type="developer")
        if citizen is None or developer is None:
            raise AssertionError("citizen registration failed")
        report["operations"]["citizen_id"] = citizen.citizen_id
        report["operations"]["developer_id"] = developer.citizen_id

        node_one.governance_council.register_member(citizen.identity_hash, role="admin", voting_power=5)

        app = node_one.citizen_registry.register_app(
            "sovereign-feed",
            developer_identity,
            app_metadata={"category": "media"},
        )
        if app is None:
            raise AssertionError("application registration failed")
        report["operations"]["app_id"] = app.app_id

        minted = node_one.economic_engine.mint_tokens(citizen.identity_hash, 250, reason="genesis_reward")
        if not minted:
            raise AssertionError("genesis mint failed")
        node_one.economic_engine.record_usage(
            consumer_id=citizen.citizen_id,
            provider_id=app.app_id,
            service_type="app_usage",
            quantity=3,
            metadata={"app_name": "sovereign-feed"},
            bill_consumer=False,
        )

        neighbor_identity = SovereignIdentity("NeighborNode")
        node_one.add_neighbor(neighbor_identity.identity_hash, "127.0.0.1", 8463)
        closest = node_one.get_closest_nodes(sha256_hex("some_key"))
        LOGGER.info("Closest nodes: %d", len(closest))

        consensus_result = node_one.store("consensus_test", {"consensus": "data"}, require_consensus=True)
        LOGGER.info("Consensus store result: %s", consensus_result)
        if not consensus_result:
            raise AssertionError("consensus store failed")

        name_registered = node_one.name_registry.register_name(
            "testname",
            citizen.identity_hash,
            "http://test.com",
        )
        LOGGER.info("Name registration: %s", name_registered)
        if not name_registered:
            raise AssertionError("name registration failed")
        resolved_name = node_one.name_registry.resolve_name("testname")
        if resolved_name is None:
            raise AssertionError("name resolution failed immediately after register")
        report["operations"]["registered_name"] = "testname"

        balance = node_one.economic_engine.get_balance(citizen.identity_hash)
        LOGGER.info("Citizen balance: %d", balance)
        transfer = node_one.economic_engine.transfer_tokens(
            citizen.identity_hash,
            developer.identity_hash,
            50,
            "test_transfer",
        )
        LOGGER.info("Token transfer: %s", transfer["success"])
        if not transfer.get("success"):
            raise AssertionError(f"token transfer failed: {transfer}")

        open_proposals = node_one.governance_council.list_open_proposals()
        LOGGER.info("Open proposals: %d", len(open_proposals))

        article_id = node_one.governance_council.constitution.add_article("Test Article", "Test body", citizen_identity)
        LOGGER.info("Added constitution article: %s", article_id[:12])

        policy_id = node_one.governance_council.policy_registry.register_policy(
            "Test Policy",
            "Policy body",
            citizen.identity_hash,
        )
        LOGGER.info("Registered policy: %s", policy_id[:12])

        got_citizen = node_one.citizen_registry.get_citizen(citizen.citizen_id)
        if got_citizen is None:
            raise AssertionError("get_citizen failed")

        use_result = node_one.citizen_registry.use_app(citizen.citizen_id, app.app_id)
        if not use_result.get("success"):
            raise AssertionError(f"use_app failed: {use_result}")
        LOGGER.info("App usage recorded tokens=%s", use_result.get("tokens_earned"))

        proposal = node_one.governance_council.submit_proposal(
            proposer_id=citizen.identity_hash,
            title="Adopt Foundational Charter",
            proposal_type="policy",
            content={"body": "Foundational civic principles."},
        )
        node_one.governance_council.cast_vote(proposal.proposal_id, citizen.identity_hash, "YES")
        node_one.governance_council.finalize_proposal(proposal.proposal_id, force=True)
        got_proposal = node_one.governance_council.get_proposal(proposal.proposal_id)
        if got_proposal is None:
            raise AssertionError("get_proposal failed")
        report["operations"]["proposal_id"] = proposal.proposal_id

        LOGGER.info("Testing personal data operations...")
        contact = personal_data_store.add_contact(
            display_name="Test Contact",
            pan_phone_address="pan:test:voice",
            phone_numbers=["+1234567890"],
            email_addresses=["test@example.com"],
            tags=["test"],
        )
        message = personal_data_store.send_message(
            recipient_sovereign_id=developer.identity_hash,
            content="Test message",
            message_type="chat",
        )
        call_log = personal_data_store.log_call(
            caller_sovereign_id=citizen.identity_hash,
            recipient_sovereign_id=developer.identity_hash,
            call_type="voice",
            direction="outgoing",
            duration_seconds=60,
        )
        prefs = personal_data_store.get_preferences()
        prefs.theme = "light"
        personal_data_store.save_preferences(prefs)
        phone_address = phone_registry.assign_phone_address(
            sovereign_id=citizen.identity_hash,
            vm_id="test_vm",
            network_hash="test_net",
            identity_motif="test_motif",
        )
        resolved_phone = phone_registry.resolve_address(phone_address)
        if resolved_phone is None:
            raise AssertionError("phone address resolution failed")
        LOGGER.info(
            "personal contact=%s message=%s call=%s phone=%s",
            contact.contact_id[:12],
            message.message_id[:12],
            call_log.call_id[:12],
            phone_address,
        )

        LOGGER.info("--- Phase 1: Snapshotting authoritative persistence ---")
        snapshots = _snapshot_store(persistence_one)
        snapshots.update(_personal_snapshot(personal_data_store))
        report["operations"]["snapshot_sizes"] = {
            key: (len(value) if isinstance(value, dict) else 1)
            for key, value in snapshots.items()
        }

        persistence_one.close()
        persistence_one = None
        personal_data_store.close()
        personal_data_store = None

        LOGGER.info("--- Phase 2: Reloading from persistence ---")
        persistence_two = PANPersistenceStore(base_path=base_path)
        node_two = DHTNode(node_identity, persistence=persistence_two)
        node_two.citizen_registry = PANCitizenRegistry(node_identity, node_two, persistence=persistence_two)
        personal_data_store_two = PANPersonalDataStore(
            sovereign_id=citizen_identity.identity_hash,
            base_path=base_path / "personal_data",
            persistence=persistence_two,
        )
        reloaded = _snapshot_store(persistence_two)
        reloaded.update(_personal_snapshot(personal_data_store_two))

        hydrated_name = node_two.name_registry.resolve_name("testname")
        if hydrated_name is None:
            raise AssertionError("name_registry did not hydrate testname")
        LOGGER.info("Reloaded name %s target=%s", hydrated_name["name"], hydrated_name["target_identity"][:12])

        all_match = True
        mismatches: List[str] = []
        for key, original in snapshots.items():
            current = reloaded.get(key)
            matched = original == current
            report["comparisons"][key] = "MATCH" if matched else "MISMATCH"
            if matched:
                LOGGER.info("State verified for %s", key)
            else:
                all_match = False
                mismatches.append(key)
                LOGGER.error("Mismatch detected for %s", key)
                LOGGER.error("Original type=%s keys=%s", type(original).__name__, list(original) if isinstance(original, dict) else original)
                LOGGER.error("Reloaded type=%s keys=%s", type(current).__name__, list(current) if isinstance(current, dict) else current)

        if not all_match:
            raise AssertionError(f"PAN SDK scenario state mismatch: {mismatches}")

        persistence_two.close()
        persistence_two = None
        personal_data_store_two.close()
        personal_data_store_two = None

        report["passed"] = True
        LOGGER.info("PAN SDK scenario completed successfully. All persisted state verified.")
        return report
    except Exception:
        LOGGER.exception("PAN SDK scenario failed")
        report["passed"] = False
        report["error"] = traceback.format_exc()
        raise
    finally:
        os.chdir(top_old_cwd)
        for handle in (persistence_one, persistence_two):
            if handle is None:
                continue
            try:
                handle.close()
            except Exception:
                LOGGER.exception("Failed to close persistence handle")
        for store in (personal_data_store, personal_data_store_two):
            if store is None:
                continue
            try:
                store.close()
            except Exception:
                LOGGER.exception("Failed to close personal data store")


def write_scenario_artifacts(report: Dict[str, Any], timestamp: str) -> Tuple[Path, Path, Path]:
    results_dir = ROOT_DIR / "results"
    logs_dir = ROOT_DIR / "logs"
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    txt_path = results_dir / f"pan_sdk_system_test_{timestamp}.txt"
    json_path = results_dir / f"pan_sdk_system_test_{timestamp}.json"
    md_path = results_dir / f"pan_sdk_system_test_{timestamp}.md"
    txt_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [
        f"# PAN SDK system scenario {timestamp}",
        "",
        f"Passed: {report.get('passed')}",
        "",
        "## Operations",
        "",
        "```json",
        json.dumps(report.get("operations", {}), indent=2, default=str),
        "```",
        "",
        "## Comparisons",
        "",
    ]
    for key, status in report.get("comparisons", {}).items():
        lines.append(f"- `{key}`: {status}")
    if report.get("error"):
        lines.extend(["", "## Error", "", "```", str(report["error"]), "```"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return txt_path, json_path, md_path


def main() -> None:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = ROOT_DIR / "logs" / f"pan_sdk_system_test_{timestamp}.log"
    configure_logging(log_file)
    try:
        with tempfile.TemporaryDirectory(prefix="pan_sdk_system_") as tmpdir:
            report = run_scenario(Path(tmpdir))
    except Exception as exc:
        report = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        write_scenario_artifacts(report, timestamp)
        LOGGER.info("Log file retained at %s", log_file.resolve())
        raise SystemExit(1)
    paths = write_scenario_artifacts(report, timestamp)
    LOGGER.info("Temporary workspace cleaned up. Log file retained at %s", log_file.resolve())
    LOGGER.info("Artifacts: %s", [str(path) for path in paths])
    raise SystemExit(0 if report.get("passed") else 1)


if __name__ == "__main__":
    main()
