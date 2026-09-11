"""
Sovereign email/social overlay — Nostr-inspired stateless cryptographic relays.

Source: docs/research/Building a Sovereign Digital Nation.md section 5
Integrated: 2026-09-10
Purpose: Identity-hash addressing, UnifiedDataPacket transport, hybrid
    encryption to the recipient public key, client-side firewall inspection,
    and blind relays that never decrypt. Legacy IP routing keys are rejected.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PAN_SDK.PAN_SDK import (
    PANPersistenceStore,
    SovereignCommunicator,
    SovereignIdentity,
    UnifiedDataPacket,
    canonical,
    sha256_hex,
    utc_now_iso,
)
from security.sovereign_firewall import (
    InspectionAction,
    InspectionLane,
    SovereignFirewall,
)

LOGGER = logging.getLogger("EmailSocial")

MAIL_KIND = "MAIL_SEALED"
SOCIAL_KIND = "SOCIAL_BROADCAST"
KNOCK_KIND = "DISCOVERY_KNOCK"
CALLBACK_KIND = "DISCOVERY_CALLBACK"
RECEIPT_KIND = "MAIL_RECEIPT"
SEAL_ALG = "rsa-oaep-sha256+aes-256-gcm"
DEFAULT_KNOCK_TTL_SECONDS = 30

FORBIDDEN_ROUTE_KEYS = frozenset(
    {
        "carrier_msisdn",
        "default_gateway",
        "dest_ip",
        "destination_ip",
        "host",
        "iccid",
        "imsi",
        "ip",
        "ip_address",
        "ipv4",
        "ipv6",
        "isp_route",
        "legacy_ip_route",
        "next_hop",
        "next_hop_ip",
        "port",
        "source_ip",
        "tcp_host",
        "udp_host",
    }
)


class EmailSocialError(Exception):
    """Domain error for the email/social overlay."""


class EmailSocialBlocked(EmailSocialError):
    """Raised when the firewall or routing policy refuses a packet."""


class EmailSocialCryptoError(EmailSocialError):
    """Raised when sealing or opening a message fails."""


class EmailSocialRelayError(EmailSocialError):
    """Raised when a relay refuses or cannot store an event."""


class EventKind(str, Enum):
    """Overlay event kinds carried as UnifiedDataPacket.kind."""

    MAIL = MAIL_KIND
    SOCIAL = SOCIAL_KIND
    KNOCK = KNOCK_KIND
    CALLBACK = CALLBACK_KIND
    RECEIPT = RECEIPT_KIND


@dataclass
class EmailSocialResult:
    """Structured publish/fetch outcome."""

    status: str
    reason: str
    packet_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return True when the action committed."""
        return self.status == "ok"


@dataclass
class OpenedMail:
    """Decrypted mail after client-side fetch."""

    packet_id: str
    sender_hash: str
    subject: str
    body: str
    timestamp: str


def mesh_address_for(identity: SovereignIdentity) -> str:
    """
    Return the public-key-derived PAN mesh address.

    Args:
        identity: PAN RSA identity.

    Returns:
        pan:id:<identity_hash> address string.
    """
    return identity.mesh_address


