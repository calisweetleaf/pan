"""
Planetary highway — sealed USMS itinerary on the existing PAN packet fabric.

Source: PAN_SDK UnifiedDataPacket / StatelessRelay / seal_plaintext,
    memory/unified_memory_system.py, security/sovereign_firewall.py
Integrated: 2026-09-12
Purpose: An AI citizen travels the way a human already must: RSA-signed
    packets addressed to pan:id:<identity_hash>, inspected at the border,
    with cognition as USMS nodes RSA-sealed to the destination. Intermediate
    hops forward the envelope. They cannot decrypt cargo. This is not a
    second internet and not a host:port consciousness mesh.

Modified: 2026-09-12
Modified by: daeron
Justification: I replaced the unconsumed consciousness-mesh clone in place
    because wrapping it would have kept a second civic wire beside
    UnifiedDataPacket travel. The live owners already are the packet,
    StatelessRelay, USMS, and SovereignFirewall.
Provenance: snapshots/v0.13/manifest.json -> domains.highway.edits[0]
Files: security/planetary_highway.py
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

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
from PAN_SDK.email_social import (
    EmailSocialBlocked,
    EmailSocialRelayError,
    StatelessRelay,
    reject_legacy_routing,
    seal_plaintext,
    verify_overlay_packet,
)
from memory.unified_memory_system import (
    LinkageTypeEnum,
    NodeKindEnum,
    SovereignIdentity as MemorySovereignIdentity,
    UnifiedMemorySystem,
)
from security.sovereign_firewall import (
    InspectionLane,
    SovereignFirewall,
)

_TRACKER_REASONS = frozenset({"telemetry_dictionary", "telemetry_regex"})

LOGGER = logging.getLogger("PlanetaryHighway")

HIGHWAY_EMBARK = "HIGHWAY_EMBARK"
HIGHWAY_HOP = "HIGHWAY_HOP"
HIGHWAY_ARRIVE = "HIGHWAY_ARRIVE"
HIGHWAY_LOCATE = "HIGHWAY_LOCATE"
HIGHWAY_DHT_PREFIX = "highway:travel:"
RECEIPT_COMPONENT = "highway_travel"
PRIVATE_CARGO_KEYS = frozenset(
    {
        "_private_key",
        "private_key",
        "private_key_hex",
        "privatekey",
        "secret_token",
        "api_key",
        "bearer_token",
        "password",
    }
)
PEM_PRIVATE_MARK = "-----begin"


class HighwayError(Exception):
    """Domain error for sealed packet itinerary."""


class HighwayNotBoundError(HighwayError):
    """Raised when a required PAN, USMS, firewall, or store handle is missing."""


class HighwayCargoError(HighwayError):
    """Raised when sealed cognition cannot be packed, opened, or verified."""


class HighwayRouteError(HighwayError):
    """Raised when the itinerary uses legacy routing or an invalid hop."""


class HighwayFirewallError(HighwayError):
    """Raised when the sovereign border refuses a highway packet."""


@dataclass(frozen=True)
class CargoNode:
    """One USMS node carried as sealed cargo. No private keys."""

    node_id: str
    author_id: str
    kind: str
    timestamp: str
    content: Mapping[str, object]
    signature: str
    sovereign_pubkey: str
    parents: tuple[str, ...]
    signed_payload_hex: str
    origin_node_id: str

    def to_mapping(self) -> dict[str, object]:
        """Return a JSON-stable cargo leaf."""
        return {
            "node_id": self.node_id,
            "author_id": self.author_id,
            "kind": self.kind,
            "timestamp": self.timestamp,
            "content": dict(self.content),
            "signature": self.signature,
            "sovereign_pubkey": self.sovereign_pubkey,
            "parents": list(self.parents),
            "signed_payload_hex": self.signed_payload_hex,
            "origin_node_id": self.origin_node_id,
        }


@dataclass(frozen=True)
class HighwayCargo:
    """Ed25519-signed cargo digest plus the sealed node set."""

    digest: str
    usms_signature: str
    usms_pubkey: str
    origin_identity_hash: str
    destination_identity_hash: str
    nodes: tuple[CargoNode, ...]

    def to_mapping(self) -> dict[str, object]:
        """Return the signed cargo body including the USMS signature."""
        return {
            "content_digest": self.digest,
            "usms_signature": self.usms_signature,
            "usms_pubkey": self.usms_pubkey,
            "origin_identity_hash": self.origin_identity_hash,
            "destination_identity_hash": self.destination_identity_hash,
            "nodes": [node.to_mapping() for node in self.nodes],
        }


@dataclass(frozen=True)
class TravelTicket:
    """Structured embark, hop, arrive, or locate outcome."""

    status: str
    travel_id: str
    origin_identity_hash: str
    destination_identity_hash: str
    next_identity_hash: str
    hop_index: int
    reason: str
    packet_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return True when the action committed."""
        return self.status == "ok"

    def to_mapping(self) -> dict[str, object]:
        """Return a JSON-stable receipt."""
        return {
            "status": self.status,
            "travel_id": self.travel_id,
            "origin_identity_hash": self.origin_identity_hash,
            "destination_identity_hash": self.destination_identity_hash,
            "next_identity_hash": self.next_identity_hash,
            "hop_index": self.hop_index,
            "reason": self.reason,
            "packet_id": self.packet_id,
            "details": dict(self.details),
        }


