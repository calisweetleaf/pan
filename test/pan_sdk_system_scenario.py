"""PAN SDK end-to-end scenario runner with detailed logging and fail-loud comparisons."""

from __future__ import annotations

import io
import json
import logging
import os
import sqlite3
import sys
import tempfile
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Mapping, TextIO

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
from PAN_SDK.email_social import (
    MAIL_KIND,
    EmailSocialBlocked,
    EmailSocialCryptoError,
    EmailSocialError,
    EmailSocialNode,
    EmailSocialRelayError,
)
from PAN_SDK.master_db import MasterDatabaseError
from PAN_SDK.personal_data import PANPersonalDataStore, PANPhoneAddressRegistry
from PAN_SDK.treasury import (
    ProposalKind,
    TreasuryContractRejected,
    TreasuryError,
    TreasuryState,
    build_proof,
)
from security.sovereign_firewall import FirewallError, SovereignFirewall

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
    "treasury_fsm",
    "treasury_validators",
    "treasury_proposals",
    "master_db_docs",
    "master_db_counters",
    "master_db_sets",
    "master_db_meta",
)

SCENARIO_EXCEPTIONS = (
    AssertionError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    sqlite3.Error,
    TreasuryError,
    TreasuryContractRejected,
    EmailSocialError,
    EmailSocialBlocked,
    EmailSocialCryptoError,
    EmailSocialRelayError,
    MasterDatabaseError,
    FirewallError,
)

POI_MINT_AMOUNT = 40
CIVIC_GENESIS_MINT = 250
CIVIC_TRANSFER_AMOUNT = 50
EXPECTED_POST_POI_BALANCE = CIVIC_GENESIS_MINT - CIVIC_TRANSFER_AMOUNT + POI_MINT_AMOUNT


def _print_banner(title: str) -> None:
    """Print a section header so the terminal readout is a run report."""
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _snapshot_store(
    store: PANPersistenceStore,
    extra_components: tuple[str, ...] = (),
) -> dict[str, object]:
    """Load civic plus nation-pillar kv components from one sqlite store."""
    snapshot: dict[str, object] = {}
    for component in PERSISTENCE_COMPONENTS + extra_components:
        snapshot[component] = store.load_component(component)
    pending = store.read_state("dht_pending_transactions", "pending")
    snapshot["pending_transactions"] = pending if pending is not None else []
    metrics = store.read_state("economy_usage_metrics", "metrics")
    snapshot["usage_metrics"] = metrics if metrics is not None else {}
    return snapshot


def _personal_snapshot(store: PANPersonalDataStore) -> dict[str, object]:
    """Serialize the personal-data surface for round-trip comparison."""
    return {
        "personal_contacts": {cid: contact.to_dict() for cid, contact in store.contacts.items()},
        "personal_messages": {mid: message.to_dict() for mid, message in store.messages.items()},
        "personal_call_logs": {cid: call.to_dict() for cid, call in store.call_logs.items()},
        "personal_preferences": store.preferences.to_dict() if store.preferences else None,
    }


def _close_handle(handle: object | None, label: str) -> None:
    """Close a sqlite-backed handle if it is still open."""
    if handle is None:
        return
    closer = getattr(handle, "close", None)
    if closer is None:
        return
    try:
        closer()
    except (OSError, sqlite3.Error, RuntimeError) as exc:
        LOGGER.exception("Failed to close %s: %s", label, exc)


def _require_same_sqlite(
    left: PANPersistenceStore,
    right: PANPersistenceStore,
    label: str,
) -> None:
    """Fail loud when two owners are not on the same sqlite file."""
    if left is not right:
        raise AssertionError(f"{label} is not the civic PANPersistenceStore object")
    if left.db_path != right.db_path:
        raise AssertionError(
            f"{label} sqlite diverged: {left.db_path} vs {right.db_path}"
        )


