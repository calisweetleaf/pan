"""Direct consumer for the planetary immune system.

Real tempdir USMS + SQLite firewall ledger + two PAN DHT nodes.
No mocks. Prints a run report and writes JSON/MD/LOG artifacts.
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Callable

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PAN_SDK import SovereignCommunicator, SovereignIdentity, UnifiedDataPacket
from memory.unified_memory_system import (
    LinkageTypeEnum,
    MemoryAccessError,
    NodeKindEnum,
    SovereignIdentityError,
    UnifiedMemoryError,
)
from security.defensive_offensive_bridge import DefensiveOffensiveBridge, ThreatLevel
from security.defensive_sovereignty import (
    APIConfigurationLoader,
    BlockchainThreatIntelligence,
    NetworkThreatMonitor,
    SecondCombatChainRetiredError,
    SovereigntyCoordinator,
    ThreatDetectionModule,
)
from security.reactive_offense import NetworkJammer, TracebackHunter
from security.planetary_immune_system import (
    BulletinVerificationError,
    EREBUS_TOWER_IDS,
    ImmuneSystemError,
    ImmuneSystemNotBoundError,
    PlanetaryImmuneSystem,
    ROELevel,
)
from security.sovereign_firewall import (
    FirewallError,
    InspectionAction,
    InspectionLane,
    LegacyInternetEgressError,
    SovereignFirewall,
    THREAT_BULLETIN_KIND,
)


CheckFn = Callable[[dict[str, object]], None]


class CheckFailure(Exception):
    """A named immune-system check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _make_packet(
    identity: SovereignIdentity,
    kind: str,
    content: dict[str, object],
) -> UnifiedDataPacket:
    """Sign a packet with a real PAN identity."""
    communicator = SovereignCommunicator(identity)
    return communicator.create_packet(kind, content)