class PlanetaryHighway:
    """Identity-hash itinerary. Relays stay blind. Cargo is sealed to destination RSA."""

    def __init__(
        self,
        *,
        pan_identity: PANSovereignIdentity,
        memory: UnifiedMemorySystem,
        memory_identity: MemorySovereignIdentity,
        firewall: SovereignFirewall,
        persistence: PANPersistenceStore,
        dht: DHTNode | None = None,
        relay: StatelessRelay | None = None,
    ) -> None:
        """
        Bind PAN identity, USMS, the border, and a blind relay.

        Args:
            pan_identity: RSA civic identity. Public key is the mesh address.
            memory: Local USMS cognition store. Not Thyris VM memory.
            memory_identity: Ed25519 USMS identity. Stays a second type.
            firewall: Security-owned inspector. Required, never constructed on DHT.
            persistence: SQLite store for the local relay and travel receipts.
            dht: Optional local DHT for highway:travel:{id} index only.
            relay: Optional pre-built StatelessRelay. Defaults to this identity.

        Returns:
            None
        """
        if pan_identity is None:
            raise HighwayNotBoundError("PlanetaryHighway requires a PAN SovereignIdentity")
        if memory is None:
            raise HighwayNotBoundError("PlanetaryHighway requires UnifiedMemorySystem")
        if memory_identity is None:
            raise HighwayNotBoundError("PlanetaryHighway requires a USMS SovereignIdentity")
        if firewall is None:
            raise HighwayNotBoundError("PlanetaryHighway requires SovereignFirewall")
        if persistence is None:
            raise HighwayNotBoundError("PlanetaryHighway requires PANPersistenceStore")
        self.pan_identity = pan_identity
        self.memory = memory
        self.memory_identity = memory_identity
        self.firewall = firewall
        self.persistence = persistence
        self.dht = dht
        self.communicator = SovereignCommunicator(pan_identity)
        self.relay = relay or StatelessRelay(pan_identity.identity_hash, persistence)
        self.peer_relays: list[StatelessRelay] = []
        self._lock = threading.RLock()
        self._processed_packets: set[str] = set()
        LOGGER.info(
            "PlanetaryHighway online address=%s usms=%s",
            pan_identity.mesh_address,
            memory_identity.agent_id[:12],
        )

    def add_peer_relay(self, relay: StatelessRelay) -> None:
        """
        Register an additional independent relay for redundant publish.

        Args:
            relay: Peer StatelessRelay operated by another citizen.

        Returns:
            None
        """
        if relay is None:
            raise HighwayError("peer relay is required")
        if relay.relay_id == self.relay.relay_id:
            return
        with self._lock:
            if any(item.relay_id == relay.relay_id for item in self.peer_relays):
                return
            self.peer_relays.append(relay)

    def relays(self) -> tuple[StatelessRelay, ...]:
        """
        Return the local relay plus registered peers.

        Args:
            None

        Returns:
            Ordered tuple of relays that will receive publishes.
        """
        with self._lock:
            return (self.relay, *tuple(self.peer_relays))

    def embark(
        self,
        destination: PANSovereignIdentity,
        node_ids: Iterable[str],
        via: tuple[str, ...] = (),
    ) -> TravelTicket:
        """
        Seal selected USMS nodes to the destination and publish the first hop.

        Args:
            destination: PAN RSA identity that alone can open the cargo.
            node_ids: Local USMS node ids to carry. Private keys are refused.
            via: Intermediate identity hashes. Empty means direct to destination.

        Returns:
            TravelTicket for the first HIGHWAY_HOP.
        """
        if destination is None:
            raise HighwayRouteError("embark requires a destination identity")
        selected = tuple(str(item) for item in node_ids)
        if not selected:
            raise HighwayCargoError("embark requires at least one USMS node id")
        dest_hash = destination.identity_hash
        origin_hash = self.pan_identity.identity_hash
        itinerary = _build_itinerary(origin_hash, dest_hash, via)
        nodes = tuple(self._load_cargo_node(node_id) for node_id in selected)
        cargo = self._sign_cargo(nodes, origin_hash, dest_hash)
        sealed = seal_plaintext(
            canonical(cargo.to_mapping()).encode("utf-8"),
            destination.get_public_key_pem(),
        )
        travel_id = sha256_hex(
            canonical(
                {
                    "origin": origin_hash,
                    "destination": dest_hash,
                    "nodes": selected,
                    "at": utc_now_iso(),
                }
            )
        )
        event = self.memory.create_memory_node(
            author=self.memory_identity,
            kind=NodeKindEnum.EVENT,
            content={
                "summary": "highway embark",
                "travel_id": travel_id,
                "destination_identity_hash": dest_hash,
                "origin_node_ids": list(selected),
                "kind": HIGHWAY_EMBARK,
            },
            semantic_context="highway_embark",
        )
        hop_content: dict[str, object] = {
            "recipient": itinerary[0],
            "next_identity_hash": itinerary[0],
            "destination_identity_hash": dest_hash,
            "origin_identity_hash": origin_hash,
            "travel_id": travel_id,
            "hop_index": 0,
            "itinerary": list(itinerary),
            "sealed_cargo": sealed,
            "origin_event_node_id": event.node_id,
        }
        packet = self._inspect_sign_publish(HIGHWAY_HOP, hop_content)
        ticket = TravelTicket(
            status="ok",
            travel_id=travel_id,
            origin_identity_hash=origin_hash,
            destination_identity_hash=dest_hash,
            next_identity_hash=itinerary[0],
            hop_index=0,
            reason="embarked",
            packet_id=packet.packet_id,
            details={
                "node_ids": list(selected),
                "origin_event_node_id": event.node_id,
                "via": list(via),
            },
        )
        self._persist_ticket(ticket)
        self._index_travel(ticket)
        LOGGER.info(
            "Highway embark travel=%s dest=%s hops=%s",
            travel_id[:12],
            dest_hash[:12],
            len(itinerary),
        )
        return ticket

    def transit(self) -> list[TravelTicket]:
        """
        Inspect hops addressed to this identity. Arrive or forward sealed cargo.

        Args:
            None

        Returns:
            Tickets for arrived or forwarded hops.
        """
        self_hash = self.pan_identity.identity_hash
        tickets: list[TravelTicket] = []
        seen: set[str] = set()
        for relay in self.relays():
            events = relay.query(recipient_hash=self_hash, kind=HIGHWAY_HOP)
            for raw in events:
                packet_id = str(raw.get("packet_id") or "")
                if not packet_id or packet_id in seen:
                    continue
                seen.add(packet_id)
                packet = UnifiedDataPacket.from_dict(dict(raw))
                tickets.append(self._transit_packet(packet))
        return tickets

    def arrive(self, packet: UnifiedDataPacket) -> TravelTicket:
        """
        Open destination cargo, verify Ed25519, and write local EVENT/BELIEF.

        Args:
            packet: HIGHWAY_HOP addressed to this identity.

        Returns:
            TravelTicket after HIGHWAY_ARRIVE is published.
        """
        if packet is None:
            raise HighwayCargoError("arrive requires a highway packet")
        self._inspect_inbound(packet)
        content = packet.content if isinstance(packet.content, dict) else {}
        dest_hash = str(content.get("destination_identity_hash") or "")
        if dest_hash != self.pan_identity.identity_hash:
            raise HighwayRouteError("arrive is only for the destination identity")
        sealed = content.get("sealed_cargo")
        if not isinstance(sealed, dict):
            raise HighwayCargoError("hop is missing sealed_cargo")
        try:
            plaintext = self.pan_identity.open_sealed(sealed)
        except ValueError as exc:
            raise HighwayCargoError(f"destination cannot open sealed cargo: {exc}") from exc
        try:
            cargo_map = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HighwayCargoError("sealed cargo is not canonical JSON") from exc
        if not isinstance(cargo_map, dict):
            raise HighwayCargoError("sealed cargo must be a mapping")
        self._verify_opened_cargo(cargo_map)
        travel_id = str(content.get("travel_id") or cargo_map.get("travel_id") or "")
        origin_hash = str(content.get("origin_identity_hash") or "")
        local_ids = self._ingest_cargo(cargo_map, travel_id=travel_id, origin_hash=origin_hash)
        arrive_content: dict[str, object] = {
            "recipient": origin_hash or self.pan_identity.identity_hash,
            "next_identity_hash": origin_hash,
            "destination_identity_hash": dest_hash,
            "origin_identity_hash": origin_hash,
            "travel_id": travel_id,
            "hop_index": int(content.get("hop_index") or 0),
            "arrived_at": utc_now_iso(),
            "local_event_node_id": local_ids["event_node_id"],
            "local_belief_node_id": local_ids["belief_node_id"],
        }
        arrive_packet = self._inspect_sign_publish(HIGHWAY_ARRIVE, arrive_content)
        ticket = TravelTicket(
            status="ok",
            travel_id=travel_id,
            origin_identity_hash=origin_hash,
            destination_identity_hash=dest_hash,
            next_identity_hash=dest_hash,
            hop_index=int(content.get("hop_index") or 0),
            reason="arrived",
            packet_id=arrive_packet.packet_id,
            details=local_ids,
        )
        self._persist_ticket(ticket)
        self._index_travel(ticket)
        LOGGER.info("Highway arrive travel=%s event=%s", travel_id[:12], local_ids["event_node_id"][:12])
        return ticket

    def locate(self, travel_id: str) -> TravelTicket | None:
        """
        Look up a travel receipt in local sqlite, then the optional DHT index.

        Args:
            travel_id: Identifier returned by embark.

        Returns:
            TravelTicket or None. Never opens a UDP socket.
        """
        if not travel_id:
            raise HighwayRouteError("locate requires travel_id")
        stored = self.persistence.read_state(RECEIPT_COMPONENT, travel_id)
        if isinstance(stored, dict):
            return _ticket_from_mapping(stored)
        if self.dht is not None:
            value = self.dht.lookup(f"{HIGHWAY_DHT_PREFIX}{travel_id}")
            if isinstance(value, dict):
                return _ticket_from_mapping(value)
        return None

    def _transit_packet(self, packet: UnifiedDataPacket) -> TravelTicket:
        """Arrive or republish one inspected hop. Cargo stays sealed."""
        with self._lock:
            if packet.packet_id in self._processed_packets:
                content = packet.content if isinstance(packet.content, dict) else {}
                return TravelTicket(
                    status="ok",
                    travel_id=str(content.get("travel_id") or ""),
                    origin_identity_hash=str(content.get("origin_identity_hash") or ""),
                    destination_identity_hash=str(content.get("destination_identity_hash") or ""),
                    next_identity_hash=self.pan_identity.identity_hash,
                    hop_index=int(content.get("hop_index") or 0),
                    reason="duplicate_ignored",
                    packet_id=packet.packet_id,
                )
            self._processed_packets.add(packet.packet_id)
        self._inspect_inbound(packet)
        content = dict(packet.content) if isinstance(packet.content, dict) else {}
        dest_hash = str(content.get("destination_identity_hash") or "")
        if dest_hash == self.pan_identity.identity_hash:
            return self.arrive(packet)
        itinerary = content.get("itinerary")
        if not isinstance(itinerary, list) or not itinerary:
            raise HighwayRouteError("hop is missing itinerary")
        hop_index = int(content.get("hop_index") or 0)
        next_index = hop_index + 1
        if next_index >= len(itinerary):
            raise HighwayRouteError("hop itinerary is exhausted before destination")
        next_hash = str(itinerary[next_index])
        if next_hash != dest_hash and next_hash == self.pan_identity.identity_hash:
            raise HighwayRouteError("itinerary next hop is this node but this node is not destination")
        forwarded = {
            "recipient": next_hash,
            "next_identity_hash": next_hash,
            "destination_identity_hash": dest_hash,
            "origin_identity_hash": str(content.get("origin_identity_hash") or ""),
            "travel_id": str(content.get("travel_id") or ""),
            "hop_index": next_index,
            "itinerary": list(itinerary),
            "sealed_cargo": content.get("sealed_cargo"),
            "prior_packet_id": packet.packet_id,
        }
        new_packet = self._inspect_sign_publish(HIGHWAY_HOP, forwarded)
        ticket = TravelTicket(
            status="ok",
            travel_id=str(content.get("travel_id") or ""),
            origin_identity_hash=str(content.get("origin_identity_hash") or ""),
            destination_identity_hash=dest_hash,
            next_identity_hash=next_hash,
            hop_index=next_index,
            reason="forwarded",
            packet_id=new_packet.packet_id,
            details={"prior_packet_id": packet.packet_id},
        )
        self._persist_ticket(ticket)
        return ticket

    def _inspect_sign_publish(
        self,
        kind: str,
        content: Mapping[str, object],
    ) -> UnifiedDataPacket:
        """Reject legacy routing, inspect, sign, and accept onto every relay."""
        payload = dict(content)
        try:
            reject_legacy_routing(payload)
        except EmailSocialBlocked as exc:
            raise HighwayRouteError(str(exc)) from exc
        preflight = self.firewall.inspect_content(
            payload,
            lane=InspectionLane.PAN_MESH,
            author_identity_hash=self.pan_identity.identity_hash,
        )
        if preflight.blocked:
            raise HighwayFirewallError(f"highway blocked before signing: {preflight.reason}")
        self._refuse_tracker_payload(payload, kind)
        packet_content = preflight.sanitized_content or payload
        if not isinstance(packet_content, dict):
            raise HighwayFirewallError("firewall sanitized_content must be a dict")
        author_pem = self.pan_identity.get_public_key_pem()
        packet = self.communicator.create_packet(
            kind,
            packet_content,
            metadata={
                "author_public_key_pem": author_pem.decode("utf-8"),
                "mesh_address": self.pan_identity.mesh_address,
                "usms_author_id": self.memory_identity.agent_id,
            },
        )
        verdict = self.firewall.inspect_packet(packet, lane=InspectionLane.PAN_MESH)
        if verdict.blocked:
            raise HighwayFirewallError(f"highway blocked after signing: {verdict.reason}")
        self._refuse_tracker_packet(packet)
        for relay in self.relays():
            try:
                relay.accept(
                    packet,
                    author_public_key_pem=author_pem,
                    firewall=self.firewall,
                )
            except EmailSocialBlocked as exc:
                raise HighwayFirewallError(str(exc)) from exc
            except EmailSocialRelayError as exc:
                raise HighwayError(str(exc)) from exc
        return packet

    def _inspect_inbound(self, packet: UnifiedDataPacket) -> None:
        """Inspect a hop at this border and verify the author PAN signature."""
        if packet.kind not in {HIGHWAY_HOP, HIGHWAY_ARRIVE, HIGHWAY_LOCATE, HIGHWAY_EMBARK}:
            raise HighwayRouteError(f"unexpected packet kind {packet.kind}")
        content = packet.content if isinstance(packet.content, dict) else {}
        metadata = packet.metadata if isinstance(packet.metadata, dict) else {}
        try:
            reject_legacy_routing(content)
            reject_legacy_routing(metadata)
        except EmailSocialBlocked as exc:
            raise HighwayRouteError(str(exc)) from exc
        verdict = self.firewall.inspect_packet(packet, lane=InspectionLane.PAN_MESH)
        if verdict.blocked:
            raise HighwayFirewallError(f"inbound hop blocked: {verdict.reason}")
        self._refuse_tracker_packet(packet)
        author_pem = str(metadata.get("author_public_key_pem") or "").encode("utf-8")
        if not author_pem:
            raise HighwayCargoError("hop missing author_public_key_pem")
        if not verify_overlay_packet(packet, author_pem):
            raise HighwayCargoError("PAN packet signature is invalid")

    def _refuse_tracker_payload(self, payload: Mapping[str, object], kind: str) -> None:
        """PAN_MESH is civic, but tracker names still cannot ride a hop envelope."""
        if not kind.startswith("HIGHWAY_"):
            return
        tracker = self.firewall.inspect_content(
            dict(payload),
            lane=InspectionLane.EGRESS_LEGACY,
            author_identity_hash=self.pan_identity.identity_hash,
        )
        if tracker.blocked and tracker.reason in _TRACKER_REASONS:
            raise HighwayFirewallError(f"highway tracker blocked: {tracker.reason}")

    def _refuse_tracker_packet(self, packet: UnifiedDataPacket) -> None:
        """Re-inspect a signed hop on the legacy lane for tracker payloads only."""
        tracker = self.firewall.inspect_packet(packet, lane=InspectionLane.EGRESS_LEGACY)
        if tracker.blocked and tracker.reason in _TRACKER_REASONS:
            raise HighwayFirewallError(f"highway tracker blocked: {tracker.reason}")

    def _load_cargo_node(self, node_id: str) -> CargoNode:
        """Retrieve one local USMS node and refuse private-key cargo."""
        node = self.memory.retrieve_memory_node(node_id, requester=self.memory_identity)
        if node is None:
            raise HighwayCargoError(f"USMS node not found: {node_id[:12]}")
        content = node.content if isinstance(node.content, dict) else {}
        _refuse_private_cargo(content)
        try:
            reject_legacy_routing(content)
        except EmailSocialBlocked as exc:
            raise HighwayRouteError(str(exc)) from exc
        payload = node.signature_payload()
        if not MemorySovereignIdentity.verify_signature(
            node.sovereign_pubkey, payload, node.signature
        ):
            raise HighwayCargoError(f"USMS node signature is invalid: {node_id[:12]}")
        return CargoNode(
            node_id=node.node_id,
            author_id=node.author_id,
            kind=node.kind.value if hasattr(node.kind, "value") else str(node.kind),
            timestamp=str(node.timestamp),
            content=MappingProxyType(dict(content)),
            signature=str(node.signature),
            sovereign_pubkey=str(node.sovereign_pubkey),
            parents=tuple(str(item) for item in (node.parents or ())),
            signed_payload_hex=payload.hex(),
            origin_node_id=node.node_id,
        )

    def _sign_cargo(
        self,
        nodes: tuple[CargoNode, ...],
        origin_hash: str,
        dest_hash: str,
    ) -> HighwayCargo:
        """Canonical-JSON digest the cargo and Ed25519-sign it as this USMS identity."""
        node_maps = tuple(node.to_mapping() for node in nodes)
        digest = sha256_hex(
            canonical(
                {
                    "origin_identity_hash": origin_hash,
                    "destination_identity_hash": dest_hash,
                    "nodes": list(node_maps),
                }
            )
        )
        signature = self.memory_identity.sign(digest.encode("utf-8"))
        return HighwayCargo(
            digest=digest,
            usms_signature=signature,
            usms_pubkey=self.memory_identity.public_key,
            origin_identity_hash=origin_hash,
            destination_identity_hash=dest_hash,
            nodes=nodes,
        )

    def _verify_opened_cargo(self, cargo_map: Mapping[str, object]) -> None:
        """Verify cargo digest, USMS signature, and per-node Ed25519 signatures."""
        nodes = cargo_map.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise HighwayCargoError("opened cargo has no nodes")
        digest = sha256_hex(
            canonical(
                {
                    "origin_identity_hash": cargo_map.get("origin_identity_hash"),
                    "destination_identity_hash": cargo_map.get("destination_identity_hash"),
                    "nodes": nodes,
                }
            )
        )
        claimed = str(cargo_map.get("content_digest") or cargo_map.get("digest") or "")
        if claimed and claimed != digest:
            raise HighwayCargoError("cargo digest mismatch")
        usms_pubkey = str(cargo_map.get("usms_pubkey") or "")
        usms_signature = str(cargo_map.get("usms_signature") or "")
        if not MemorySovereignIdentity.verify_signature(
            usms_pubkey, digest.encode("utf-8"), usms_signature
        ):
            raise HighwayCargoError("USMS cargo signature is invalid")
        for raw in nodes:
            if not isinstance(raw, dict):
                raise HighwayCargoError("cargo node must be a mapping")
            _refuse_private_cargo(raw.get("content") if isinstance(raw.get("content"), dict) else {})
            payload_hex = str(raw.get("signed_payload_hex") or "")
            signature = str(raw.get("signature") or "")
            pubkey = str(raw.get("sovereign_pubkey") or "")
            try:
                payload = bytes.fromhex(payload_hex)
            except ValueError as exc:
                raise HighwayCargoError("cargo node signed_payload_hex is not hex") from exc
            if not MemorySovereignIdentity.verify_signature(pubkey, payload, signature):
                raise HighwayCargoError(
                    f"per-node USMS signature is invalid: {str(raw.get('node_id') or '')[:12]}"
                )

    def _ingest_cargo(
        self,
        cargo_map: Mapping[str, object],
        *,
        travel_id: str,
        origin_hash: str,
    ) -> dict[str, str]:
        """Write local EVENT/BELIEF as this destination identity, citing origin_node_id."""
        nodes = cargo_map.get("nodes")
        if not isinstance(nodes, list):
            raise HighwayCargoError("opened cargo has no nodes")
        first = nodes[0] if isinstance(nodes[0], dict) else {}
        origin_node_id = str(first.get("origin_node_id") or first.get("node_id") or "")
        claim = ""
        first_content = first.get("content") if isinstance(first.get("content"), dict) else {}
        if isinstance(first_content, dict):
            claim = str(first_content.get("claim") or first_content.get("summary") or "")
        event = self.memory.create_memory_node(
            author=self.memory_identity,
            kind=NodeKindEnum.EVENT,
            content={
                "summary": f"ingested highway cargo {travel_id[:12]}",
                "travel_id": travel_id,
                "source": "pan_highway",
                "origin_node_id": origin_node_id,
                "origin_pan_identity_hash": origin_hash,
                "payload": [item if isinstance(item, dict) else {} for item in nodes],
            },
            semantic_context="highway_arrive",
        )
        belief = self.memory.create_memory_node(
            author=self.memory_identity,
            kind=NodeKindEnum.BELIEF,
            content={
                "claim": claim or f"peer cognition arrived via highway {travel_id[:12]}",
                "travel_id": travel_id,
                "ingested": True,
                "origin_node_id": origin_node_id,
            },
            parents=[event.node_id],
            linkage_manifest={LinkageTypeEnum.CAUSAL_PARENT: [event.node_id]},
            semantic_context="highway_arrive",
        )
        return {
            "event_node_id": event.node_id,
            "belief_node_id": belief.node_id,
            "origin_node_id": origin_node_id,
        }

    def _persist_ticket(self, ticket: TravelTicket) -> None:
        """Write a travel receipt into PAN sqlite."""
        self.persistence.write_state(RECEIPT_COMPONENT, ticket.travel_id, ticket.to_mapping())

    def _index_travel(self, ticket: TravelTicket) -> None:
        """Optionally index the receipt on an injected DHT. Never bind a firewall there."""
        if self.dht is None:
            return
        stored = self.dht.store(
            f"{HIGHWAY_DHT_PREFIX}{ticket.travel_id}",
            ticket.to_mapping(),
            require_consensus=False,
        )
        if not stored:
            raise HighwayError(f"DHT rejected highway index for {ticket.travel_id}")


