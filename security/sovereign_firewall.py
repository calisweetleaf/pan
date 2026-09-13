"""
Sovereign Firewall — fail-closed anti-surveillance border for UnifiedDataPackets.

Source: PAN whitepaper Table 2 (ingress sanitization, telemetry regex,
    sensitive-payload compression, identity blocklist, SQLite ledger)
Integrated: 2026-09-11

Modified: 2026-09-12
Modified by: daeron
Justification: I added LegacyInternetEgressError as the shared fail-loud
    type for SMTP/HTTP/socket lineage and mapped HIGHWAY_* packet kinds onto
    PAN_MESH so AI itinerary hops use the civic lane. Wrapping a second
    firewall would have split the border. Unknown kinds stay EGRESS_LEGACY.
Provenance: snapshots/v0.13/manifest.json -> domains.highway.edits[0]
Files: security/sovereign_firewall.py
"""

from __future__ import annotations

import base64
import json
import logging
import re
import sqlite3
import sys
import threading
import zlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterator, Mapping

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PAN_SDK.PAN_SDK import UnifiedDataPacket, sha256_hex, utc_now_iso

LOGGER = logging.getLogger("SovereignFirewall")

TELEMETRY_DICTIONARY = frozenset(
    {
        "google-analytics",
        "google analytics",
        "doubleclick",
        "palantir",
        "hotjar",
        "fullstory",
        "mixpanel",
        "segment.io",
        "amplitude",
        "sentry.io",
        "telemetry-export",
        "metrics-endpoint",
        "api.cloud",
        "facebook.com/tr",
        "nist-telemetry",
    }
)

LEGACY_TELEMETRY_PATTERN = re.compile(
    r"(?i)(?<![\w])(google[-\s]?analytics|palantir|doubleclick|hotjar|"
    r"telemetry[-_]?export|metrics[-_]?endpoint|api\.cloud|"
    r"facebook\.com/tr|sentry\.io|mixpanel|fullstory)(?![\w])"
)

SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(-----begin (?:rsa |ec |openssh )?private key-----|"
    r"\bpassword\b|\bsecret_token\b|\bapi_key\b|\bbearer\s+[a-z0-9._\-]{12,})"
)

ROUTING_KEYS = frozenset(
    {
        "next_hop",
        "isp_route",
        "default_gateway",
        "carrier_msisdn",
        "imsi",
        "iccid",
        "legacy_ip_route",
    }
)

SECRET_FIELD_KEYS = frozenset(
    {
        "password",
        "private_key",
        "secret",
        "secret_token",
        "api_key",
        "bearer_token",
    }
)

IPV4_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

LACKA_ENVELOPE_KEY = "lacka_envelope"
LACKA_ALGORITHM = "deflate-v1"
THREAT_BULLETIN_KIND = "THREAT_MEMORY_BULLETIN"


class FirewallError(Exception):
    """Domain error for sovereign border inspection."""


class FirewallInspectionError(FirewallError):
    """Packet or content failed structural inspection."""


class FirewallLedgerError(FirewallError):
    """SQLite ledger could not record a border decision."""


class LegacyInternetEgressError(FirewallError):
    """Raised when a security owner attempts legacy internet egress."""


class InspectionLane(str, Enum):
    """Where a packet is headed."""

    EGRESS_LEGACY = "egress_legacy"
    INGRESS = "ingress"
    PAN_MESH = "pan_mesh"


class InspectionAction(str, Enum):
    """Terminal inspection action."""

    ALLOW = "allow"
    BLOCK = "block"
    COMPRESS = "compress"


@dataclass
class InspectionVerdict:
    """Structured, ledgered inspection result."""

    action: InspectionAction
    reason: str
    lane: InspectionLane
    packet_id: str
    content_hash: str
    matched_rules: list[str] = field(default_factory=list)
    sanitized_content: dict[str, object] | None = None
    author_identity_hash: str = ""
    timestamp: str = field(default_factory=utc_now_iso)

    @property
    def blocked(self) -> bool:
        """Return True when the packet must not leave or enter."""
        return self.action is InspectionAction.BLOCK

    @property
    def allowed(self) -> bool:
        """Return True when the packet may continue."""
        return self.action is not InspectionAction.BLOCK

    @property
    def modified(self) -> bool:
        """Return True when inspect_content produced a compression envelope."""
        return self.action is InspectionAction.COMPRESS

    def __getitem__(self, key: str) -> object:
        """Expose the historical inspect_content mapping used by NetworkThreatMonitor."""
        mapping: dict[str, object] = {
            "blocked": self.blocked,
            "reason": self.reason,
            "sanitized_content": self.sanitized_content,
            "modified": self.modified,
            "action": self.action.value,
            "lane": self.lane.value,
            "matched_rules": list(self.matched_rules),
        }
        if key not in mapping:
            raise KeyError(key)
        return mapping[key]