def seal_plaintext(plaintext: bytes, recipient_public_key_pem: bytes) -> dict[str, str]:
    """
    Seal bytes to a recipient public key using AES-256-GCM plus RSA-OAEP.

    Args:
        plaintext: Message bytes. May be any length.
        recipient_public_key_pem: Recipient SubjectPublicKeyInfo PEM.

    Returns:
        JSON-stable envelope mapping.
    """
    if not plaintext:
        raise EmailSocialCryptoError("plaintext must be non-empty")
    if not recipient_public_key_pem:
        raise EmailSocialCryptoError("recipient_public_key_pem is required")
    aes_key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(aes_key).encrypt(nonce, plaintext, None)
    public_key = serialization.load_pem_public_key(recipient_public_key_pem)
    wrapped = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return {
        "alg": SEAL_ALG,
        "wrapped_key": base64.b64encode(wrapped).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def verify_overlay_packet(packet: UnifiedDataPacket, author_public_key_pem: bytes) -> bool:
    """
    Verify integrity and the RSA-PSS signature using the author's public key.

    Args:
        packet: Signed overlay packet.
        author_public_key_pem: Author SubjectPublicKeyInfo PEM.

    Returns:
        True only when integrity and signature both hold.
    """
    if packet is None or packet.signature is None:
        return False
    if not packet.verify_integrity():
        return False
    packet_dict = packet.to_dict()
    packet_dict["signature"] = None
    packet_data = canonical(packet_dict).encode("utf-8")
    try:
        public_key = serialization.load_pem_public_key(author_public_key_pem)
        public_key.verify(
            packet.signature,
            packet_data,
            padding.PSS(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def reject_legacy_routing(payload: Mapping[str, object]) -> None:
    """
    Reject legacy IP/carrier routing artifacts anywhere in a payload.

    Args:
        payload: Nested mapping about to be published.

    Returns:
        None
    """
    for key, value in _walk_items(payload):
        leaf = key.rsplit(".", 1)[-1].lower()
        if leaf in FORBIDDEN_ROUTE_KEYS:
            raise EmailSocialBlocked(f"legacy routing key forbidden: {leaf}")
        if isinstance(value, str) and leaf in {"address", "endpoint", "callback"}:
            if _looks_like_ipv4(value):
                raise EmailSocialBlocked(f"legacy IP value in {leaf}")


def _looks_like_ipv4(value: str) -> bool:
    """Return True when value contains a dotted IPv4 token."""
    parts = value.replace("/", " ").replace(":", " ").split()
    for token in parts:
        octets = token.split(".")
        if len(octets) != 4:
            continue
        try:
            numbers = [int(part) for part in octets]
        except ValueError:
            continue
        if all(0 <= item <= 255 for item in numbers):
            return True
    return False


def _walk_items(value: object, prefix: str = "") -> list[tuple[str, object]]:
    """Flatten mappings and lists into dotted paths."""
    found: list[tuple[str, object]] = []
    if isinstance(value, Mapping):
        for key, inner in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            found.append((path, inner))
            found.extend(_walk_items(inner, path))
        return found
    if isinstance(value, list):
        for index, inner in enumerate(value):
            path = f"{prefix}[{index}]"
            found.append((path, inner))
            found.extend(_walk_items(inner, path))
    return found


class StatelessRelay:
    """Blind store-and-forward. Relays verify signatures and do not decrypt."""

    def __init__(self, relay_id: str, persistence: PANPersistenceStore) -> None:
        """
        Open a relay backed by PAN sqlite kv state.

        Args:
            relay_id: Operator identity hash for this relay.
            persistence: SQLite-backed PAN store.

        Returns:
            None
        """
        if not relay_id:
            raise EmailSocialRelayError("relay_id is required")
        if persistence is None:
            raise EmailSocialRelayError("StatelessRelay requires PANPersistenceStore")
        self.relay_id = relay_id
        self.persistence = persistence
        self._lock = threading.RLock()
        self._events: dict[str, dict[str, object]] = {}
        self.hydrate_from_persistence()
        LOGGER.info("StatelessRelay online id=%s events=%s", relay_id[:12], len(self._events))

    def hydrate_from_persistence(self) -> None:
        """Reload stored events from sqlite."""
        stored = self.persistence.load_component(self._component())
        self._events = {}
        if stored:
            for event_id, raw in stored.items():
                if isinstance(raw, dict):
                    self._events[str(event_id)] = dict(raw)

    def accept(
        self,
        packet: UnifiedDataPacket,
        *,
        author_public_key_pem: bytes,
        firewall: SovereignFirewall,
    ) -> EmailSocialResult:
        """
        Accept a signed packet after signature and firewall checks.

        Args:
            packet: Signed overlay packet.
            author_public_key_pem: Author public key used to verify the signature.
            firewall: Security-owned inspector. Relays stay content-blind.

        Returns:
            EmailSocialResult. Duplicate packet ids are idempotent ok.
        """
        if packet is None:
            raise EmailSocialRelayError("relay accept requires a packet")
        if not packet.verify_integrity():
            raise EmailSocialRelayError("packet failed integrity check")
        if not verify_overlay_packet(packet, author_public_key_pem):
            raise EmailSocialRelayError("packet signature is invalid")
        reject_legacy_routing(packet.content if isinstance(packet.content, dict) else {})
        reject_legacy_routing(packet.metadata if isinstance(packet.metadata, dict) else {})
        verdict = firewall.inspect_packet(packet, lane=InspectionLane.PAN_MESH)
        if verdict.blocked:
            raise EmailSocialBlocked(f"relay firewall blocked: {verdict.reason}")
        payload = packet.to_dict()
        with self._lock:
            if packet.packet_id in self._events:
                return EmailSocialResult(
                    status="ok",
                    reason="duplicate_ignored",
                    packet_id=packet.packet_id,
                )
            self._events[packet.packet_id] = payload
            self.persistence.write_state(self._component(), packet.packet_id, payload)
        LOGGER.info("Relay %s stored %s %s", self.relay_id[:12], packet.kind, packet.packet_id[:12])
        return EmailSocialResult(
            status="ok",
            reason="stored",
            packet_id=packet.packet_id,
            details={"relay_id": self.relay_id, "kind": packet.kind},
        )

    def query(
        self,
        *,
        recipient_hash: str | None = None,
        kind: str | None = None,
        include_expired: bool = False,
    ) -> list[dict[str, object]]:
        """
        Return stored events filtered by recipient and kind.

        Args:
            recipient_hash: If set, only events addressed to this identity hash.
            kind: Optional UnifiedDataPacket kind filter.
            include_expired: If False, drop expired knocks.

        Returns:
            Copies of stored packet mappings.
        """
        now = datetime.now(timezone.utc)
        found: list[dict[str, object]] = []
        with self._lock:
            for payload in self._events.values():
                if kind is not None and str(payload.get("kind") or "") != kind:
                    continue
                content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
                if recipient_hash is not None:
                    addressed = str(content.get("recipient") or "")
                    if addressed and addressed != recipient_hash:
                        continue
                    if not addressed and str(payload.get("author_identity_hash") or "") != recipient_hash:
                        if kind != SOCIAL_KIND:
                            continue
                if not include_expired and str(payload.get("kind") or "") == KNOCK_KIND:
                    expires_at = str(content.get("expires_at") or "")
                    if expires_at and _parse_iso(expires_at) < now:
                        continue
                found.append(dict(payload))
        return found

    def drop_expired_knocks(self) -> int:
        """Delete expired discovery knocks. Relays do not keep stale presence."""
        now = datetime.now(timezone.utc)
        removed = 0
        with self._lock:
            expired_ids = []
            for event_id, payload in self._events.items():
                if str(payload.get("kind") or "") != KNOCK_KIND:
                    continue
                content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
                expires_at = str(content.get("expires_at") or "")
                if expires_at and _parse_iso(expires_at) < now:
                    expired_ids.append(event_id)
            for event_id in expired_ids:
                del self._events[event_id]
                self.persistence.delete_state(self._component(), event_id)
                removed += 1
        return removed

    def _component(self) -> str:
        """Kv component name unique to this relay."""
        return f"email_relay_{self.relay_id}"


def _parse_iso(value: str) -> datetime:
    """Parse an ISO timestamp, defaulting naive values to UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class EmailSocialNode:
    """Client overlay: encrypt, firewall, publish to multiple blind relays."""

    def __init__(
        self,
        identity: SovereignIdentity,
        persistence: PANPersistenceStore,
        firewall: SovereignFirewall,
        relay: StatelessRelay | None = None,
    ) -> None:
        """
        Bind a citizen client to identity, sqlite, firewall, and a local relay.

        Args:
            identity: Sender/recipient PAN identity. Public key is the address.
            persistence: SQLite store for the local relay and receipts.
            firewall: Security-owned inspector required before transmission.
            relay: Optional pre-built local relay. Defaults to one keyed by identity.

        Returns:
            None
        """
        if identity is None:
            raise EmailSocialError("EmailSocialNode requires a SovereignIdentity")
        if persistence is None:
            raise EmailSocialError("EmailSocialNode requires PANPersistenceStore")
        if firewall is None:
            raise EmailSocialError("EmailSocialNode requires SovereignFirewall")
        self.identity = identity
        self.persistence = persistence
        self.firewall = firewall
        self.communicator = SovereignCommunicator(identity)
        self.relay = relay or StatelessRelay(identity.identity_hash, persistence)
        self.peer_relays: list[StatelessRelay] = []
        self._lock = threading.RLock()
        LOGGER.info(
            "EmailSocialNode online address=%s relay=%s",
            identity.mesh_address,
            self.relay.relay_id[:12],
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
            raise EmailSocialError("peer relay is required")
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

    def send_mail(
        self,
        *,
        recipient: SovereignIdentity,
        body: str,
        subject: str = "",
    ) -> EmailSocialResult:
        """
        Encrypt a private message to the recipient identity and publish to relays.

        Args:
            recipient: Destination PAN identity (public key is the address).
            body: Plaintext body. Sealed before it touches a relay.
            subject: Optional subject, sealed with the body.

        Returns:
            EmailSocialResult including packet_id.
        """
        if recipient is None:
            raise EmailSocialError("recipient identity is required")
        if not body:
            raise EmailSocialError("mail body must be non-empty")
        inner = {
            "subject": subject,
            "body": body,
            "from": self.identity.identity_hash,
            "to": recipient.identity_hash,
        }
        reject_legacy_routing(inner)
        sealed = seal_plaintext(
            canonical(inner).encode("utf-8"),
            recipient.get_public_key_pem(),
        )
        content: dict[str, object] = {
            "recipient": recipient.identity_hash,
            "address": recipient.mesh_address,
            "sealed": sealed,
        }
        packet = self._package_and_publish(MAIL_KIND, content)
        return EmailSocialResult(
            status="ok",
            reason="mail_published",
            packet_id=packet.packet_id,
            details={"recipient": recipient.identity_hash, "relays": len(self.relays())},
        )

    def broadcast_social(self, text: str, *, feed: str = "public") -> EmailSocialResult:
        """
        Publish a signed public social event. Relays remain moderation-blind.

        Args:
            text: Public post body. Inspected client-side before send.
            feed: Named feed label.

        Returns:
            EmailSocialResult including packet_id.
        """
        if not text:
            raise EmailSocialError("social text must be non-empty")
        content: dict[str, object] = {
            "text": text,
            "feed": feed,
            "author": self.identity.identity_hash,
            "address": self.identity.mesh_address,
        }
        packet = self._package_and_publish(SOCIAL_KIND, content)
        return EmailSocialResult(
            status="ok",
            reason="social_published",
            packet_id=packet.packet_id,
            details={"feed": feed},
        )

    def knock(
        self,
        *,
        recipient_hash: str,
        tunnel_id: str,
        ttl_seconds: int = DEFAULT_KNOCK_TTL_SECONDS,
    ) -> EmailSocialResult:
        """
        Publish an ephemeral discovery knock addressed by identity, never by IP.

        Args:
            recipient_hash: Intended peer identity hash.
            tunnel_id: Opaque capability the peer must echo.
            ttl_seconds: Positive lifetime before relays drop the knock.

        Returns:
            EmailSocialResult including expires_at.
        """
        if not recipient_hash or not tunnel_id:
            raise EmailSocialError("knock requires recipient_hash and tunnel_id")
        if ttl_seconds < 1:
            raise EmailSocialError("knock ttl_seconds must be >= 1")
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        content: dict[str, object] = {
            "recipient": recipient_hash,
            "tunnel_id": tunnel_id,
            "from": self.identity.identity_hash,
            "address": self.identity.mesh_address,
            "expires_at": expires.isoformat(),
        }
        packet = self._package_and_publish(KNOCK_KIND, content)
        return EmailSocialResult(
            status="ok",
            reason="knock_published",
            packet_id=packet.packet_id,
            details={"expires_at": content["expires_at"], "tunnel_id": tunnel_id},
        )

    def callback(self, *, recipient: SovereignIdentity, tunnel_id: str) -> EmailSocialResult:
        """
        Answer a knock with a callback that still carries only identity addresses.

        Args:
            recipient: Peer who knocked.
            tunnel_id: Echo of the knock capability.

        Returns:
            EmailSocialResult.
        """
        if recipient is None or not tunnel_id:
            raise EmailSocialError("callback requires recipient and tunnel_id")
        content: dict[str, object] = {
            "recipient": recipient.identity_hash,
            "tunnel_id": tunnel_id,
            "from": self.identity.identity_hash,
            "address": recipient.mesh_address,
            "accepted": True,
        }
        packet = self._package_and_publish(CALLBACK_KIND, content)
        return EmailSocialResult(
            status="ok",
            reason="callback_published",
            packet_id=packet.packet_id,
            details={"tunnel_id": tunnel_id},
        )

    def ack_mail(self, *, sender: SovereignIdentity, ref_packet_id: str) -> EmailSocialResult:
        """
        Publish a delivery receipt for a fetched mail packet.

        Args:
            sender: Original mail author who should receive the receipt.
            ref_packet_id: Packet id of the mail being acknowledged.

        Returns:
            EmailSocialResult including the receipt packet_id.
        """
        if sender is None or not ref_packet_id:
            raise EmailSocialError("ack_mail requires sender and ref_packet_id")
        content: dict[str, object] = {
            "recipient": sender.identity_hash,
            "ref_packet_id": ref_packet_id,
            "from": self.identity.identity_hash,
        }
        packet = self._package_and_publish(RECEIPT_KIND, content)
        return EmailSocialResult(
            status="ok",
            reason="receipt_published",
            packet_id=packet.packet_id,
            details={"ref_packet_id": ref_packet_id},
        )

    def fetch_mail(self) -> list[OpenedMail]:
        """
        Pull sealed mail addressed to this identity from every relay and decrypt.

        Args:
            None

        Returns:
            OpenedMail list, de-duplicated by packet_id.
        """
        seen: set[str] = set()
        opened: list[OpenedMail] = []
        for relay in self.relays():
            for raw in relay.query(recipient_hash=self.identity.identity_hash, kind=MAIL_KIND):
                packet_id = str(raw.get("packet_id") or "")
                if not packet_id or packet_id in seen:
                    continue
                packet = UnifiedDataPacket.from_dict(json.loads(canonical(raw)))
                author_pem = str((packet.metadata or {}).get("author_public_key_pem") or "").encode("utf-8")
                if not verify_overlay_packet(packet, author_pem):
                    raise EmailSocialRelayError(f"mail {packet_id} failed signature verification")
                seen.add(packet_id)
                content = packet.content if isinstance(packet.content, dict) else {}
                sealed = content.get("sealed")
                if not isinstance(sealed, dict):
                    raise EmailSocialCryptoError(f"mail {packet_id} missing sealed envelope")
                try:
                    plaintext = self.identity.open_sealed(sealed)
                    inner = json.loads(plaintext.decode("utf-8"))
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise EmailSocialCryptoError(f"mail {packet_id} could not be opened") from exc
                if not isinstance(inner, dict):
                    raise EmailSocialCryptoError(f"mail {packet_id} plaintext is not a mapping")
                opened.append(
                    OpenedMail(
                        packet_id=packet_id,
                        sender_hash=str(inner.get("from") or raw.get("author_identity_hash") or ""),
                        subject=str(inner.get("subject") or ""),
                        body=str(inner.get("body") or ""),
                        timestamp=str(raw.get("timestamp") or ""),
                    )
                )
        return opened

    def fetch_social(self, *, feed: str | None = None) -> list[dict[str, object]]:
        """
        Pull public social events. Filtering is client-side only.

        Args:
            feed: Optional feed label to keep.

        Returns:
            Stored packet mappings, de-duplicated by packet_id.
        """
        seen: set[str] = set()
        posts: list[dict[str, object]] = []
        for relay in self.relays():
            for raw in relay.query(kind=SOCIAL_KIND):
                packet_id = str(raw.get("packet_id") or "")
                if not packet_id or packet_id in seen:
                    continue
                content = raw.get("content") if isinstance(raw.get("content"), dict) else {}
                if feed is not None and str(content.get("feed") or "") != feed:
                    continue
                seen.add(packet_id)
                posts.append(dict(raw))
        return posts

    def fetch_knocks(self) -> list[dict[str, object]]:
        """
        Pull live knocks addressed to this identity.

        Args:
            None

        Returns:
            Knock packet mappings that have not yet expired.
        """
        seen: set[str] = set()
        knocks: list[dict[str, object]] = []
        for relay in self.relays():
            for raw in relay.query(recipient_hash=self.identity.identity_hash, kind=KNOCK_KIND):
                packet_id = str(raw.get("packet_id") or "")
                if packet_id and packet_id not in seen:
                    seen.add(packet_id)
                    knocks.append(dict(raw))
        return knocks

    def _package_and_publish(self, kind: str, content: dict[str, object]) -> UnifiedDataPacket:
        """Inspect, sign, inspect again, then push to every relay."""
        reject_legacy_routing(content)
        pre = self.firewall.inspect_content(
            content,
            lane=InspectionLane.PAN_MESH,
            author_identity_hash=self.identity.identity_hash,
        )
        if pre.action is InspectionAction.BLOCK:
            raise EmailSocialBlocked(f"firewall blocked content: {pre.reason}")
        packaged = dict(pre.sanitized_content) if pre.modified and pre.sanitized_content else dict(content)
        metadata: dict[str, object] = {
            "author_public_key_pem": self.identity.get_public_key_pem().decode("utf-8"),
            "mesh_address": self.identity.mesh_address,
        }
        reject_legacy_routing(metadata)
        packet = self.communicator.create_packet(kind, packaged, metadata=metadata)
        post = self.firewall.inspect_packet(packet, lane=InspectionLane.PAN_MESH)
        if post.blocked:
            raise EmailSocialBlocked(f"firewall blocked packet: {post.reason}")
        author_pem = self.identity.get_public_key_pem()
        accepted = 0
        for relay in self.relays():
            result = relay.accept(packet, author_public_key_pem=author_pem, firewall=self.firewall)
            if result.ok:
                accepted += 1
        if accepted < 1:
            raise EmailSocialRelayError("no relay accepted the packet")
        return packet


def _bootstrap_path() -> None:
    """Ensure repo root is importable when this file is executed directly."""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


if __name__ == "__main__":
    _bootstrap_path()
    raise SystemExit("EmailSocialNode is a library; run test/email_social/test_email_social.py")