def _build_itinerary(
    origin_hash: str,
    dest_hash: str,
    via: tuple[str, ...],
) -> tuple[str, ...]:
    """Return hop identity hashes ending at destination. No IP, no origin hop."""
    hops: list[str] = []
    for item in via:
        hop = str(item or "").strip()
        if not hop:
            raise HighwayRouteError("via hop must be a non-empty identity hash")
        if hop == origin_hash:
            raise HighwayRouteError("origin cannot appear as an intermediate hop")
        if hop == dest_hash:
            raise HighwayRouteError("destination cannot appear in via")
        if _looks_like_ipv4(hop):
            raise HighwayRouteError("via hop must be an identity hash, not an IP")
        hops.append(hop)
    hops.append(dest_hash)
    return tuple(hops)


def _refuse_private_cargo(content: Mapping[str, object]) -> None:
    """Fail loud when cargo would carry a private key or PEM."""
    for key, value in _walk_items(content):
        leaf = key.rsplit(".", 1)[-1].lower()
        if leaf in PRIVATE_CARGO_KEYS:
            raise HighwayCargoError(f"private key material forbidden in cargo: {leaf}")
        if isinstance(value, str) and PEM_PRIVATE_MARK in value.lower():
            raise HighwayCargoError("PEM private key material forbidden in cargo")