def _exercise_nation_pillars(
    *,
    base_path: Path,
    persistence: PANPersistenceStore,
    node: DHTNode,
    node_identity: SovereignIdentity,
    citizen_identity: SovereignIdentity,
    developer_identity: SovereignIdentity,
    citizen_account: str,
    report: dict[str, Any],  # gate-shaped payload: mixed civic ids, pillar facts, snapshot sizes
) -> tuple[SovereignFirewall, SovereignFirewall, PANPersistenceStore, str]:
    """
    Run Fed mint, sealed mail, and CRDT writes on the civic sqlite store.

    EmailSocialNode is constructed explicitly. DHTNode must not own it.

    Args:
        base_path: Temporary civic workspace.
        persistence: Shared civic PANPersistenceStore.
        node: Civic DHT node that already bound treasury and master_db.
        node_identity: Node operator; also the explicit mail overlay identity.
        citizen_identity: Validator and PoI worker.
        developer_identity: Third genesis validator.
        citizen_account: Economic account that receives the PoI mint.
        report: Mutable scenario payload.

    Returns:
        Civic firewall, peer firewall, peer persistence, and civic email relay component name.
    """
    _print_banner("PHASE 1b: Nation pillars on one PANPersistenceStore")
    if node.treasury is None:
        raise AssertionError("DHTNode did not bind SovereignTreasury")
    if node.master_db is None:
        raise AssertionError("DHTNode did not bind MasterDatabase")
    if getattr(node, "email_social", None) is not None:
        raise AssertionError("EmailSocialNode must not be auto-bound onto DHTNode")
    _require_same_sqlite(persistence, node.treasury.persistence, "treasury")
    _require_same_sqlite(persistence, node.master_db.persistence, "master_db")
    print(f"shared sqlite={persistence.db_path}")
    print(f"treasury bound state={node.treasury.state.value}")
    print(f"master_db replica={node.master_db.replica_id[:12]}")
    print("email_social on DHTNode: absent (explicit construct required)")

    fw_civic = SovereignFirewall(base_path / "fw_civic.sqlite")
    fw_peer = SovereignFirewall(base_path / "fw_peer.sqlite")
    mail_civic = EmailSocialNode(node_identity, persistence, fw_civic)
    _require_same_sqlite(persistence, mail_civic.persistence, "email_social")
    if mail_civic.persistence.db_path != node.treasury.persistence.db_path:
        raise AssertionError("email sqlite path diverged from treasury")
    if mail_civic.persistence.db_path != node.master_db.persistence.db_path:
        raise AssertionError("email sqlite path diverged from master_db")

    peer_identity = SovereignIdentity("ScenarioMailPeer")
    peer_store = PANPersistenceStore(base_path=base_path / "mail_peer")
    mail_peer = EmailSocialNode(peer_identity, peer_store, fw_peer)
    mail_civic.add_peer_relay(mail_peer.relay)
    mail_peer.add_peer_relay(mail_civic.relay)
    print(
        f"explicit EmailSocialNode civic_relay={mail_civic.relay.relay_id[:12]} "
        f"peer_store={peer_store.db_path}"
    )

    treasury = node.treasury
    for identity in (node_identity, citizen_identity, developer_identity):
        treasury.register_validator(identity.identity_hash)
    genesis = treasury.seal_genesis(node_identity.identity_hash)
    print(f"seal_genesis status={genesis.status} state={treasury.state.value} quorum={treasury.quorum_threshold()}")
    if treasury.state is not TreasuryState.MINT_PHASE:
        raise AssertionError("genesis did not enter MINT_PHASE")
    if treasury.quorum_threshold() != 3:
        raise AssertionError(f"expected quorum 3, got {treasury.quorum_threshold()}")

    proof = build_proof(
        worker_identity_hash=citizen_identity.identity_hash,
        prompt="infer:civic-walkthrough",
        output="commitment-civic-1",
        verifier_identity_hashes=(node_identity.identity_hash, developer_identity.identity_hash),
    )
    proposal = treasury.submit_proposal(
        citizen_identity.identity_hash,
        ProposalKind.MINT,
        {
            "recipient_id": citizen_account,
            "amount": POI_MINT_AMOUNT,
            "poi": proof.to_mapping(),
        },
    )
    for voter in (node_identity, citizen_identity, developer_identity):
        treasury.vote(proposal.proposal_id, voter.identity_hash, True)
    executed = treasury.execute_proposal(proposal.proposal_id)
    print(f"quorum PoI mint status={executed.status} reason={executed.reason}")
    if not executed.ok:
        raise AssertionError(f"PoI mint failed: {executed.reason}")
    poi_balance = node.economic_engine.get_balance(citizen_account)
    print(f"citizen balance after PoI mint={poi_balance}")
    if poi_balance != EXPECTED_POST_POI_BALANCE:
        raise AssertionError(
            f"expected post-PoI balance {EXPECTED_POST_POI_BALANCE}, got {poi_balance}"
        )

    master_db = node.master_db
    mint_doc = {
        "proposal_id": proposal.proposal_id,
        "amount": POI_MINT_AMOUNT,
        "recipient": citizen_account,
        "treasury_state": treasury.state.value,
    }
    master_db.put("civic:mint", mint_doc)
    cycles = master_db.increment("inference_cycles", 3)
    master_db.add("validators", "chair")
    stored_doc = master_db.get("civic:mint")
    print(f"master_db civic:mint={stored_doc} inference_cycles={cycles}")
    if stored_doc != mint_doc:
        raise AssertionError("master_db did not retain the civic mint document")
    if cycles != 3:
        raise AssertionError(f"expected inference_cycles 3, got {cycles}")
    if "chair" not in set(master_db.members("validators") or []):
        raise AssertionError("master_db OR-set did not record chair")

    mail_body = f"fed minted {POI_MINT_AMOUNT} after PoI quorum"
    published = mail_civic.send_mail(
        recipient=peer_identity,
        subject="treasury-cycle",
        body=mail_body,
    )
    print(
        f"published mail packet={published.packet_id} ok={published.ok} "
        f"relays={published.details.get('relays')}"
    )
    if not published.ok:
        raise AssertionError("civic mail publish failed")
    inbox = mail_peer.fetch_mail()
    if len(inbox) != 1:
        raise AssertionError(f"expected 1 peer mail, got {len(inbox)}")
    if inbox[0].body != mail_body:
        raise AssertionError(f"peer decrypted body mismatch: {inbox[0].body!r}")
    if inbox[0].sender_hash != node_identity.identity_hash:
        raise AssertionError("peer mail sender hash mismatch")
    print(f"peer opened subject={inbox[0].subject!r} body={inbox[0].body!r}")

    social = mail_civic.broadcast_social("agora: mint cycle sealed", feed="agora")
    print(f"social packet={social.packet_id} ok={social.ok}")
    if not social.ok:
        raise AssertionError("social broadcast failed")
    feed = mail_peer.fetch_social(feed="agora")
    if len(feed) != 1:
        raise AssertionError(f"expected 1 social post, got {len(feed)}")

    relay_component = f"email_relay_{node_identity.identity_hash}"
    civic_relay_mail = mail_civic.relay.query(
        recipient_hash=peer_identity.identity_hash,
        kind=MAIL_KIND,
    )
    if len(civic_relay_mail) != 1:
        raise AssertionError("civic relay did not store sealed mail on the shared sqlite")

    operations = report["operations"]
    operations["treasury_state"] = treasury.state.value
    operations["treasury_validators"] = len(treasury.validators)
    operations["poi_mint_amount"] = POI_MINT_AMOUNT
    operations["poi_balance"] = poi_balance
    operations["poi_proposal_id"] = proposal.proposal_id
    operations["mail_packet_id"] = published.packet_id
    operations["social_packet_id"] = social.packet_id
    operations["master_db_mint"] = stored_doc
    operations["master_db_cycles"] = cycles
    operations["shared_sqlite"] = str(persistence.db_path)
    operations["email_explicit"] = True
    operations["email_not_auto_bound"] = getattr(node, "email_social", None) is None
    operations["peer_identity_hash"] = peer_identity.identity_hash
    operations["email_relay_component"] = relay_component
    print("nation pillars wrote treasury + master_db + email onto the civic sqlite")
    return fw_civic, fw_peer, peer_store, relay_component


