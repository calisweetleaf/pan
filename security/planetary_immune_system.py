"""
Planetary immune system — USMS cognition bound to the PAN mesh.

Source: memory/unified_memory_system.py, PAN_SDK DHT/UnifiedDataPacket,
    security/sovereign_firewall.py
Integrated: 2026-09-11

Modified: 2026-09-12
Modified by: cursor-grok (daeron)
Justification: I extended the live immune owner so ROE OBSERVE/DECEIVE/DEGRADE
    persist as USMS BELIEF content, with neighbor-weighted DAG activation taken
    further from MTL/USMS. Wrapping defensive_offensive_bridge to avoid this
    edit is banned. NEUTRALIZE without human authorization fails loud and never
    becomes an external-host action. RSA PAN and Ed25519 USMS stay bound.
Provenance: snapshots/v0.2/manifest.json -> domains.immune.edits[0]
Files: security/planetary_immune_system.py
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PAN_SDK.PAN_SDK import (
    DHTNode,
    PANPersistenceStore,
    SovereignCommunicator,
    SovereignIdentity as PANSovereignIdentity,
    UnifiedDataPacket,
    canonical,
    sha256_hex,
    utc_now_iso,
)
from memory.unified_memory_system import (
    LinkageTypeEnum,
    MemoryAccessError,
    MemoryIntegrityError,
    NodeKindEnum,
    SovereignIdentity as MemorySovereignIdentity,
    SovereignIdentityError,
    UnifiedMemoryError,
    UnifiedMemoryNode,
    UnifiedMemorySystem,
)
from security.sovereign_firewall import (
    FirewallInspectionError,
    InspectionLane,
    SovereignFirewall,
    THREAT_BULLETIN_KIND,
)

LOGGER = logging.getLogger("PlanetaryImmuneSystem")

HIGH_CONFIDENCE_THRESHOLD = 0.75
BULLETIN_DHT_PREFIX = "threat-memory:"
IDENTITY_DIRNAME = "identities"
PAN_IDENTITY_FILE = "pan_identity.json"
USMS_IDENTITY_FILE = "usms_identity.json"
ROE_ORDER = ("observe", "deceive", "degrade", "neutralize")


class ROELevel(str, Enum):
    """Rules of Engagement ladder persisted on USMS BELIEF nodes.

    Level 4 NEUTRALIZE is a human-authorization receipt only. This owner never
    opens a network socket or subprocess against an external host.
    """

    OBSERVE = "observe"
    DECEIVE = "deceive"
    DEGRADE = "degrade"
    NEUTRALIZE = "neutralize"


class ImmuneSystemError(Exception):
    """Domain error for the planetary immune seam."""


class ImmuneSystemNotBoundError(ImmuneSystemError):
    """Raised when a bridge or coordinator is constructed without a runtime root."""


class BulletinVerificationError(ImmuneSystemError):
    """Raised when a mesh bulletin fails cryptographic or firewall checks."""


@dataclass
class IntelligenceRecord:
    """Persisted threat intelligence anchored in USMS and optionally the PAN DHT."""

    intel_id: str
    timestamp: float
    source: str
    threat_type: str
    confidence: float
    threat_level: str
    actionable: bool
    event_node_id: str
    belief_node_id: str | None
    bulletin_packet_id: str | None
    bulletin_dht_key: str | None
    similar_node_ids: tuple[str, ...] = ()
    entanglement_id: str | None = None
    payload: dict[str, object] = field(default_factory=dict)
    roe_level: str = ROELevel.OBSERVE.value
    neural_activation: float = 0.0
    neutralize_denied: bool = False

    def to_mapping(self) -> dict[str, object]:
        """Return the historical coordinator mapping consumed by the bridge."""
        return {
            "intel_id": self.intel_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "data": dict(self.payload),
            "confidence": self.confidence,
            "threat_level": self.threat_level,
            "actionable": self.actionable,
            "event_node_id": self.event_node_id,
            "belief_node_id": self.belief_node_id,
            "bulletin_packet_id": self.bulletin_packet_id,
            "bulletin_dht_key": self.bulletin_dht_key,
            "similar_node_ids": list(self.similar_node_ids),
            "entanglement_id": self.entanglement_id,
            "roe_level": self.roe_level,
            "neural_activation": self.neural_activation,
            "neutralize_denied": self.neutralize_denied,
        }


class PlanetaryImmuneSystem:
    """Local USMS brain plus PAN nervous system for sovereign threat memory."""

    def __init__(
        self,
        runtime_root: str | Path,
        *,
        node_name: str = "immune-node",
        pan_identity: PANSovereignIdentity | None = None,
        memory_identity: MemorySovereignIdentity | None = None,
        broadcast_requires_consensus: bool = False,
        high_confidence_threshold: float = HIGH_CONFIDENCE_THRESHOLD,
    ) -> None:
        """
        Bind USMS, the sovereign firewall, and a PAN DHT node under one runtime root.

        Args:
            runtime_root: Isolated directory for USMS sqlite, firewall ledger, PAN state.
            node_name: Human-readable name for generated identities.
            pan_identity: Optional RSA PAN identity. Loaded or created if omitted.
            memory_identity: Optional Ed25519 USMS identity. Loaded or created if omitted.
            broadcast_requires_consensus: When True, DHT store waits on PANConsensus.
            high_confidence_threshold: Minimum belief confidence for mesh broadcast.

        Returns:
            None
        """
        if not runtime_root:
            raise ImmuneSystemNotBoundError("PlanetaryImmuneSystem requires a runtime_root")
        if not 0.0 < high_confidence_threshold <= 1.0:
            raise ImmuneSystemError("high_confidence_threshold must be in (0.0, 1.0]")
        self.runtime_root = Path(runtime_root)
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.node_name = node_name
        self.broadcast_requires_consensus = broadcast_requires_consensus
        self.high_confidence_threshold = high_confidence_threshold
        self._lock = threading.RLock()
        self._subscribers: list[dict[str, object]] = []
        self.metrics: dict[str, int] = {
            "total_indicators": 0,
            "shared_indicators": 0,
            "correlated_threats": 0,
            "actionable_intelligence": 0,
            "bulletins_broadcast": 0,
            "bulletins_ingested": 0,
            "contradictions": 0,
        }

        self.pan_identity = pan_identity or self._load_or_create_pan_identity()
        self.memory_identity = memory_identity or self._load_or_create_memory_identity()
        usms_root = self.runtime_root / "usms"
        usms_root.mkdir(parents=True, exist_ok=True)
        db_path = usms_root / "unified_sovereign_memory.db"
        self.memory = UnifiedMemorySystem(
            db_path=str(db_path),
            config={"runtime_root": str(usms_root), "console_logging": False},
            enable_quantum_features=True,
        )
        self.memory.register_sovereign(self.memory_identity)
        self.firewall = SovereignFirewall(self.runtime_root / "firewall" / "ledger.sqlite")
        self.persistence = PANPersistenceStore(base_path=self.runtime_root / "pan")
        self.dht = DHTNode(
            self.pan_identity,
            persistence=self.persistence,
            enable_consensus=broadcast_requires_consensus,
        )
        self.communicator = SovereignCommunicator(self.pan_identity)
        self._write_identity_binding()
        LOGGER.info(
            "PlanetaryImmuneSystem online for %s pan=%s usms=%s",
            node_name,
            self.pan_identity.identity_hash[:12],
            self.memory_identity.agent_id[:12],
        )

    def close(self) -> None:
        """
        Shut down USMS background work, the firewall ledger, and PAN persistence.

        Args:
            None

        Returns:
            None
        """
        with self._lock:
            self.memory.shutdown()
            self.firewall.close()
            self.persistence.close()
        LOGGER.info("PlanetaryImmuneSystem closed for %s", self.node_name)

    def register_intelligence_source(
        self,
        source_id: str,
        source_callback: Callable[[dict[str, object]], None],
    ) -> None:
        """
        Register an in-process subscriber that receives persisted intelligence mappings.

        Args:
            source_id: Subscriber name.
            source_callback: Callback receiving the historical intelligence mapping.

        Returns:
            None
        """
        if not source_id:
            raise ImmuneSystemError("source_id must be non-empty")
        with self._lock:
            self._subscribers.append({"id": source_id, "callback": source_callback})

    def share_intelligence(
        self,
        intelligence_data: Mapping[str, object],
        source: str = "unknown",
    ) -> IntelligenceRecord:
        """
        Persist a detection EVENT, a ROE BELIEF, and maybe a PAN bulletin.

        Args:
            intelligence_data: Threat indicator mapping from defensive or offensive owners.
            source: Authoring subsystem name.

        Returns:
            IntelligenceRecord with USMS node ids and optional DHT key.
        """
        if not isinstance(intelligence_data, Mapping):
            raise ImmuneSystemError("intelligence_data must be a mapping")
        payload = _jsonable_mapping(intelligence_data)
        threat_type = str(payload.get("threat_type") or payload.get("attack_vector") or "unknown")
        confidence = _bounded_confidence(payload.get("confidence", 0.5))
        threat_level = str(payload.get("threat_level") or _threat_level_from_confidence(confidence))
        actionable = bool(payload.get("actionable", False))
        intel_id = sha256_hex(canonical({"source": source, "payload": payload}))[:16]
        with self._lock:
            existing = self.persistence.read_state("immune_index", intel_id)
            if isinstance(existing, dict) and existing.get("event_node_id"):
                record = self._record_from_index(existing)
                self.metrics["total_indicators"] += 1
                return record

            similar = self._semantic_neighbors(threat_type)
            human_authorized = bool(payload.get("human_authorized", False))
            requested_roe = str(payload.get("roe_level") or "").strip().lower()
            activation = self._neural_activation(confidence, similar)
            roe = self._resolve_roe_level(requested_roe, activation, human_authorized)
            event_content: dict[str, object] = {
                "summary": f"threat event {threat_type}",
                "intel_id": intel_id,
                "source": source,
                "threat_type": threat_type,
                "threat_level": threat_level,
                "confidence": confidence,
                "payload": payload,
            }
            event_links = {}
            if similar:
                event_links[LinkageTypeEnum.SEMANTIC_SIMILAR] = [similar[0].node_id]
            event_node = self.memory.create_memory_node(
                author=self.memory_identity,
                kind=NodeKindEnum.EVENT,
                content=event_content,
                linkage_manifest=event_links or None,
                semantic_context=threat_type,
            )
            claim = (
                f"I believe {threat_type} is a live threat at confidence {confidence:.2f} "
                f"and threat_level {threat_level}"
            )
            belief_links: dict[LinkageTypeEnum, list[str]] = {
                LinkageTypeEnum.CAUSAL_PARENT: [event_node.node_id]
            }
            if similar:
                belief_links[LinkageTypeEnum.SYNTHESIS] = [node.node_id for node in similar[:3]]
            belief_node = self.memory.create_memory_node(
                author=self.memory_identity,
                kind=NodeKindEnum.BELIEF,
                content={
                    "claim": claim,
                    "intel_id": intel_id,
                    "threat_type": threat_type,
                    "threat_level": threat_level,
                    "confidence": confidence,
                    "roe_observe": True,
                    "roe_deceive": roe in {ROELevel.DECEIVE, ROELevel.DEGRADE, ROELevel.NEUTRALIZE},
                    "roe_degrade": roe in {ROELevel.DEGRADE, ROELevel.NEUTRALIZE},
                    "roe_neutralize": roe == ROELevel.NEUTRALIZE,
                    "roe_level": roe.value,
                    "neural_activation": activation,
                    "human_authorized": human_authorized,
                    "neutralize_denied": False,
                },
                parents=[event_node.node_id],
                linkage_manifest=belief_links,
                semantic_context=threat_type,
            )
            self.memory.attest_belief(
                belief_node.node_id,
                self.memory_identity,
                confidence,
                rationale=claim,
            )
            entanglement_id = self._maybe_entangle(payload, event_node.node_id)
            bulletin_packet_id = None
            bulletin_dht_key = None
            if confidence >= self.high_confidence_threshold:
                bulletin_packet_id, bulletin_dht_key = self._broadcast_belief(
                    event_node=event_node,
                    belief_node=belief_node,
                    threat_type=threat_type,
                    confidence=confidence,
                    threat_level=threat_level,
                    intel_id=intel_id,
                )
            similar_ids = tuple(node.node_id for node in similar[:5])
            record = IntelligenceRecord(
                intel_id=intel_id,
                timestamp=event_node.last_access_timestamp,
                source=source,
                threat_type=threat_type,
                confidence=confidence,
                threat_level=threat_level,
                actionable=actionable,
                event_node_id=event_node.node_id,
                belief_node_id=belief_node.node_id,
                bulletin_packet_id=bulletin_packet_id,
                bulletin_dht_key=bulletin_dht_key,
                similar_node_ids=similar_ids,
                entanglement_id=entanglement_id,
                payload=payload,
                roe_level=roe.value,
                neural_activation=activation,
                neutralize_denied=False,
            )
            self.persistence.write_state("immune_index", intel_id, record.to_mapping())
            campaign = str(payload.get("campaign_id") or "")
            if campaign:
                campaign_ids = self.persistence.read_state("immune_campaigns", campaign) or []
                if not isinstance(campaign_ids, list):
                    campaign_ids = []
                if event_node.node_id not in campaign_ids:
                    campaign_ids.append(event_node.node_id)
                self.persistence.write_state("immune_campaigns", campaign, campaign_ids)
            self.metrics["total_indicators"] += 1
            if actionable:
                self.metrics["actionable_intelligence"] += 1
            if similar_ids:
                self.metrics["correlated_threats"] += 1
            self._notify_subscribers(record)
            return record

    def record_roe_decision(
        self,
        *,
        event_node_id: str,
        roe_level: str,
        human_authorized: bool = False,
        summary: str = "",
    ) -> UnifiedMemoryNode:
        """
        Persist an explicit ROE BELIEF on the USMS DAG.

        NEUTRALIZE without human_authorized fails loud. No external host action
        is taken at any level.

        Args:
            event_node_id: Parent EVENT already stored in USMS.
            roe_level: observe | deceive | degrade | neutralize.
            human_authorized: Required for NEUTRALIZE. Logged, never implied.
            summary: Optional rationale stored on the BELIEF.

        Returns:
            The ROE BELIEF node.
        """
        requested = str(roe_level or "").strip().lower()
        if requested not in ROE_ORDER:
            raise ImmuneSystemError(f"unknown ROE level {roe_level!r}")
        if requested == ROELevel.NEUTRALIZE.value and not human_authorized:
            raise ImmuneSystemError(
                "ROE Level 4 NEUTRALIZE requires human authorization; "
                "external-host action is not authorized"
            )
        roe = ROELevel(requested)
        with self._lock:
            event = self.memory.retrieve_memory_node(
                event_node_id, requester=self.memory_identity
            )
            if event is None:
                raise ImmuneSystemError(f"event node not found: {event_node_id[:12]}")
            claim = summary or f"ROE {roe.value} recorded for {event.content.get('threat_type')}"
            belief = self.memory.create_memory_node(
                author=self.memory_identity,
                kind=NodeKindEnum.BELIEF,
                content={
                    "claim": claim,
                    "intel_id": event.content.get("intel_id"),
                    "threat_type": event.content.get("threat_type"),
                    "roe_observe": True,
                    "roe_deceive": roe in {ROELevel.DECEIVE, ROELevel.DEGRADE, ROELevel.NEUTRALIZE},
                    "roe_degrade": roe in {ROELevel.DEGRADE, ROELevel.NEUTRALIZE},
                    "roe_neutralize": roe == ROELevel.NEUTRALIZE,
                    "roe_level": roe.value,
                    "human_authorized": human_authorized,
                    "neutralize_denied": False,
                    "explicit_roe_decision": True,
                },
                parents=[event_node_id],
                linkage_manifest={LinkageTypeEnum.CAUSAL_PARENT: [event_node_id]},
                semantic_context=str(event.content.get("threat_type") or "roe"),
            )
            self.memory.attest_belief(
                belief.node_id,
                self.memory_identity,
                1.0 if human_authorized else 0.74,
                rationale=claim,
            )
            return belief

    def get_relevant_intelligence(
        self,
        threat_context: Mapping[str, object],
    ) -> list[dict[str, object]]:
        """
        Semantic-search USMS for intelligence relevant to a live threat context.

        Args:
            threat_context: Current threat mapping (threat_type, summary, campaign_id).

        Returns:
            Up to ten historical intelligence mappings with relevance_score.
        """
        if not isinstance(threat_context, Mapping):
            raise ImmuneSystemError("threat_context must be a mapping")
        query = " ".join(
            str(threat_context.get(key) or "")
            for key in ("threat_type", "attack_vector", "summary", "campaign_id")
        ).strip() or "threat"
        with self._lock:
            nodes = self.memory.search_nodes_by_content(
                query,
                limit=10,
                requester=self.memory_identity,
            )
        ranked: list[dict[str, object]] = []
        index = self.persistence.load_component("immune_index")
        for position, node in enumerate(nodes):
            intel_id = str(node.content.get("intel_id") or node.node_id[:16])
            stored = index.get(intel_id) if isinstance(index, dict) else None
            row: dict[str, object]
            if isinstance(stored, dict):
                row = dict(stored)
            else:
                row = {
                    "intel_id": intel_id,
                    "timestamp": node.last_access_timestamp,
                    "source": str(node.content.get("source") or "usms"),
                    "data": dict(node.content),
                    "confidence": float(node.content.get("confidence") or 0.5),
                    "threat_level": str(node.content.get("threat_level") or "low"),
                    "actionable": bool(node.content.get("actionable", False)),
                    "event_node_id": node.node_id,
                }
            row["relevance_score"] = max(0.0, 1.0 - (position * 0.08))
            ranked.append(row)
        return ranked

    def record_countermeasure_failure(
        self,
        belief_node_id: str,
        summary: str,
        details: Mapping[str, object] | None = None,
    ) -> UnifiedMemoryNode:
        """
        Write a CONTRADICTION-linked EVENT when an offensive countermeasure fails.

        Args:
            belief_node_id: USMS belief that authorized the countermeasure.
            summary: Failure summary used as semantic context.
            details: Optional structured failure payload.

        Returns:
            The failure EVENT node.
        """
        if not belief_node_id:
            raise ImmuneSystemError("belief_node_id is required")
        payload = _jsonable_mapping(details or {})
        with self._lock:
            belief = self.memory.retrieve_memory_node(
                belief_node_id, requester=self.memory_identity
            )
            if belief is None:
                raise ImmuneSystemError(f"belief node not found: {belief_node_id[:12]}")
            failure = self.memory.create_memory_node(
                author=self.memory_identity,
                kind=NodeKindEnum.EVENT,
                content={
                    "summary": summary,
                    "claim": f"countermeasure failed against {belief.content.get('threat_type')}",
                    "belief_node_id": belief_node_id,
                    "details": payload,
                },
                parents=[belief_node_id],
                linkage_manifest={LinkageTypeEnum.CONTRADICTION: [belief_node_id]},
                semantic_context=summary,
            )
            self.metrics["contradictions"] += 1
            return failure

    def ingest_bulletin(self, packet_payload: Mapping[str, object]) -> IntelligenceRecord:
        """
        Verify a PAN threat bulletin and remember it as local USMS nodes.

        Args:
            packet_payload: `UnifiedDataPacket.to_dict()` from a peer DHT lookup.

        Returns:
            Local IntelligenceRecord. Does not re-broadcast.
        """
        if not isinstance(packet_payload, Mapping):
            raise BulletinVerificationError("bulletin payload must be a mapping")
        packet = UnifiedDataPacket.from_dict(dict(packet_payload))
        if packet.kind != THREAT_BULLETIN_KIND:
            raise BulletinVerificationError(f"unexpected packet kind {packet.kind}")
        verdict = self.firewall.inspect_packet(packet, lane=InspectionLane.PAN_MESH)
        if verdict.blocked:
            raise BulletinVerificationError(f"firewall dropped bulletin: {verdict.reason}")
        if not packet.verify_integrity():
            raise BulletinVerificationError("bulletin failed content integrity")
        author_pem = str(packet.metadata.get("pan_public_key_pem") or "").encode("utf-8")
        if not author_pem:
            raise BulletinVerificationError("bulletin missing pan_public_key_pem")
        if not self._verify_pan_signature(packet, author_pem):
            raise BulletinVerificationError("PAN packet signature is invalid")
        content = packet.content
        digest = sha256_hex(canonical(_bulletin_signed_body(content)))
        usms_pubkey = str(content.get("usms_pubkey") or "")
        usms_signature = str(content.get("usms_signature") or "")
        if not MemorySovereignIdentity.verify_signature(
            usms_pubkey, digest.encode("utf-8"), usms_signature
        ):
            raise BulletinVerificationError("USMS bulletin signature is invalid")
        threat_type = str(content.get("threat_type") or "unknown")
        confidence = _bounded_confidence(content.get("confidence", 0.5))
        intel_id = str(content.get("intel_id") or sha256_hex(packet.packet_id)[:16])
        with self._lock:
            event_node = self.memory.create_memory_node(
                author=self.memory_identity,
                kind=NodeKindEnum.EVENT,
                content={
                    "summary": f"ingested mesh bulletin {threat_type}",
                    "intel_id": intel_id,
                    "source": "pan_mesh",
                    "origin_node_id": content.get("origin_node_id"),
                    "origin_event_node_id": content.get("event_node_id"),
                    "origin_pan_identity_hash": packet.author_identity_hash,
                    "threat_type": threat_type,
                    "confidence": confidence,
                    "payload": dict(content),
                },
                semantic_context=threat_type,
            )
            belief_node = self.memory.create_memory_node(
                author=self.memory_identity,
                kind=NodeKindEnum.BELIEF,
                content={
                    "claim": str(content.get("claim") or f"peer belief: {threat_type}"),
                    "intel_id": intel_id,
                    "threat_type": threat_type,
                    "confidence": confidence,
                    "ingested": True,
                },
                parents=[event_node.node_id],
                linkage_manifest={LinkageTypeEnum.CAUSAL_PARENT: [event_node.node_id]},
                semantic_context=threat_type,
            )
            record = IntelligenceRecord(
                intel_id=intel_id,
                timestamp=event_node.last_access_timestamp,
                source="pan_mesh",
                threat_type=threat_type,
                confidence=confidence,
                threat_level=str(content.get("threat_level") or "high"),
                actionable=True,
                event_node_id=event_node.node_id,
                belief_node_id=belief_node.node_id,
                bulletin_packet_id=packet.packet_id,
                bulletin_dht_key=None,
                payload=dict(content),
            )
            self.persistence.write_state("immune_index", intel_id, record.to_mapping())
            self.metrics["bulletins_ingested"] += 1
            return record

    def lookup_bulletin(self, dht_key: str) -> dict[str, object] | None:
        """
        Read a previously stored bulletin from this node's DHT.

        Args:
            dht_key: Key written by `_broadcast_belief`.

        Returns:
            Packet mapping or None.
        """
        value = self.dht.lookup(dht_key)
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ImmuneSystemError("DHT bulletin is not a mapping")
        return value

    def _broadcast_belief(
        self,
        *,
        event_node: UnifiedMemoryNode,
        belief_node: UnifiedMemoryNode,
        threat_type: str,
        confidence: float,
        threat_level: str,
        intel_id: str,
    ) -> tuple[str, str]:
        """Package a high-confidence belief as a firewall-inspected PAN packet."""
        body: dict[str, object] = {
            "intel_id": intel_id,
            "origin_node_id": belief_node.node_id,
            "event_node_id": event_node.node_id,
            "threat_type": threat_type,
            "threat_level": threat_level,
            "confidence": confidence,
            "claim": str(belief_node.content.get("claim") or ""),
            "usms_author_id": self.memory_identity.agent_id,
            "usms_pubkey": self.memory_identity.public_key,
            "pan_identity_hash": self.pan_identity.identity_hash,
        }
        digest = sha256_hex(canonical(_bulletin_signed_body(body)))
        body["content_digest"] = digest
        body["usms_signature"] = self.memory_identity.sign(digest.encode("utf-8"))
        preflight = self.firewall.inspect_content(
            body,
            lane=InspectionLane.PAN_MESH,
            author_identity_hash=self.pan_identity.identity_hash,
        )
        if preflight.blocked:
            raise FirewallInspectionError(
                f"immune bulletin blocked before signing: {preflight.reason}"
            )
        packet_content = preflight.sanitized_content or body
        if not isinstance(packet_content, dict):
            raise FirewallInspectionError("firewall sanitized_content must be a dict")
        packet = self.communicator.create_packet(
            THREAT_BULLETIN_KIND,
            packet_content,
            parents=[event_node.node_id, belief_node.node_id],
            metadata={
                "pan_public_key_pem": self.pan_identity.get_public_key_pem().decode("utf-8"),
                "usms_author_id": self.memory_identity.agent_id,
            },
        )
        verdict = self.firewall.inspect_packet(packet, lane=InspectionLane.PAN_MESH)
        if verdict.blocked:
            raise FirewallInspectionError(f"immune bulletin blocked after signing: {verdict.reason}")
        dht_key = f"{BULLETIN_DHT_PREFIX}{digest}"
        stored = self.dht.store(
            dht_key,
            packet.to_dict(),
            require_consensus=self.broadcast_requires_consensus,
        )
        if not stored:
            raise ImmuneSystemError(f"DHT rejected bulletin store for {dht_key}")
        self.dht.store(
            f"{BULLETIN_DHT_PREFIX}latest",
            {"dht_key": dht_key, "packet_id": packet.packet_id},
            require_consensus=False,
        )
        self.metrics["bulletins_broadcast"] += 1
        LOGGER.info("Broadcast threat bulletin %s key=%s", packet.packet_id[:12], dht_key)
        return packet.packet_id, dht_key

    def _neural_activation(
        self,
        confidence: float,
        similar: list[UnifiedMemoryNode],
    ) -> float:
        """MTL-style DAG activation: local confidence plus neighbor belief pull."""
        neighbor_weight = 0.0
        for node in similar:
            node_conf = float(node.content.get("confidence") or 0.0)
            neighbor_weight += node_conf
        if similar:
            neighbor_weight = neighbor_weight / len(similar)
        return min(1.0, (confidence * 0.7) + (neighbor_weight * 0.3))

    def _resolve_roe_level(
        self,
        requested: str,
        activation: float,
        human_authorized: bool,
    ) -> ROELevel:
        """Map explicit request or DAG activation onto the ROE ladder."""
        derived = ROELevel.OBSERVE
        if activation >= 0.95:
            derived = ROELevel.NEUTRALIZE
        elif activation >= 0.75:
            derived = ROELevel.DEGRADE
        elif activation >= 0.40:
            derived = ROELevel.DECEIVE
        if requested in ROE_ORDER:
            derived = ROELevel(requested)
        if derived == ROELevel.NEUTRALIZE and not human_authorized:
            raise ImmuneSystemError(
                "ROE Level 4 NEUTRALIZE requires human authorization; "
                "external-host action is not authorized"
            )
        return derived

    def _semantic_neighbors(self, threat_type: str) -> list[UnifiedMemoryNode]:
        """Return semantically similar EVENT/BELIEF nodes for the current author."""
        try:
            nodes = self.memory.search_nodes_by_content(
                threat_type,
                limit=8,
                requester=self.memory_identity,
            )
        except (MemoryAccessError, UnifiedMemoryError, MemoryIntegrityError) as exc:
            LOGGER.warning("semantic search failed closed-open: %s", exc)
            return []
        return [
            node
            for node in nodes
            if node.kind in {NodeKindEnum.EVENT, NodeKindEnum.BELIEF}
        ]

    def _maybe_entangle(self, payload: Mapping[str, object], event_node_id: str) -> str | None:
        """Entangle three or more campaign events into one quantum-inspired cluster."""
        campaign = str(payload.get("campaign_id") or "")
        if not campaign:
            return None
        campaign_ids = self.persistence.read_state("immune_campaigns", campaign) or []
        if not isinstance(campaign_ids, list):
            return None
        node_ids = [str(item) for item in campaign_ids if isinstance(item, str)]
        if event_node_id not in node_ids:
            node_ids.append(event_node_id)
        if len(node_ids) < 3:
            return None
        entanglement_id = self.memory.quantum_entangle_nodes(
            node_ids[-3:],
            self.memory_identity,
        )
        return entanglement_id

    def _notify_subscribers(self, record: IntelligenceRecord) -> None:
        """Fan out the persisted mapping. Fail loud per subscriber, continue the rest."""
        mapping = record.to_mapping()
        for subscriber in list(self._subscribers):
            callback = subscriber.get("callback")
            source_id = str(subscriber.get("id") or "unknown")
            try:
                if not callable(callback):
                    raise ImmuneSystemError(f"subscriber {source_id} is not callable")
                callback(mapping)
                self.metrics["shared_indicators"] += 1
            except (
                ImmuneSystemError,
                TypeError,
                ValueError,
                AttributeError,
                KeyError,
                RuntimeError,
            ) as exc:
                LOGGER.error("subscriber %s failed: %s", source_id, exc)

    def _record_from_index(self, stored: Mapping[str, object]) -> IntelligenceRecord:
        """Rehydrate an IntelligenceRecord from PAN persistence."""
        similar_raw = stored.get("similar_node_ids") or []
        similar = tuple(str(item) for item in similar_raw) if isinstance(similar_raw, list) else ()
        payload_raw = stored.get("data") or stored.get("payload") or {}
        payload = dict(payload_raw) if isinstance(payload_raw, dict) else {}
        return IntelligenceRecord(
            intel_id=str(stored.get("intel_id") or ""),
            timestamp=float(stored.get("timestamp") or 0.0),
            source=str(stored.get("source") or "unknown"),
            threat_type=str(payload.get("threat_type") or stored.get("threat_type") or "unknown"),
            confidence=float(stored.get("confidence") or 0.0),
            threat_level=str(stored.get("threat_level") or "low"),
            actionable=bool(stored.get("actionable", False)),
            event_node_id=str(stored.get("event_node_id") or ""),
            belief_node_id=(
                str(stored["belief_node_id"]) if stored.get("belief_node_id") else None
            ),
            bulletin_packet_id=(
                str(stored["bulletin_packet_id"]) if stored.get("bulletin_packet_id") else None
            ),
            bulletin_dht_key=(
                str(stored["bulletin_dht_key"]) if stored.get("bulletin_dht_key") else None
            ),
            similar_node_ids=similar,
            entanglement_id=(
                str(stored["entanglement_id"]) if stored.get("entanglement_id") else None
            ),
            payload=payload,
            roe_level=str(stored.get("roe_level") or ROELevel.OBSERVE.value),
            neural_activation=float(stored.get("neural_activation") or 0.0),
            neutralize_denied=bool(stored.get("neutralize_denied", False)),
        )

    def _write_identity_binding(self) -> None:
        """Anchor the PAN/USMS identity pair as a META node once per runtime."""
        existing = self.persistence.read_state("immune_meta", "identity_binding")
        if existing:
            return
        node = self.memory.create_memory_node(
            author=self.memory_identity,
            kind=NodeKindEnum.META,
            content={
                "summary": "PAN-USMS identity binding",
                "pan_identity_hash": self.pan_identity.identity_hash,
                "pan_name": self.pan_identity.name,
                "usms_agent_id": self.memory_identity.agent_id,
                "usms_agent_name": self.memory_identity.agent_name,
                "usms_public_key": self.memory_identity.public_key,
                "note": "Ed25519 memory author bound to RSA PAN packet author",
            },
            semantic_context="identity binding pan usms",
        )
        self.persistence.write_state(
            "immune_meta",
            "identity_binding",
            {"node_id": node.node_id},
        )

    def _load_or_create_pan_identity(self) -> PANSovereignIdentity:
        """Load a persisted RSA identity or create one for this runtime root."""
        path = self.runtime_root / IDENTITY_DIRNAME / PAN_IDENTITY_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            pem = str(raw.get("private_key_pem") or "").encode("utf-8")
            name = str(raw.get("name") or self.node_name)
            if not pem:
                raise ImmuneSystemError("persisted PAN identity is missing private_key_pem")
            return PANSovereignIdentity(name, private_key_pem=pem)
        identity = PANSovereignIdentity(self.node_name)
        path.write_text(
            json.dumps(
                {
                    "name": identity.name,
                    "identity_hash": identity.identity_hash,
                    "private_key_pem": identity.serialize_private_key().decode("utf-8"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return identity

    def _load_or_create_memory_identity(self) -> MemorySovereignIdentity:
        """Load a persisted Ed25519 identity or create one for this runtime root."""
        path = self.runtime_root / IDENTITY_DIRNAME / USMS_IDENTITY_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            return MemorySovereignIdentity(
                agent_name=str(raw.get("agent_name") or f"{self.node_name}-memory"),
                agent_id=str(raw.get("agent_id") or ""),
                public_key=str(raw.get("public_key") or ""),
                creation_timestamp=float(raw.get("creation_timestamp") or 0.0),
                _private_key=str(raw.get("private_key_hex") or ""),
            )
        identity = MemorySovereignIdentity(
            agent_name=f"{self.node_name}-memory",
            agent_id="",
            public_key="",
            creation_timestamp=0.0,
        )
        path.write_text(
            json.dumps(
                {
                    "agent_name": identity.agent_name,
                    "agent_id": identity.agent_id,
                    "public_key": identity.public_key,
                    "creation_timestamp": identity.creation_timestamp,
                    "private_key_hex": identity._private_key,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return identity

    def _verify_pan_signature(self, packet: UnifiedDataPacket, author_pem: bytes) -> bool:
        """Verify the RSA packet signature against the author's public key."""
        packet_dict = packet.to_dict()
        packet_dict["signature"] = None
        packet_data = canonical(packet_dict).encode("utf-8")
        if packet.signature is None:
            return False
        return bool(
            self.pan_identity.verify_signature(packet_data, packet.signature, author_pem)
        )