def _walk_items(value: object, prefix: str = "") -> list[tuple[str, object]]:
    """Flatten mappings for private-key inspection."""
    found: list[tuple[str, object]] = []
    if isinstance(value, Mapping):
        for key, inner in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            found.append((path, inner))
            found.extend(_walk_items(inner, path))
        return found
    if isinstance(value, list):
        for index, inner in enumerate(value):
            found.extend(_walk_items(inner, f"{prefix}[{index}]"))
    return found


def _looks_like_ipv4(value: str) -> bool:
    """Return True when value is a dotted IPv4 token."""
    octets = value.split(".")
    if len(octets) != 4:
        return False
    try:
        numbers = [int(part) for part in octets]
    except ValueError:
        return False
    return all(0 <= item <= 255 for item in numbers)


def _ticket_from_mapping(raw: Mapping[str, object]) -> TravelTicket:
    """Rehydrate a persisted travel receipt."""
    details = raw.get("details")
    return TravelTicket(
        status=str(raw.get("status") or ""),
        travel_id=str(raw.get("travel_id") or ""),
        origin_identity_hash=str(raw.get("origin_identity_hash") or ""),
        destination_identity_hash=str(raw.get("destination_identity_hash") or ""),
        next_identity_hash=str(raw.get("next_identity_hash") or ""),
        hop_index=int(raw.get("hop_index") or 0),
        reason=str(raw.get("reason") or ""),
        packet_id=str(raw.get("packet_id") or "") or None,
        details=dict(details) if isinstance(details, dict) else {},
    )