def _verify_pillar_hydrate(
    *,
    base_path: Path,
    persistence: PANPersistenceStore,
    node: DHTNode,
    node_identity: SovereignIdentity,
    peer_identity_hash: str,
    expected_proposal_id: str,
) -> SovereignFirewall:
    """
    Reconstruct treasury, master_db, and EmailSocialNode on the reopened sqlite.

    Args:
        base_path: Temporary civic workspace.
        persistence: Reopened civic PANPersistenceStore.
        node: Reopened DHT node.
        node_identity: Same operator identity used before close.
        peer_identity_hash: Recipient of the sealed mint notice.
        expected_proposal_id: PoI mint proposal that must survive hydrate.

    Returns:
        Firewall opened for the reconstructed EmailSocialNode. Caller closes it.
    """
    _print_banner("PHASE 2b: Hydrate nation pillars from the same sqlite")
    if node.treasury is None:
        raise AssertionError("reloaded DHTNode did not bind SovereignTreasury")
    if node.master_db is None:
        raise AssertionError("reloaded DHTNode did not bind MasterDatabase")
    if getattr(node, "email_social", None) is not None:
        raise AssertionError("reloaded DHTNode auto-bound EmailSocialNode")
    _require_same_sqlite(persistence, node.treasury.persistence, "reloaded treasury")
    _require_same_sqlite(persistence, node.master_db.persistence, "reloaded master_db")
    print(
        f"reopened treasury state={node.treasury.state.value} "
        f"validators={len(node.treasury.validators)}"
    )
    if node.treasury.state is not TreasuryState.MINT_PHASE:
        raise AssertionError("treasury FSM did not hydrate MINT_PHASE")
    if len(node.treasury.validators) != 3:
        raise AssertionError("treasury validators did not hydrate")
    if expected_proposal_id not in node.treasury.proposals:
        raise AssertionError("treasury PoI proposal did not hydrate")

    hydrated_mint = node.master_db.get("civic:mint")
    cycles = node.master_db.counter_value("inference_cycles")
    print(f"reopened master_db civic:mint={hydrated_mint} cycles={cycles}")
    if not isinstance(hydrated_mint, dict):
        raise AssertionError("master_db mint document did not hydrate")
    if hydrated_mint.get("amount") != POI_MINT_AMOUNT:
        raise AssertionError(f"hydrated mint amount mismatch: {hydrated_mint}")
    if hydrated_mint.get("proposal_id") != expected_proposal_id:
        raise AssertionError("hydrated mint proposal_id mismatch")
    if cycles != 3:
        raise AssertionError(f"master_db counter did not hydrate, got {cycles}")

    fw_civic = SovereignFirewall(base_path / "fw_civic.sqlite")
    mail_civic = EmailSocialNode(node_identity, persistence, fw_civic)
    _require_same_sqlite(persistence, mail_civic.persistence, "reloaded email_social")
    stored_mail = mail_civic.relay.query(recipient_hash=peer_identity_hash, kind=MAIL_KIND)
    feed = mail_civic.fetch_social(feed="agora")
    print(f"reopened civic relay mail={len(stored_mail)} social={len(feed)}")
    if len(stored_mail) != 1:
        raise AssertionError("civic email relay did not hydrate sealed mail")
    if len(feed) != 1:
        raise AssertionError("civic social feed did not hydrate")
    return fw_civic