def check_firewall_blocks_telemetry(details: dict[str, object]) -> None:
    """EGRESS_LEGACY drops tracker payloads and ledgers the drop."""
    with tempfile.TemporaryDirectory(prefix="fw_telemetry_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        identity = SovereignIdentity("FirewallProbe")
        try:
            packet = _make_packet(
                identity,
                "METRICS_UPLOAD",
                {"message": "export user_activity to google-analytics"},
            )
            verdict = firewall.inspect_packet(packet, lane=InspectionLane.EGRESS_LEGACY)
            print(f"telemetry action={verdict.action.value} reason={verdict.reason}")
            if not verdict.blocked:
                raise CheckFailure("telemetry packet was allowed")
            if verdict.reason not in {"telemetry_dictionary", "telemetry_regex"}:
                raise CheckFailure(f"unexpected telemetry reason: {verdict.reason}")
            events = firewall.ledger_events(limit=5)
            if not events:
                raise CheckFailure("firewall ledger is empty after a block")
            details["telemetry_reason"] = verdict.reason
            details["telemetry_ledger_rows"] = len(events)
        finally:
            firewall.close()


def check_firewall_allows_civic_chat(details: dict[str, object]) -> None:
    """A civic chat packet is allowed on EGRESS_LEGACY."""
    with tempfile.TemporaryDirectory(prefix="fw_chat_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        identity = SovereignIdentity("FirewallProbe")
        try:
            packet = _make_packet(
                identity,
                "CHAT_MESSAGE",
                {"message": "hello from the sovereign mesh"},
            )
            verdict = firewall.inspect_packet(packet)
            print(f"civic chat action={verdict.action.value}")
            if verdict.blocked:
                raise CheckFailure(f"civic chat blocked: {verdict.reason}")
            details["civic_chat_allowed"] = True
        finally:
            firewall.close()


def check_inspect_content_compresses_secrets(details: dict[str, object]) -> None:
    """Pre-packet inspection envelopes secrets instead of shipping plaintext."""
    with tempfile.TemporaryDirectory(prefix="fw_compress_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        try:
            verdict = firewall.inspect_content(
                {"password": "correct-horse-battery", "note": "citizen vault"},
                lane=InspectionLane.EGRESS_LEGACY,
            )
            print(f"secret preflight action={verdict.action.value}")
            if verdict.action is not InspectionAction.COMPRESS:
                raise CheckFailure(f"expected COMPRESS, got {verdict.action.value}")
            envelope = verdict.sanitized_content
            if not isinstance(envelope, dict) or envelope.get("lacka_envelope") is not True:
                raise CheckFailure("compress path did not return a lacka envelope")
            if "correct-horse-battery" in json.dumps(envelope):
                raise CheckFailure("plaintext secret survived compression")
            details["compressed_bytes"] = envelope.get("compressed_bytes")
            details["original_bytes"] = envelope.get("original_bytes")
        finally:
            firewall.close()


def check_signed_secret_packet_is_blocked(details: dict[str, object]) -> None:
    """inspect_packet never mutates a signed packet; secrets fail closed."""
    with tempfile.TemporaryDirectory(prefix="fw_signed_secret_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        identity = SovereignIdentity("FirewallProbe")
        try:
            packet = _make_packet(
                identity,
                "DATA_TRANSFER",
                {"password": "should-not-cross-the-border"},
            )
            original = dict(packet.content)
            verdict = firewall.inspect_packet(packet)
            print(f"signed secret action={verdict.action.value} reason={verdict.reason}")
            if not verdict.blocked:
                raise CheckFailure("signed secret packet was allowed")
            if packet.content != original:
                raise CheckFailure("inspect_packet mutated a signed packet")
            details["signed_secret_blocked"] = True
        finally:
            firewall.close()


def check_identity_blocklist(details: dict[str, object]) -> None:
    """Blocked identities cannot send packets."""
    with tempfile.TemporaryDirectory(prefix="fw_block_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        hostile = SovereignIdentity("HostileNode")
        try:
            firewall.block_identity(hostile.identity_hash, reason="test_block")
            packet = _make_packet(hostile, "CHAT_MESSAGE", {"message": "hello"})
            verdict = firewall.inspect_packet(packet)
            print(f"blocklist action={verdict.action.value}")
            if verdict.reason != "identity_blocklist":
                raise CheckFailure(f"expected identity_blocklist, got {verdict.reason}")
            details["blocked_identity"] = hostile.identity_hash[:12]
        finally:
            firewall.close()


def check_memory_survives_restart(details: dict[str, object]) -> None:
    """USMS threat events survive process restart via the same runtime root."""
    with tempfile.TemporaryDirectory(prefix="immune_restart_", ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        first = None
        second = None
        try:
            first = PlanetaryImmuneSystem(root, node_name="immune-alpha")
            record = first.share_intelligence(
                {
                    "threat_type": "polymorphic_loader_v3",
                    "confidence": 0.91,
                    "actionable": True,
                    "vector": "network",
                    "summary": "novel loader dropped a packed beacon",
                },
                source="defensive_sovereignty",
            )
            print(
                f"first share intel_id={record.intel_id} event={record.event_node_id[:12]} "
                f"belief={record.belief_node_id[:12] if record.belief_node_id else None} "
                f"dht={record.bulletin_dht_key}"
            )
            if record.belief_node_id is None:
                raise CheckFailure("high-confidence share did not create a BELIEF node")
            if record.bulletin_dht_key is None:
                raise CheckFailure("high-confidence share did not broadcast a bulletin")
            details["intel_id"] = record.intel_id
            details["event_node_id"] = record.event_node_id
            details["belief_node_id"] = record.belief_node_id
            details["bulletin_dht_key"] = record.bulletin_dht_key
            first.close()
            first = None
            second = PlanetaryImmuneSystem(root, node_name="immune-alpha")
            hits = second.get_relevant_intelligence(
                {"threat_type": "polymorphic_loader_v3"}
            )
            print(f"restart search hits={len(hits)}")
            if not hits:
                raise CheckFailure("USMS amnesia after restart")
            recovered_ids = {str(item.get("intel_id")) for item in hits}
            if details["intel_id"] not in recovered_ids:
                raise CheckFailure("restart search missed the original intel_id")
            node = second.memory.retrieve_memory_node(
                str(details["event_node_id"]),
                requester=second.memory_identity,
            )
            if node is None:
                raise CheckFailure("event node missing after restart")
            details["restart_hits"] = len(hits)
        finally:
            if first is not None:
                first.close()
            if second is not None:
                second.close()


def check_peer_ingests_bulletin(details: dict[str, object]) -> None:
    """Peer ingest reconstructs origin ROE and neural_activation from the signed bulletin."""
    with tempfile.TemporaryDirectory(prefix="immune_mesh_", ignore_cleanup_errors=True) as tmpdir:
        alpha_root = Path(tmpdir) / "alpha"
        bravo_root = Path(tmpdir) / "bravo"
        alpha = None
        bravo = None
        try:
            alpha = PlanetaryImmuneSystem(alpha_root, node_name="immune-alpha")
            bravo = PlanetaryImmuneSystem(bravo_root, node_name="immune-bravo")
            record = alpha.share_intelligence(
                {
                    "threat_type": "zero_day_loader",
                    "confidence": 0.88,
                    "actionable": True,
                    "summary": "zero-day loader observed on the civic bus",
                },
                source="defensive_sovereignty",
            )
            if record.bulletin_dht_key is None:
                raise CheckFailure("alpha did not broadcast")
            packet_dict = alpha.lookup_bulletin(record.bulletin_dht_key)
            if packet_dict is None:
                raise CheckFailure("alpha DHT lookup missed the bulletin")
            ingested = bravo.ingest_bulletin(packet_dict)
            print(
                f"bravo ingested intel_id={ingested.intel_id} "
                f"event={ingested.event_node_id[:12]}"
            )
            packet_content = packet_dict.get("content")
            if not isinstance(packet_content, dict):
                raise CheckFailure("bulletin packet missing content mapping")
            if record.belief_node_id is None:
                raise CheckFailure("alpha share did not persist a BELIEF")
            origin_belief = alpha.memory.retrieve_memory_node(
                record.belief_node_id, requester=alpha.memory_identity
            )
            if origin_belief is None:
                raise CheckFailure("alpha BELIEF missing after broadcast")
            origin_roe = origin_belief.content.get("roe_level")
            origin_activation = float(origin_belief.content.get("neural_activation") or 0.0)
            bulletin_activation = float(packet_content.get("neural_activation") or -1.0)
            print(
                f"origin roe={origin_roe} activation={origin_activation} "
                f"bulletin_roe={packet_content.get('roe_level')} "
                f"ingested_roe={ingested.roe_level}"
            )
            if packet_content.get("roe_level") != origin_roe:
                raise CheckFailure("bulletin dropped origin ROE")
            if abs(bulletin_activation - origin_activation) > 1e-9:
                raise CheckFailure("bulletin dropped neural_activation")
            if packet_content.get("pan_identity_hash") == packet_content.get("usms_author_id"):
                raise CheckFailure("bulletin collapsed PAN RSA hash into USMS author id")
            if ingested.belief_node_id is None:
                raise CheckFailure("bravo ingest did not persist a BELIEF")
            ingested_belief = bravo.memory.retrieve_memory_node(
                ingested.belief_node_id, requester=bravo.memory_identity
            )
            if ingested_belief is None:
                raise CheckFailure("bravo BELIEF missing after ingest")
            if ingested_belief.content.get("roe_level") != origin_roe:
                raise CheckFailure("ingested BELIEF dropped origin ROE")
            ingested_activation = float(ingested_belief.content.get("neural_activation") or -1.0)
            if abs(ingested_activation - origin_activation) > 1e-9:
                raise CheckFailure("ingested BELIEF dropped neural_activation")
            if ingested.roe_level != origin_roe:
                raise CheckFailure("ingested IntelligenceRecord dropped origin ROE")
            if abs(ingested.neural_activation - origin_activation) > 1e-9:
                raise CheckFailure("ingested IntelligenceRecord dropped neural_activation")
            if ingested.bulletin_dht_key is not None:
                raise CheckFailure("ingest re-broadcast a bulletin")
            if ingested_belief.content.get("roe_neutralize") is True:
                raise CheckFailure("peer ingest must not persist NEUTRALIZE from this share")
            if packet_content.get("human_authorized") is not False:
                raise CheckFailure("unauthorized deceive bulletin claimed human_authorized")
            if ingested_belief.content.get("human_authorized") is not False:
                raise CheckFailure("ingested BELIEF invented human authorization")
            hits = bravo.get_relevant_intelligence({"threat_type": "zero_day_loader"})
            if not hits:
                raise CheckFailure("bravo semantic search missed ingested bulletin")
            details["peer_ingested_intel_id"] = ingested.intel_id
            details["peer_hits"] = len(hits)
            details["packet_kind"] = packet_dict.get("kind")
            details["bulletin_roe_level"] = packet_content.get("roe_level")
            details["ingested_roe_level"] = ingested.roe_level
            details["ingested_neural_activation"] = ingested.neural_activation
            details["identities_distinct"] = True
            if ingested.tower_competition_node_id is None:
                raise CheckFailure("bravo ingest did not attach local Erebus towers")
            if "tower_allocations" in packet_content:
                raise CheckFailure("bulletin protocol expanded with tower_allocations")
            bravo_towers = bravo.list_erebus_towers()
            if set(bravo_towers) != set(EREBUS_TOWER_IDS):
                raise CheckFailure(f"bravo missing standing towers: {bravo_towers}")
            details["peer_tower_competition"] = ingested.tower_competition_node_id
            if details["packet_kind"] != THREAT_BULLETIN_KIND:
                raise CheckFailure(f"unexpected bulletin kind {details['packet_kind']}")
        finally:
            if alpha is not None:
                alpha.close()
            if bravo is not None:
                bravo.close()


def check_contradiction_and_campaign_entangle(details: dict[str, object]) -> None:
    """Failed countermeasures write CONTRADICTION; three campaign vectors entangle."""
    with tempfile.TemporaryDirectory(prefix="immune_campaign_", ignore_cleanup_errors=True) as tmpdir:
        immune = None
        try:
            immune = PlanetaryImmuneSystem(Path(tmpdir), node_name="immune-campaign")
            last = None
            for vector in ("network", "filesystem", "memory"):
                last = immune.share_intelligence(
                    {
                        "threat_type": "coordinated_campaign",
                        "campaign_id": "campaign-omega",
                        "vector": vector,
                        "confidence": 0.8,
                        "actionable": True,
                        "summary": f"campaign omega hit {vector}",
                    },
                    source="defensive_sovereignty",
                )
                print(f"campaign vector={vector} event={last.event_node_id[:12]}")
            if last is None or last.belief_node_id is None:
                raise CheckFailure("campaign share failed to produce a belief")
            if last.entanglement_id is None:
                raise CheckFailure("third campaign vector did not quantum-entangle")
            failure = immune.record_countermeasure_failure(
                last.belief_node_id,
                "countermeasure failed against campaign omega",
                {"reason": "peer already rotated implants"},
            )
            contradiction_targets = failure.linkage_manifest.get(
                LinkageTypeEnum.CONTRADICTION,
                [],
            )
            print(
                f"contradiction node={failure.node_id[:12]} "
                f"targets={contradiction_targets}"
            )
            if last.belief_node_id not in contradiction_targets:
                raise CheckFailure("failure EVENT is not CONTRADICTION-linked to the belief")
            details["entanglement_id"] = last.entanglement_id
            details["contradiction_node_id"] = failure.node_id
            details["contradictions"] = immune.metrics["contradictions"]
        finally:
            if immune is not None:
                immune.close()


def check_legacy_ip_routing_blocked(details: dict[str, object]) -> None:
    """Legacy ISP routing artifacts never leave through EGRESS_LEGACY."""
    with tempfile.TemporaryDirectory(prefix="fw_route_") as tmpdir:
        firewall = SovereignFirewall(Path(tmpdir) / "ledger.sqlite")
        identity = SovereignIdentity("FirewallProbe")
        try:
            packet = _make_packet(
                identity,
                "ROUTE_HINT",
                {"next_hop": "isp-gateway", "message": "please route via carrier"},
            )
            verdict = firewall.inspect_packet(packet, lane=InspectionLane.EGRESS_LEGACY)
            print(f"routing action={verdict.action.value} reason={verdict.reason}")
            if verdict.reason != "legacy_routing_artifact":
                raise CheckFailure(f"expected legacy_routing_artifact, got {verdict.reason}")
            details["routing_blocked"] = True
        finally:
            firewall.close()


def check_roe_ladder_persists_through_bridge(details: dict[str, object]) -> None:
    """D/O process_threat_event writes ROE DECEIVE into USMS; it survives reopen."""
    with tempfile.TemporaryDirectory(prefix="immune_roe_", ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        bridge = None
        reopened = None
        try:
            bridge = DefensiveOffensiveBridge(runtime_root=root)
            response = bridge.process_threat_event(
                ThreatLevel.MEDIUM,
                {
                    "threat_type": "credential_harvester",
                    "confidence": 0.55,
                    "attack_vector": "phishing",
                    "summary": "harvesting civic credentials on the mesh",
                },
                source="defensive_sovereignty",
            )
            print(
                f"bridge threat_id={response.threat_id} "
                f"mapped_roe={getattr(response.roe_level, 'name', response.roe_level)}"
            )
            immune = bridge.threat_intelligence
            hits = immune.get_relevant_intelligence({"threat_type": "credential_harvester"})
            if not hits:
                raise CheckFailure("bridge share did not land in USMS")
            row = hits[0]
            belief_id = str(row.get("belief_node_id") or "")
            if not belief_id:
                raise CheckFailure("USMS hit missing belief_node_id")
            belief = immune.memory.retrieve_memory_node(
                belief_id, requester=immune.memory_identity
            )
            if belief is None:
                raise CheckFailure("ROE BELIEF missing after bridge share")
            print(
                f"belief roe_level={belief.content.get('roe_level')} "
                f"deceive={belief.content.get('roe_deceive')} "
                f"activation={belief.content.get('neural_activation')}"
            )
            if belief.content.get("roe_level") != ROELevel.DECEIVE.value:
                raise CheckFailure(
                    f"expected roe_deceive, got {belief.content.get('roe_level')}"
                )
            if belief.content.get("roe_deceive") is not True:
                raise CheckFailure("roe_deceive flag was not persisted")
            if belief.content.get("roe_neutralize") is True:
                raise CheckFailure("MEDIUM threat must not persist NEUTRALIZE")
            details["roe_level"] = belief.content.get("roe_level")
            details["neural_activation"] = belief.content.get("neural_activation")
            details["belief_node_id"] = belief_id
            intel_id = str(row.get("intel_id") or "")
            immune.close()
            bridge.stop_coordination()
            bridge = None
            reopened = PlanetaryImmuneSystem(root, node_name="immune-roe-reopen")
            recovered = reopened.get_relevant_intelligence(
                {"threat_type": "credential_harvester"}
            )
            recovered_ids = {str(item.get("intel_id")) for item in recovered}
            if intel_id not in recovered_ids:
                raise CheckFailure("ROE intelligence did not survive reopen")
            details["restart_recovered"] = True
        finally:
            if bridge is not None:
                try:
                    bridge.threat_intelligence.close()
                except (ImmuneSystemError, OSError, RuntimeError):
                    pass
                bridge.stop_coordination()
            if reopened is not None:
                reopened.close()


def check_neutralize_requires_human_authorization(details: dict[str, object]) -> None:
    """ROE L4 without human authorization fails loud and never becomes an external action."""
    with tempfile.TemporaryDirectory(prefix="immune_l4_", ignore_cleanup_errors=True) as tmpdir:
        immune = None
        try:
            immune = PlanetaryImmuneSystem(Path(tmpdir), node_name="immune-l4")
            try:
                immune.share_intelligence(
                    {
                        "threat_type": "external_host_exploit",
                        "confidence": 0.99,
                        "roe_level": ROELevel.NEUTRALIZE.value,
                        "human_authorized": False,
                    },
                    source="reactive_offense",
                )
            except ImmuneSystemError as exc:
                print(f"share L4 denied: {exc}")
                details["share_denied"] = str(exc)
            else:
                raise CheckFailure("L4 share without human auth was allowed")
            observe = immune.share_intelligence(
                {
                    "threat_type": "scanner_noise",
                    "confidence": 0.2,
                    "summary": "benign scanner",
                },
                source="defensive_sovereignty",
            )
            if observe.event_node_id == "":
                raise CheckFailure("observe share did not persist an event")
            try:
                immune.record_roe_decision(
                    event_node_id=observe.event_node_id,
                    roe_level=ROELevel.NEUTRALIZE.value,
                    human_authorized=False,
                )
            except ImmuneSystemError as exc:
                print(f"record L4 denied: {exc}")
                details["record_denied"] = str(exc)
            else:
                raise CheckFailure("record_roe_decision allowed L4 without human auth")
            if "human authorization" not in str(details.get("share_denied") or "").lower():
                raise CheckFailure("L4 deny did not name human authorization")
            details["external_host_action"] = False
        finally:
            if immune is not None:
                immune.close()


def check_erebus_towers_bind_usms(details: dict[str, object]) -> None:
    """Standing Erebus towers are USMS META nodes bound to the PAN/USMS identity pair."""
    with tempfile.TemporaryDirectory(prefix="immune_towers_", ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        first = None
        second = None
        try:
            first = PlanetaryImmuneSystem(root, node_name="immune-towers")
            if first.pan_identity.identity_hash == first.memory_identity.agent_id:
                raise CheckFailure("PAN RSA hash collapsed into USMS Ed25519 agent_id")
            towers = first.list_erebus_towers()
            print(f"standing towers={towers}")
            if set(towers) != set(EREBUS_TOWER_IDS):
                raise CheckFailure(f"expected four towers, got {sorted(towers)}")
            binding = first.persistence.read_state("immune_meta", "identity_binding")
            if not isinstance(binding, dict) or not binding.get("node_id"):
                raise CheckFailure("identity binding META missing")
            binding_id = str(binding["node_id"])
            for tower_id, node_id in towers.items():
                node = first.memory.retrieve_memory_node(
                    node_id, requester=first.memory_identity
                )
                if node is None:
                    raise CheckFailure(f"tower {tower_id} node missing")
                if node.kind != NodeKindEnum.META:
                    raise CheckFailure(f"tower {tower_id} is {node.kind}, not META")
                if node.content.get("tower_kind") != "erebus_cognitive_tower":
                    raise CheckFailure(f"tower {tower_id} missing tower_kind")
                bound = node.linkage_manifest.get(LinkageTypeEnum.COHERENCE_BOUND, [])
                if binding_id not in bound:
                    raise CheckFailure(f"tower {tower_id} is not COHERENCE_BOUND to identity")
                print(
                    f"tower {tower_id} node={node_id[:12]} kind={node.kind.value} "
                    f"bound={binding_id[:12]}"
                )
            details["tower_ids"] = dict(towers)
            details["identities_distinct"] = True
            first.close()
            first = None
            second = PlanetaryImmuneSystem(root, node_name="immune-towers")
            recovered = second.list_erebus_towers()
            if recovered != towers:
                raise CheckFailure("tower node ids did not survive reopen")
            details["restart_tower_ids"] = dict(recovered)
        finally:
            if first is not None:
                first.close()
            if second is not None:
                second.close()


def check_erebus_tower_competition_cosine_field(details: dict[str, object]) -> None:
    """Neighbor cosine pull raises activation; competition META binds towers to the BELIEF."""
    with tempfile.TemporaryDirectory(prefix="immune_field_", ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        immune = None
        reopened = None
        try:
            immune = PlanetaryImmuneSystem(root, node_name="immune-field")
            first = immune.share_intelligence(
                {
                    "threat_type": "mesh_credential_replay",
                    "confidence": 0.9,
                    "actionable": True,
                    "vector": "alpha",
                    "summary": "high-confidence replay on the civic mesh",
                },
                source="defensive_sovereignty",
            )
            second = immune.share_intelligence(
                {
                    "threat_type": "mesh_credential_replay",
                    "confidence": 0.5,
                    "actionable": True,
                    "vector": "bravo",
                    "summary": "follow-on replay of the same campaign",
                },
                source="defensive_sovereignty",
            )
            print(
                f"first activation={first.neural_activation:.4f} "
                f"winning={first.winning_tower} "
                f"second activation={second.neural_activation:.4f} "
                f"winning={second.winning_tower}"
            )
            if second.neural_activation <= 0.55:
                raise CheckFailure(
                    f"cosine neighbor pull did not raise activation: {second.neural_activation}"
                )
            if second.neural_activation <= second.confidence:
                raise CheckFailure("second activation did not exceed local confidence")
            alloc_sum = sum(second.tower_allocations.values())
            if abs(alloc_sum - 1.0) > 1e-6:
                raise CheckFailure(f"tower allocations must sum to 1, got {alloc_sum}")
            if second.winning_tower != "deceive":
                raise CheckFailure(
                    f"expected deceive winning tower, got {second.winning_tower}"
                )
            if second.tower_competition_node_id is None:
                raise CheckFailure("competition META was not persisted")
            competition = immune.memory.retrieve_memory_node(
                second.tower_competition_node_id,
                requester=immune.memory_identity,
            )
            if competition is None or competition.kind != NodeKindEnum.META:
                raise CheckFailure("competition node missing or wrong kind")
            if second.belief_node_id is None:
                raise CheckFailure("second share missing belief")
            bound = competition.linkage_manifest.get(LinkageTypeEnum.COHERENCE_BOUND, [])
            if second.belief_node_id not in bound:
                raise CheckFailure("competition is not COHERENCE_BOUND to the BELIEF")
            tower_ids = set(immune.list_erebus_towers().values())
            if not tower_ids.issubset(set(competition.parents)):
                raise CheckFailure("competition parents omit standing towers")
            if competition.content.get("neutralize_executable") is True:
                raise CheckFailure("competition executed NEUTRALIZE without a human")
            hits = immune.get_relevant_intelligence(
                {"threat_type": "mesh_credential_replay"}
            )
            if not hits:
                raise CheckFailure("cosine field share was not searchable")
            for hit in hits:
                if str(hit.get("winning_tower") or "") == "erebus_cognitive_tower":
                    raise CheckFailure("tower META leaked into intelligence search")
            try:
                immune.share_intelligence(
                    {
                        "threat_type": "external_host_exploit",
                        "confidence": 0.99,
                        "roe_level": ROELevel.NEUTRALIZE.value,
                        "human_authorized": False,
                    },
                    source="reactive_offense",
                )
            except ImmuneSystemError as exc:
                print(f"L4 still denied after tower bind: {exc}")
                details["l4_denied"] = str(exc)
            else:
                raise CheckFailure("tower bind allowed L4 without human authorization")
            details["first_activation"] = first.neural_activation
            details["second_activation"] = second.neural_activation
            details["second_allocations"] = dict(second.tower_allocations)
            details["winning_tower"] = second.winning_tower
            details["competition_node_id"] = second.tower_competition_node_id
            intel_id = second.intel_id
            immune.close()
            immune = None
            reopened = PlanetaryImmuneSystem(root, node_name="immune-field")
            recovered = reopened.get_relevant_intelligence(
                {"threat_type": "mesh_credential_replay"}
            )
            recovered_ids = {str(item.get("intel_id")) for item in recovered}
            if intel_id not in recovered_ids:
                raise CheckFailure("tower competition intel did not survive reopen")
            recovered_row = next(
                item for item in recovered if str(item.get("intel_id")) == intel_id
            )
            if not recovered_row.get("tower_allocations"):
                raise CheckFailure("tower allocations missing after reopen")
            details["restart_recovered"] = True
            details["identities_distinct"] = (
                reopened.pan_identity.identity_hash != reopened.memory_identity.agent_id
            )
        finally:
            if immune is not None:
                immune.close()
            if reopened is not None:
                reopened.close()


def check_second_chain_retired_share_uses_immune(details: dict[str, object]) -> None:
    """Lineage D/O cannot construct a second chain; share writes USMS via the immune owner."""
    with tempfile.TemporaryDirectory(prefix="immune_bind_", ignore_cleanup_errors=True) as tmpdir:
        immune = None
        try:
            raised = False
            try:
                BlockchainThreatIntelligence(difficulty=5)
            except SecondCombatChainRetiredError as exc:
                print(f"construct denied: {exc}")
                raised = True
            if not raised:
                raise CheckFailure("BlockchainThreatIntelligence still constructed")
            detector = ThreatDetectionModule(APIConfigurationLoader(), None)
            try:
                detector.share_threat_intelligence(
                    {"threat_type": "unbound_probe", "confidence": 0.4},
                    source="lineage_unbound",
                )
            except ImmuneSystemNotBoundError as exc:
                print(f"unbound share denied: {exc}")
                details["unbound_denied"] = str(exc)
            else:
                raise CheckFailure("unbound share_threat_intelligence did not fail loud")
            immune = PlanetaryImmuneSystem(Path(tmpdir), node_name="immune-bind")
            if immune.pan_identity.identity_hash == immune.memory_identity.agent_id:
                raise CheckFailure("PAN RSA hash collapsed into USMS Ed25519 agent_id")
            detector.bind_immune_system(immune)
            record = detector.share_threat_intelligence(
                {
                    "threat_type": "credential_harvester",
                    "confidence": 0.55,
                    "actionable": True,
                    "summary": "lineage detector share through live immune owner",
                },
                source="threat_detection_module",
            )
            print(
                f"detector intel={record.intel_id} event={record.event_node_id} "
                f"roe={record.roe_level} bulletin={record.bulletin_dht_key}"
            )
            if record.event_node_id == "":
                raise CheckFailure("detector share did not persist a USMS EVENT")
            if record.roe_level == ROELevel.NEUTRALIZE.value:
                raise CheckFailure("detector share persisted NEUTRALIZE without human auth")
            hits = immune.get_relevant_intelligence({"threat_type": "credential_harvester"})
            if not hits:
                raise CheckFailure("detector share was not searchable in USMS")
            hostile = SovereignIdentity("BindHostile")
            packet = _make_packet(
                hostile,
                "METRICS_UPLOAD",
                {"message": "export user_activity to google-analytics"},
            )
            monitor = NetworkThreatMonitor(APIConfigurationLoader(), None)
            monitor.bind_immune_system(immune)
            threats = monitor.analyze_pan_packet(packet)
            print(f"monitor threats={dict(threats)}")
            if "pan_packet_firewall_violation" not in threats:
                raise CheckFailure("bound monitor did not flag firewall violation")
            firewall_hits = immune.get_relevant_intelligence(
                {"threat_type": "pan_packet_firewall_violation"}
            )
            if not firewall_hits:
                raise CheckFailure("monitor detection did not persist through PlanetaryImmuneSystem")
            details["retired_construct"] = True
            details["detector_intel_id"] = record.intel_id
            details["detector_roe_level"] = record.roe_level
            details["monitor_hits"] = len(firewall_hits)
            details["identities_distinct"] = True
        finally:
            if immune is not None:
                immune.close()


def _make_coordinator() -> SovereigntyCoordinator:
    """Bind the real coordinator class without the lineage constructor graph.

    SovereigntyCoordinator.__init__ still walks DistributedDefense / ResourcePriority
    and is not this campaign's owner. The WAN methods live on the class and raise
    as their first statement. I call those methods on an unbound instance so the
    test never opens SMTP, HTTP, or a host socket.
    """
    coord = object.__new__(SovereigntyCoordinator)
    coord.config = {
        "alert_channels": ["log"],
        "alerting_enabled": False,
        "external_threat_feeds": False,
    }
    return coord


def _close_coordinator(coord: SovereigntyCoordinator) -> None:
    """No threads were started. Keep the hook so later ctor repair stays cheap."""
    shutdown = getattr(coord, "shutdown", None)
    if callable(shutdown) and hasattr(coord, "_lock"):
        shutdown()


def check_smtp_alert_fails_loud(details: dict[str, object]) -> None:
    """SMTP never leaves the nation. Civic mail is email_social."""
    coord = _make_coordinator()
    try:
        try:
            coord._send_email_alert({"message": "do not mail the isp", "severity": "HIGH"})
        except LegacyInternetEgressError as exc:
            print(f"smtp refused: {exc}")
            details["refused"] = True
        else:
            raise CheckFailure("SMTP alert did not fail loud")
    finally:
        _close_coordinator(coord)


def check_webhook_alert_fails_loud(details: dict[str, object]) -> None:
    """HTTP webhooks never leave the nation."""
    coord = _make_coordinator()
    try:
        try:
            coord._send_webhook_alert({"message": "do not post to the old web", "severity": "HIGH"})
        except LegacyInternetEgressError as exc:
            print(f"webhook refused: {exc}")
            details["refused"] = True
        else:
            raise CheckFailure("webhook alert did not fail loud")
    finally:
        _close_coordinator(coord)


def check_threat_feed_fetch_fails_loud(details: dict[str, object]) -> None:
    """External threat feeds stay dead. Combat memory is USMS."""
    coord = _make_coordinator()
    try:
        try:
            coord._fetch_threat_intelligence_feed("https://example.invalid/feed", "otx")
        except LegacyInternetEgressError as exc:
            print(f"feed fetch refused: {exc}")
        else:
            raise CheckFailure("threat feed fetch did not fail loud")
        coord.config["external_threat_feeds"] = True
        try:
            coord._sync_threat_intelligence()
        except LegacyInternetEgressError as exc:
            print(f"feed sync refused: {exc}")
            details["sync_refused"] = True
        else:
            raise CheckFailure("threat feed sync swallowed LegacyInternetEgressError")
    finally:
        _close_coordinator(coord)


def check_whois_fails_loud(details: dict[str, object]) -> None:
    """WHOIS and public-IP recon never open a host socket."""
    hunter = TracebackHunter()
    try:
        hunter._perform_whois_lookup("203.0.113.10")
    except LegacyInternetEgressError as exc:
        print(f"whois refused: {exc}")
    else:
        raise CheckFailure("whois lookup did not fail loud")
    try:
        hunter.map_infrastructure({"source_ip": "203.0.113.10"})
    except LegacyInternetEgressError as exc:
        print(f"map_infrastructure refused: {exc}")
        details["map_refused"] = True
    else:
        raise CheckFailure("map_infrastructure with source_ip did not fail loud")


def check_wifi_deauth_fails_loud(details: dict[str, object]) -> None:
    """WiFi deauth is not a country. ROE L4 is a USMS receipt."""
    jammer = NetworkJammer()
    try:
        jammer._execute_wifi_deauth("mesh-peer", {"protocol": "wifi"})
    except LegacyInternetEgressError as exc:
        print(f"wifi deauth refused: {exc}")
    else:
        raise CheckFailure("wifi deauth did not fail loud")
    try:
        jammer._execute_deauth_packets("wlan0", "00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF")
    except LegacyInternetEgressError as exc:
        print(f"deauth packets refused: {exc}")
        details["deauth_refused"] = True
    else:
        raise CheckFailure("deauth packet injection did not fail loud")


def check_bridge_refuses_simulated_authorization(details: dict[str, object]) -> None:
    """L3/L4 never invent a simulated_operator. L4 without a human fails loud."""
    source = Path(ROOT_DIR / "security" / "defensive_offensive_bridge.py").read_text(encoding="utf-8")
    if "_simulate_authorization_response" in source:
        raise CheckFailure("simulated authorization method is still present")
    if "simulate_threat_scenario" in source:
        raise CheckFailure("simulate_threat_scenario is still present")
    if "simulated_operator" in source:
        raise CheckFailure("simulated_operator is still present")
    with tempfile.TemporaryDirectory(prefix="immune_no_sim_", ignore_cleanup_errors=True) as tmpdir:
        bridge = None
        try:
            bridge = DefensiveOffensiveBridge(runtime_root=Path(tmpdir))
            high = bridge.process_threat_event(
                ThreatLevel.HIGH,
                {
                    "threat_type": "mesh_credential_replay",
                    "confidence": 0.8,
                    "identity_hash": "ab" * 32,
                    "summary": "on-mesh degrade only",
                },
                source="defensive_sovereignty",
            )
            print(
                f"HIGH authorized={high.human_authorized} "
                f"pending={any(item.get('action') == 'authorization_pending' for item in high.authorization_chain)}"
            )
            if high.human_authorized:
                raise CheckFailure("HIGH/DEGRADE was auto-authorized without a human")
            if not any(item.get("action") == "authorization_pending" for item in high.authorization_chain):
                raise CheckFailure("HIGH/DEGRADE did not record authorization_pending")
            if not bridge.threat_intelligence.firewall.is_identity_blocked("ab" * 32):
                raise CheckFailure("on-mesh degrade did not block the identity")
            try:
                bridge.process_threat_event(
                    ThreatLevel.CRITICAL,
                    {
                        "threat_type": "external_host_exploit",
                        "confidence": 0.99,
                        "summary": "must not leave the mesh",
                    },
                    source="reactive_offense",
                )
            except ImmuneSystemError as exc:
                print(f"CRITICAL L4 denied: {exc}")
                details["l4_denied"] = str(exc)
            else:
                raise CheckFailure("CRITICAL/NEUTRALIZE did not fail loud")
            if "human authorization" not in str(details.get("l4_denied") or "").lower():
                raise CheckFailure("L4 deny did not name human authorization")
            details["no_simulated_operator"] = True
        finally:
            if bridge is not None:
                try:
                    bridge.threat_intelligence.close()
                except (ImmuneSystemError, OSError, RuntimeError):
                    pass
                bridge.stop_coordination()


CHECKS: tuple[tuple[str, CheckFn], ...] = (
    ("firewall_blocks_telemetry", check_firewall_blocks_telemetry),
    ("firewall_allows_civic_chat", check_firewall_allows_civic_chat),
    ("inspect_content_compresses_secrets", check_inspect_content_compresses_secrets),
    ("signed_secret_packet_is_blocked", check_signed_secret_packet_is_blocked),
    ("identity_blocklist", check_identity_blocklist),
    ("legacy_ip_routing_blocked", check_legacy_ip_routing_blocked),
    ("memory_survives_restart", check_memory_survives_restart),
    ("peer_ingests_bulletin", check_peer_ingests_bulletin),
    ("contradiction_and_campaign_entangle", check_contradiction_and_campaign_entangle),
    ("roe_ladder_persists_through_bridge", check_roe_ladder_persists_through_bridge),
    ("neutralize_requires_human_authorization", check_neutralize_requires_human_authorization),
    ("erebus_towers_bind_usms", check_erebus_towers_bind_usms),
    ("erebus_tower_competition_cosine_field", check_erebus_tower_competition_cosine_field),
    ("second_chain_retired_share_uses_immune", check_second_chain_retired_share_uses_immune),
    ("smtp_alert_fails_loud", check_smtp_alert_fails_loud),
    ("webhook_alert_fails_loud", check_webhook_alert_fails_loud),
    ("threat_feed_fetch_fails_loud", check_threat_feed_fetch_fails_loud),
    ("whois_fails_loud", check_whois_fails_loud),
    ("wifi_deauth_fails_loud", check_wifi_deauth_fails_loud),
    ("bridge_refuses_simulated_authorization", check_bridge_refuses_simulated_authorization),
)


def run() -> dict[str, object]:
    """Execute every immune-system check and return a gate-shaped payload."""
    started = time.time()
    checks: list[dict[str, object]] = []
    passed_count = 0
    failed_count = 0
    for name, fn in CHECKS:
        _print_banner(f"CHECK: {name}")
        detail: dict[str, object] = {}
        try:
            fn(detail)
            print(f"PASS {name}")
            checks.append({"name": name, "status": "pass", "detail": detail})
            passed_count += 1
        except CheckFailure as exc:
            print(f"FAIL {name}: {exc}")
            traceback.print_exc()
            checks.append(
                {
                    "name": name,
                    "status": "fail",
                    "error": str(exc),
                    "detail": detail,
                }
            )
            failed_count += 1
        except (
            ImmuneSystemError,
            BulletinVerificationError,
            FirewallError,
            LegacyInternetEgressError,
            UnifiedMemoryError,
            AssertionError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            MemoryAccessError,
            SovereignIdentityError,
            sqlite3.Error,
        ) as exc:
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            checks.append(
                {
                    "name": name,
                    "status": "fail",
                    "error": f"{type(exc).__name__}: {exc}",
                    "detail": detail,
                }
            )
            failed_count += 1
    elapsed = time.time() - started
    passed = failed_count == 0
    payload: dict[str, object] = {
        "name": "planetary_immune_system",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
    }
    if not passed:
        payload["error"] = f"{failed_count} immune checks failed"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    artifacts = write_artifacts(payload, timestamp, "invoked via run()\n")
    payload["artifacts"] = {key: str(path) for key, path in artifacts.items()}
    artifacts["json"].write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def write_artifacts(payload: dict[str, object], timestamp: str, log_text: str) -> dict[str, Path]:
    """Write Code Forge JSON, Markdown, and log artifacts for this run."""
    run_dir = CURRENT_DIR / "runs" / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "result.json"
    md_path = run_dir / "result.md"
    log_path = run_dir / "result.log"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    log_path.write_text(log_text, encoding="utf-8")
    lines = [
        f"# Planetary immune system run {timestamp}",
        "",
        f"I ran `python test/immune/test_planetary_immune_system.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required a real USMS sqlite file, a real firewall ledger, and two PAN DHT nodes.",
        "I required the demo firewall to be gone. I required high-confidence beliefs to",
        "become `THREAT_MEMORY_BULLETIN` packets that a peer can ingest after restart.",
        "I required ROE DECEIVE/DEGRADE to persist as USMS BELIEF content via the",
        "defensive-offensive bridge, and ROE Level 4 to fail without human authorization.",
        "I required standing Erebus towers as USMS META nodes, cosine-weighted DAG",
        "activation, and competition META that survives reopen without collapsing",
        "PAN RSA and USMS Ed25519 identities.",
        "",
        "## Checks",
        "",
    ]
    for item in payload.get("checks", []):
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('name')}`: {item.get('status')}")
        if item.get("error"):
            lines.append(f"  - error: `{item.get('error')}`")
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
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "md": md_path, "log": log_path, "run_dir": run_dir}


def main() -> int:
    """Run checks, persist artifacts, print a gate-shaped summary."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        print(f"immune consumer start {timestamp}")
        payload = run()
        print(f"immune consumer status={payload.get('status')}")
    log_text = buffer.getvalue()
    sys.stdout.write(log_text)
    artifacts = write_artifacts(payload, timestamp, log_text)
    print(f"artifacts json={artifacts['json']}")
    print(f"artifacts md={artifacts['md']}")
    print(f"artifacts log={artifacts['log']}")
    payload["artifacts"] = {key: str(path) for key, path in artifacts.items()}
    artifacts["json"].write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return 0 if payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