class SovereignFirewall:
    """Deterministic packet border: dictionary, regex, identity, SQLite ledger."""

    def __init__(self, ledger_path: str | Path) -> None:
        """
        Open the offline firewall ledger.

        Args:
            ledger_path: SQLite file that records every allow, compress, and drop.

        Returns:
            None
        """
        if not ledger_path:
            raise FirewallLedgerError("SovereignFirewall requires a SQLite ledger path")
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.ledger_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.blocked_count = 0
        self.allowed_count = 0
        self.compressed_count = 0
        self._init_schema()
        LOGGER.info("SovereignFirewall ledger opened at %s", self.ledger_path)

    def close(self) -> None:
        """Close the ledger connection."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def inspect_content(
        self,
        content: Mapping[str, object],
        *,
        lane: InspectionLane = InspectionLane.EGRESS_LEGACY,
        author_identity_hash: str = "",
    ) -> InspectionVerdict:
        """
        Inspect raw content before cryptographic packaging.

        Args:
            content: Candidate packet payload.
            lane: Inspection lane. EGRESS_LEGACY is ruthless toward trackers.
            author_identity_hash: Optional author hash for blocklist checks.

        Returns:
            InspectionVerdict. COMPRESS supplies sanitized_content for signing.
        """
        if not isinstance(content, Mapping):
            raise FirewallInspectionError("inspect_content requires a mapping payload")
        payload = dict(content)
        verdict = self._evaluate_mapping(
            payload,
            lane=lane,
            packet_id="pre-packet",
            author_identity_hash=author_identity_hash,
            allow_compress=True,
        )
        self._persist_verdict(verdict)
        self._count(verdict)
        return verdict

    def inspect_packet(
        self,
        packet: UnifiedDataPacket,
        custom_rule: Callable[[UnifiedDataPacket], bool] | None = None,
        *,
        lane: InspectionLane | None = None,
    ) -> InspectionVerdict:
        """
        Inspect a signed packet without mutating it.

        Args:
            packet: UnifiedDataPacket already packaged by a communicator.
            custom_rule: Optional extra predicate; False blocks the packet.
            lane: Override lane. Threat bulletins default to PAN_MESH.

        Returns:
            InspectionVerdict. Sensitive plaintext is blocked, never rewritten.
        """
        if packet is None:
            raise FirewallInspectionError("inspect_packet requires a UnifiedDataPacket")
        resolved_lane = lane or self._lane_for_packet(packet)
        if self.is_identity_blocked(packet.author_identity_hash):
            verdict = InspectionVerdict(
                action=InspectionAction.BLOCK,
                reason="identity_blocklist",
                lane=resolved_lane,
                packet_id=packet.packet_id,
                content_hash=packet.content_hash or "",
                matched_rules=["identity_blocklist"],
                sanitized_content=None,
                author_identity_hash=packet.author_identity_hash,
            )
            self._persist_verdict(verdict)
            self._count(verdict)
            return verdict
        if not packet.verify_integrity():
            verdict = InspectionVerdict(
                action=InspectionAction.BLOCK,
                reason="content_hash_mismatch",
                lane=resolved_lane,
                packet_id=packet.packet_id,
                content_hash=packet.content_hash or "",
                matched_rules=["integrity"],
                author_identity_hash=packet.author_identity_hash,
            )
            self._persist_verdict(verdict)
            self._count(verdict)
            return verdict
        if not isinstance(packet.content, dict):
            raise FirewallInspectionError("packet.content must be a dict")
        verdict = self._evaluate_mapping(
            packet.content,
            lane=resolved_lane,
            packet_id=packet.packet_id,
            author_identity_hash=packet.author_identity_hash,
            allow_compress=False,
        )
        if custom_rule is not None:
            try:
                custom_allowed = bool(custom_rule(packet))
            except (TypeError, ValueError) as exc:
                raise FirewallInspectionError(
                    f"custom_rule failed closed: {exc}"
                ) from exc
            if not custom_allowed:
                verdict = InspectionVerdict(
                    action=InspectionAction.BLOCK,
                    reason="custom_rule_violation",
                    lane=resolved_lane,
                    packet_id=packet.packet_id,
                    content_hash=packet.content_hash or "",
                    matched_rules=verdict.matched_rules + ["custom_rule"],
                    author_identity_hash=packet.author_identity_hash,
                )
        verdict.packet_id = packet.packet_id
        verdict.content_hash = packet.content_hash or verdict.content_hash
        self._persist_verdict(verdict)
        self._count(verdict)
        return verdict

    def block_identity(self, identity_hash: str, reason: str = "operator_block") -> None:
        """
        Permanently block a PAN identity hash.

        Args:
            identity_hash: SovereignIdentity.identity_hash to isolate.
            reason: Operator-supplied block reason.

        Returns:
            None
        """
        if not identity_hash or not isinstance(identity_hash, str):
            raise FirewallInspectionError("identity_hash must be a non-empty string")
        with self._lock:
            try:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO identity_blocklist
                    (identity_hash, blocked_at, reason)
                    VALUES (?, ?, ?)
                    """,
                    (identity_hash, utc_now_iso(), reason),
                )
                self._conn.commit()
            except sqlite3.Error as exc:
                raise FirewallLedgerError(f"failed to persist identity block: {exc}") from exc
        LOGGER.warning("Blocked identity %s (%s)", identity_hash[:12], reason)

    def is_identity_blocked(self, identity_hash: str) -> bool:
        """
        Return True when the identity is on the blocklist.

        Args:
            identity_hash: PAN identity hash.

        Returns:
            True when blocked.
        """
        if not identity_hash:
            return False
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM identity_blocklist WHERE identity_hash = ?",
                (identity_hash,),
            ).fetchone()
        return row is not None

    def get_status(self) -> dict[str, int | str]:
        """
        Return live counters for the current process.

        Args:
            None

        Returns:
            Counts plus ledger path.
        """
        return {
            "blocks": self.blocked_count,
            "allowed": self.allowed_count,
            "compressed": self.compressed_count,
            "total_processed": self.blocked_count + self.allowed_count + self.compressed_count,
            "ledger_path": str(self.ledger_path),
        }

    def ledger_events(self, limit: int = 50) -> list[dict[str, object]]:
        """
        Read recent ledger rows from SQLite.

        Args:
            limit: Maximum rows, newest first.

        Returns:
            Ledger dictionaries.
        """
        if limit < 1:
            raise FirewallLedgerError("limit must be >= 1")
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT event_id, timestamp, packet_id, action, reason, lane,
                       author_identity_hash, content_hash, matched_rules_json
                FROM firewall_events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        events: list[dict[str, object]] = []
        for row in rows:
            events.append(
                {
                    "event_id": row["event_id"],
                    "timestamp": row["timestamp"],
                    "packet_id": row["packet_id"],
                    "action": row["action"],
                    "reason": row["reason"],
                    "lane": row["lane"],
                    "author_identity_hash": row["author_identity_hash"],
                    "content_hash": row["content_hash"],
                    "matched_rules": json.loads(row["matched_rules_json"]),
                }
            )
        return events

    def _init_schema(self) -> None:
        """Create ledger tables if they do not exist."""
        with self._lock:
            try:
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=FULL")
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS firewall_events (
                        event_id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        packet_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        lane TEXT NOT NULL,
                        author_identity_hash TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        matched_rules_json TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS identity_blocklist (
                        identity_hash TEXT PRIMARY KEY,
                        blocked_at TEXT NOT NULL,
                        reason TEXT NOT NULL
                    );
                    """
                )
                self._conn.commit()
            except sqlite3.Error as exc:
                raise FirewallLedgerError(f"failed to initialize firewall ledger: {exc}") from exc

    def _lane_for_packet(self, packet: UnifiedDataPacket) -> InspectionLane:
        """Choose PAN_MESH for immune bulletins and highway hops."""
        kind = str(packet.kind or "")
        if kind == THREAT_BULLETIN_KIND or kind.startswith("HIGHWAY_"):
            return InspectionLane.PAN_MESH
        return InspectionLane.EGRESS_LEGACY

    def _evaluate_mapping(
        self,
        payload: dict[str, object],
        *,
        lane: InspectionLane,
        packet_id: str,
        author_identity_hash: str,
        allow_compress: bool,
    ) -> InspectionVerdict:
        """Run the deterministic inspection pipeline against one mapping."""
        matched: list[str] = []
        if payload.get(LACKA_ENVELOPE_KEY) is True:
            if not self._valid_envelope(payload):
                return InspectionVerdict(
                    action=InspectionAction.BLOCK,
                    reason="malformed_lacka_envelope",
                    lane=lane,
                    packet_id=packet_id,
                    content_hash=sha256_hex(_canonical(payload)),
                    matched_rules=["lacka_envelope"],
                    author_identity_hash=author_identity_hash,
                )
            return InspectionVerdict(
                action=InspectionAction.ALLOW,
                reason="lacka_envelope_accepted",
                lane=lane,
                packet_id=packet_id,
                content_hash=sha256_hex(_canonical(payload)),
                matched_rules=["lacka_envelope"],
                sanitized_content=payload,
                author_identity_hash=author_identity_hash,
            )

        for key, value in _walk_items(payload):
            key_l = key.rsplit(".", 1)[-1].lower()
            if key_l in ROUTING_KEYS:
                matched.append(f"routing:{key_l}")
                return InspectionVerdict(
                    action=InspectionAction.BLOCK,
                    reason="legacy_routing_artifact",
                    lane=lane,
                    packet_id=packet_id,
                    content_hash=sha256_hex(_canonical(payload)),
                    matched_rules=matched,
                    author_identity_hash=author_identity_hash,
                )
            if key_l in SECRET_FIELD_KEYS:
                if allow_compress:
                    enveloped = _lacka_compress(payload)
                    matched.append(f"secret_field:{key_l}")
                    return InspectionVerdict(
                        action=InspectionAction.COMPRESS,
                        reason="sensitive_content_compressed",
                        lane=lane,
                        packet_id=packet_id,
                        content_hash=sha256_hex(_canonical(enveloped)),
                        matched_rules=matched,
                        sanitized_content=enveloped,
                        author_identity_hash=author_identity_hash,
                    )
                matched.append(f"secret_field:{key_l}")
                return InspectionVerdict(
                    action=InspectionAction.BLOCK,
                    reason="sensitive_plaintext_on_signed_packet",
                    lane=lane,
                    packet_id=packet_id,
                    content_hash=sha256_hex(_canonical(payload)),
                    matched_rules=matched,
                    author_identity_hash=author_identity_hash,
                )
            if isinstance(value, str) and SENSITIVE_VALUE_PATTERN.search(value):
                if allow_compress:
                    enveloped = _lacka_compress(payload)
                    matched.append("sensitive_value_pattern")
                    return InspectionVerdict(
                        action=InspectionAction.COMPRESS,
                        reason="sensitive_content_compressed",
                        lane=lane,
                        packet_id=packet_id,
                        content_hash=sha256_hex(_canonical(enveloped)),
                        matched_rules=matched,
                        sanitized_content=enveloped,
                        author_identity_hash=author_identity_hash,
                    )
                matched.append("sensitive_value_pattern")
                return InspectionVerdict(
                    action=InspectionAction.BLOCK,
                    reason="sensitive_plaintext_on_signed_packet",
                    lane=lane,
                    packet_id=packet_id,
                    content_hash=sha256_hex(_canonical(payload)),
                    matched_rules=matched,
                    author_identity_hash=author_identity_hash,
                )
            if (
                lane is not InspectionLane.PAN_MESH
                and key_l in {"dest_ip", "destination_ip", "next_hop_ip"}
                and isinstance(value, str)
                and IPV4_PATTERN.search(value)
            ):
                matched.append(f"legacy_ip:{key_l}")
                return InspectionVerdict(
                    action=InspectionAction.BLOCK,
                    reason="legacy_ip_routing",
                    lane=lane,
                    packet_id=packet_id,
                    content_hash=sha256_hex(_canonical(payload)),
                    matched_rules=matched,
                    author_identity_hash=author_identity_hash,
                )

        if lane is not InspectionLane.PAN_MESH:
            haystack = _flatten_text(payload).lower()
            for token in TELEMETRY_DICTIONARY:
                if token in haystack:
                    matched.append(f"dictionary:{token}")
                    return InspectionVerdict(
                        action=InspectionAction.BLOCK,
                        reason="telemetry_dictionary",
                        lane=lane,
                        packet_id=packet_id,
                        content_hash=sha256_hex(_canonical(payload)),
                        matched_rules=matched,
                        author_identity_hash=author_identity_hash,
                    )
            regex_hit = LEGACY_TELEMETRY_PATTERN.search(haystack)
            if regex_hit:
                matched.append(f"regex:{regex_hit.group(0)}")
                return InspectionVerdict(
                    action=InspectionAction.BLOCK,
                    reason="telemetry_regex",
                    lane=lane,
                    packet_id=packet_id,
                    content_hash=sha256_hex(_canonical(payload)),
                    matched_rules=matched,
                    author_identity_hash=author_identity_hash,
                )

        return InspectionVerdict(
            action=InspectionAction.ALLOW,
            reason="allowed",
            lane=lane,
            packet_id=packet_id,
            content_hash=sha256_hex(_canonical(payload)),
            matched_rules=matched,
            sanitized_content=payload,
            author_identity_hash=author_identity_hash,
        )

    def _valid_envelope(self, payload: Mapping[str, object]) -> bool:
        """Return True when a lacka envelope has the required fields."""
        algorithm = payload.get("algorithm")
        digest = payload.get("original_sha256")
        blob = payload.get("payload_b64")
        return (
            algorithm == LACKA_ALGORITHM
            and isinstance(digest, str)
            and len(digest) == 64
            and isinstance(blob, str)
            and len(blob) > 0
        )

    def _persist_verdict(self, verdict: InspectionVerdict) -> None:
        """Write the verdict to SQLite or fail closed."""
        event_id = sha256_hex(
            f"{verdict.timestamp}:{verdict.packet_id}:{verdict.action.value}:{verdict.content_hash}"
        )
        with self._lock:
            if self._conn is None:
                raise FirewallLedgerError("firewall ledger is closed")
            try:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO firewall_events
                    (event_id, timestamp, packet_id, action, reason, lane,
                     author_identity_hash, content_hash, matched_rules_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        verdict.timestamp,
                        verdict.packet_id,
                        verdict.action.value,
                        verdict.reason,
                        verdict.lane.value,
                        verdict.author_identity_hash,
                        verdict.content_hash,
                        json.dumps(verdict.matched_rules),
                    ),
                )
                self._conn.commit()
            except sqlite3.Error as exc:
                raise FirewallLedgerError(f"failed to ledger firewall verdict: {exc}") from exc

    def _count(self, verdict: InspectionVerdict) -> None:
        """Update in-process counters."""
        if verdict.action is InspectionAction.BLOCK:
            self.blocked_count += 1
        elif verdict.action is InspectionAction.COMPRESS:
            self.compressed_count += 1
        else:
            self.allowed_count += 1


def _canonical(value: object) -> str:
    """Deterministic JSON for hashing."""
    return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=False, default=str)


def _lacka_compress(payload: Mapping[str, object]) -> dict[str, object]:
    """Wrap plaintext in a real deflate envelope and stamp the original digest."""
    canonical = _canonical(dict(payload))
    original_digest = sha256_hex(canonical)
    compressed = zlib.compress(canonical.encode("utf-8"), level=9)
    return {
        LACKA_ENVELOPE_KEY: True,
        "algorithm": LACKA_ALGORITHM,
        "original_sha256": original_digest,
        "payload_b64": base64.b64encode(compressed).decode("ascii"),
        "original_bytes": len(canonical.encode("utf-8")),
        "compressed_bytes": len(compressed),
    }


def _walk_items(value: object, prefix: str = "") -> Iterator[tuple[str, object]]:
    """Yield dotted paths and leaf values."""
    if isinstance(value, Mapping):
        for key, inner in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, inner
            yield from _walk_items(inner, path)
        return
    if isinstance(value, list):
        for index, inner in enumerate(value):
            path = f"{prefix}[{index}]"
            yield path, inner
            yield from _walk_items(inner, path)


def _flatten_text(value: object) -> str:
    """Concatenate string leaves for dictionary/regex matching."""
    chunks: list[str] = []
    for path, leaf in _walk_items(value):
        chunks.append(path)
        if isinstance(leaf, str):
            chunks.append(leaf)
        elif isinstance(leaf, (int, float, bool)):
            chunks.append(str(leaf))
    return " ".join(chunks)


def _bootstrap_path() -> None:
    """Ensure repo root is importable when this file is executed directly."""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


if __name__ == "__main__":
    _bootstrap_path()
    raise SystemExit("SovereignFirewall is a library; run test/immune/test_planetary_immune_system.py")