def run_scenario(base_path: Path) -> dict[str, Any]:
    """
    Walk one civic node through census, economy, names, personal data, and nation pillars.

    Args:
        base_path: Temporary directory that owns the civic sqlite file.

    Returns:
        Gate-shaped report with operations, persistence comparisons, and passed flag.
        Values are schema-shaped civic records (ids, snapshots, MATCH/MISMATCH).
    """
    LOGGER.info("Starting PAN SDK scenario. Persistence path: %s", base_path)
    report: dict[str, Any] = {"operations": {}, "comparisons": {}, "passed": False}
    top_old_cwd = Path.cwd()
    base_path.mkdir(parents=True, exist_ok=True)
    os.chdir(base_path)
    persistence_one = None
    persistence_two = None
    personal_data_store = None
    personal_data_store_two = None
    fw_civic = None
    fw_peer = None
    fw_civic_two = None
    peer_store = None
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
        _print_banner("PHASE 1: Civic census, economy, names, personal data")
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

        minted = node_one.economic_engine.mint_tokens(citizen.identity_hash, CIVIC_GENESIS_MINT, reason="genesis_reward")
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
            CIVIC_TRANSFER_AMOUNT,
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

        fw_civic, fw_peer, peer_store, relay_component = _exercise_nation_pillars(
            base_path=base_path,
            persistence=persistence_one,
            node=node_one,
            node_identity=node_identity,
            citizen_identity=citizen_identity,
            developer_identity=developer_identity,
            citizen_account=citizen.identity_hash,
            report=report,
        )

        LOGGER.info("--- Phase 1: Snapshotting authoritative persistence ---")
        snapshots = _snapshot_store(persistence_one, extra_components=(relay_component,))
        snapshots.update(_personal_snapshot(personal_data_store))
        report["operations"]["snapshot_sizes"] = {
            key: (len(value) if isinstance(value, dict) else 1)
            for key, value in snapshots.items()
        }

        _close_handle(fw_civic, "civic firewall")
        fw_civic = None
        _close_handle(fw_peer, "peer firewall")
        fw_peer = None
        _close_handle(peer_store, "peer persistence")
        peer_store = None
        persistence_one.close()
        persistence_one = None
        personal_data_store.close()
        personal_data_store = None

        LOGGER.info("--- Phase 2: Reloading from persistence ---")
        _print_banner("PHASE 2: Reload civic sqlite and compare snapshots")
        persistence_two = PANPersistenceStore(base_path=base_path)
        node_two = DHTNode(node_identity, persistence=persistence_two)
        node_two.citizen_registry = PANCitizenRegistry(node_identity, node_two, persistence=persistence_two)
        personal_data_store_two = PANPersonalDataStore(
            sovereign_id=citizen_identity.identity_hash,
            base_path=base_path / "personal_data",
            persistence=persistence_two,
        )
        reloaded = _snapshot_store(persistence_two, extra_components=(relay_component,))
        reloaded.update(_personal_snapshot(personal_data_store_two))

        hydrated_name = node_two.name_registry.resolve_name("testname")
        if hydrated_name is None:
            raise AssertionError("name_registry did not hydrate testname")
        LOGGER.info("Reloaded name %s target=%s", hydrated_name["name"], hydrated_name["target_identity"][:12])

        all_match = True
        mismatches: list[str] = []
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

        fw_civic_two = _verify_pillar_hydrate(
            base_path=base_path,
            persistence=persistence_two,
            node=node_two,
            node_identity=node_identity,
            peer_identity_hash=str(report["operations"]["peer_identity_hash"]),
            expected_proposal_id=str(report["operations"]["poi_proposal_id"]),
        )
        report["comparisons"]["treasury_fsm_live"] = "MATCH"
        report["comparisons"]["master_db_live"] = "MATCH"
        report["comparisons"]["email_relay_live"] = "MATCH"
        report["comparisons"]["email_not_auto_bound"] = "MATCH"

        persistence_two.close()
        persistence_two = None
        personal_data_store_two.close()
        personal_data_store_two = None
        _close_handle(fw_civic_two, "reloaded civic firewall")
        fw_civic_two = None

        report["passed"] = True
        LOGGER.info("PAN SDK scenario completed successfully. All persisted state verified.")
        print("scenario passed: civic snapshot + treasury/email/master_db shared sqlite hydrate")
        return report
    except SCENARIO_EXCEPTIONS:
        LOGGER.exception("PAN SDK scenario failed")
        report["passed"] = False
        report["error"] = traceback.format_exc()
        raise
    finally:
        os.chdir(top_old_cwd)
        for handle, label in (
            (fw_civic, "civic firewall"),
            (fw_peer, "peer firewall"),
            (fw_civic_two, "reloaded civic firewall"),
            (peer_store, "peer persistence"),
            (persistence_one, "persistence_one"),
            (persistence_two, "persistence_two"),
            (personal_data_store, "personal_data_store"),
            (personal_data_store_two, "personal_data_store_two"),
        ):
            _close_handle(handle, label)