def _bulletin_signed_body(content: Mapping[str, object]) -> dict[str, object]:
    """Return the USMS-signed bulletin fields without the signature itself."""
    return {
        "intel_id": content.get("intel_id"),
        "origin_node_id": content.get("origin_node_id"),
        "event_node_id": content.get("event_node_id"),
        "threat_type": content.get("threat_type"),
        "threat_level": content.get("threat_level"),
        "confidence": content.get("confidence"),
        "claim": content.get("claim"),
        "usms_author_id": content.get("usms_author_id"),
        "usms_pubkey": content.get("usms_pubkey"),
        "pan_identity_hash": content.get("pan_identity_hash"),
    }


def _jsonable_mapping(value: Mapping[str, object]) -> dict[str, object]:
    """Copy a mapping into JSON-stable primitives."""
    result: dict[str, object] = {}
    for key, inner in value.items():
        result[str(key)] = _jsonable(inner)
    return result


def _jsonable(value: object) -> object:
    """Convert schema-shaped threat payloads into JSON-stable primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


def _bounded_confidence(value: object) -> float:
    """Clamp confidence into [0.0, 1.0]."""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ImmuneSystemError("confidence must be numeric") from exc
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number


def _threat_level_from_confidence(confidence: float) -> str:
    """Map confidence onto the existing ThreatLevel vocabulary."""
    if confidence >= 0.95:
        return "critical"
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.40:
        return "medium"
    if confidence >= 0.10:
        return "low"
    return "none"


def _bootstrap_path() -> None:
    """Ensure repo root is importable when this file is executed directly."""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


if __name__ == "__main__":
    _bootstrap_path()
    raise SystemExit("PlanetaryImmuneSystem is a library; run test/immune/test_planetary_immune_system.py")