def _narrative_markdown(report: Mapping[str, Any], timestamp: str, json_path: Path, md_path: Path, log_path: Path) -> str:
    """Build the first-person Markdown report for this run."""
    passed = bool(report.get("passed"))
    operations = report.get("operations") if isinstance(report.get("operations"), dict) else {}
    comparisons = report.get("comparisons") if isinstance(report.get("comparisons"), dict) else {}
    lines = [
        f"# PAN SDK system scenario {timestamp}",
        "",
        f"I ran `python3 test/pan_sdk_system_scenario.py` at {timestamp}.",
        f"I found passed=`{passed}`.",
        "",
        "## What I required",
        "",
        "I required one civic walkthrough to exercise SovereignTreasury, an explicit",
        "EmailSocialNode, and MasterDatabase on the same PANPersistenceStore. I did not",
        "auto-bind mail onto DHTNode. I used a real TemporaryDirectory sqlite fixture.",
        "I did not mock owners, and I did not call qemu or `_run_inference`.",
        "",
        "## What I found",
        "",
        f"I found shared sqlite `{operations.get('shared_sqlite')}`.",
        f"I found treasury state `{operations.get('treasury_state')}` with "
        f"{operations.get('treasury_validators')} validators and PoI mint "
        f"{operations.get('poi_mint_amount')} leaving balance {operations.get('poi_balance')}.",
        f"I found master_db mint document `{operations.get('master_db_mint')}` and "
        f"inference_cycles `{operations.get('master_db_cycles')}`.",
        f"I found explicit mail packet `{operations.get('mail_packet_id')}` and "
        f"email_not_auto_bound=`{operations.get('email_not_auto_bound')}`.",
        "",
        "## Operations",
        "",
        "```json",
        json.dumps(operations, indent=2, default=str),
        "```",
        "",
        "## Comparisons",
        "",
    ]
    for key, status in comparisons.items():
        lines.append(f"- `{key}`: {status}")
    if report.get("error"):
        lines.extend(["", "## Error", "", "```", str(report["error"]), "```"])
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- `{json_path}`",
            f"- `{md_path}`",
            f"- `{log_path}`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_scenario_artifacts(
    report: dict[str, Any],
    timestamp: str,
    log_text: str = "",
) -> tuple[Path, Path, Path]:
    """
    Write JSON, Markdown, log, and legacy txt artifacts for this scenario run.

    Args:
        report: Gate-shaped scenario payload.
        timestamp: Run id used in filenames.
        log_text: Captured stdout/stderr. Empty when the gate only has the report.

    Returns:
        Legacy (txt, json, md) paths so `run_pan_gate.slice_scenario` keeps working.
    """
    results_dir = ROOT_DIR / "results"
    logs_dir = ROOT_DIR / "logs"
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    txt_path = results_dir / f"pan_sdk_system_test_{timestamp}.txt"
    json_path = results_dir / f"pan_sdk_system_test_{timestamp}.json"
    md_path = results_dir / f"pan_sdk_system_test_{timestamp}.md"
    log_path = results_dir / f"pan_sdk_system_test_{timestamp}.log"
    payload = dict(report)
    payload["artifacts"] = {
        "txt": str(txt_path),
        "json": str(json_path),
        "md": str(md_path),
        "log": str(log_path),
    }
    serialized = json.dumps(payload, indent=2, default=str) + "\n"
    txt_path.write_text(serialized, encoding="utf-8")
    json_path.write_text(serialized, encoding="utf-8")
    log_body = log_text if log_text else "invoked via write_scenario_artifacts without captured stdout\n"
    log_path.write_text(log_body, encoding="utf-8")
    md_path.write_text(_narrative_markdown(payload, timestamp, json_path, md_path, log_path), encoding="utf-8")
    return txt_path, json_path, md_path


def _configure_logging_to_stream(log_file: Path, stream: TextIO) -> None:
    """Write logs to the retained log file and the captured stream."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )
    console = logging.StreamHandler(stream)
    console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)


def main() -> int:
    """Run the civic walkthrough, persist JSON/MD/LOG artifacts, and exit non-zero on failure."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = ROOT_DIR / "logs" / f"pan_sdk_system_test_{timestamp}.log"
    buffer = io.StringIO()
    _configure_logging_to_stream(log_file, buffer)
    try:
        with redirect_stdout(buffer), redirect_stderr(buffer):
            print(f"pan_sdk_system_scenario start {timestamp}")
            with tempfile.TemporaryDirectory(prefix="pan_sdk_system_") as tmpdir:
                report = run_scenario(Path(tmpdir))
            print(f"pan_sdk_system_scenario passed={report.get('passed')}")
    except SCENARIO_EXCEPTIONS as exc:
        log_text = buffer.getvalue()
        sys.stdout.write(log_text)
        report = {
            "passed": False,
            "operations": {},
            "comparisons": {},
            "error": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        }
        write_scenario_artifacts(report, timestamp, log_text)
        LOGGER.info("Log file retained at %s", log_file.resolve())
        return 1
    log_text = buffer.getvalue()
    sys.stdout.write(log_text)
    txt_path, json_path, md_path = write_scenario_artifacts(report, timestamp, log_text)
    log_path = ROOT_DIR / "results" / f"pan_sdk_system_test_{timestamp}.log"
    LOGGER.info("Temporary workspace cleaned up. Log file retained at %s", log_file.resolve())
    LOGGER.info("Artifacts: %s", [str(txt_path), str(json_path), str(md_path), str(log_path)])
    print(f"artifacts txt={txt_path}")
    print(f"artifacts json={json_path}")
    print(f"artifacts md={md_path}")
    print(f"artifacts log={log_path}")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
