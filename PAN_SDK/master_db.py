"""
Sovereign master database — CRDT join over local SQLite.

Source: docs/research/Building a Sovereign Digital Nation.md section 6
Integrated: 2026-09-10
Purpose: Offline-first document, counter, and set state with a join that is
    commutative, associative, and idempotent. Page hashes skip identical
    replicas the way sqlite3_rsync skips matching pages.
"""

from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PAN_SDK.PAN_SDK import PANPersistenceStore, canonical, sha256_hex, utc_now_iso

LOGGER = logging.getLogger("MasterDatabase")

DOC_COMPONENT = "master_db_docs"
COUNTER_COMPONENT = "master_db_counters"
SET_COMPONENT = "master_db_sets"
META_COMPONENT = "master_db_meta"


class MasterDatabaseError(Exception):
    """Domain error for the CRDT master database."""


@dataclass
class LWWRecord:
    """Last-writer-wins register with a deterministic tie-break."""

    value: object
    timestamp: str
    writer: str
    sequence: int
    tombstone: bool = False

    def to_mapping(self) -> dict[str, object]:
        """Serialize the register."""
        return {
            "value": self.value,
            "timestamp": self.timestamp,
            "writer": self.writer,
            "sequence": self.sequence,
            "tombstone": self.tombstone,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> LWWRecord:
        """Rebuild a register from sqlite."""
        return cls(
            value=payload.get("value"),
            timestamp=str(payload.get("timestamp") or ""),
            writer=str(payload.get("writer") or ""),
            sequence=int(payload.get("sequence") or 0),
            tombstone=bool(payload.get("tombstone")),
        )

    def rank(self) -> tuple[str, str, int]:
        """Return the total order used by the join."""
        return (self.timestamp, self.writer, self.sequence)


@dataclass
class GCounter:
    """Grow-only counter. Merge takes the per-replica maximum."""

    counts: dict[str, int] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, object]:
        """Serialize counts."""
        return {"counts": dict(self.counts)}

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> GCounter:
        """Rebuild a counter."""
        raw = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
        counts = {str(key): int(value) for key, value in raw.items()}
        return cls(counts=counts)

    def value(self) -> int:
        """Return the summed replica counts."""
        return sum(self.counts.values())

    def merge(self, other: GCounter) -> GCounter:
        """Return the lattice join of two counters."""
        keys = set(self.counts) | set(other.counts)
        merged = {key: max(self.counts.get(key, 0), other.counts.get(key, 0)) for key in keys}
        return GCounter(counts=merged)


@dataclass
class ORSet:
    """Observed-remove set using unique add tags."""

    added: dict[str, list[str]] = field(default_factory=dict)
    removed: dict[str, list[str]] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, object]:
        """Serialize tag maps."""
        return {
            "added": {key: list(tags) for key, tags in self.added.items()},
            "removed": {key: list(tags) for key, tags in self.removed.items()},
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ORSet:
        """Rebuild an OR-set."""
        added_raw = payload.get("added") if isinstance(payload.get("added"), dict) else {}
        removed_raw = payload.get("removed") if isinstance(payload.get("removed"), dict) else {}
        added = {str(key): [str(tag) for tag in tags] for key, tags in added_raw.items() if isinstance(tags, list)}
        removed = {
            str(key): [str(tag) for tag in tags] for key, tags in removed_raw.items() if isinstance(tags, list)
        }
        return cls(added=added, removed=removed)

    def elements(self) -> set[str]:
        """Return live members (added tags not fully removed)."""
        live: set[str] = set()
        for member, tags in self.added.items():
            remaining = set(tags) - set(self.removed.get(member, []))
            if remaining:
                live.add(member)
        return live

    def merge(self, other: ORSet) -> ORSet:
        """Return the lattice join of two OR-sets."""
        members = set(self.added) | set(other.added) | set(self.removed) | set(other.removed)
        added: dict[str, list[str]] = {}
        removed: dict[str, list[str]] = {}
        for member in members:
            add_tags = set(self.added.get(member, [])) | set(other.added.get(member, []))
            rem_tags = set(self.removed.get(member, [])) | set(other.removed.get(member, []))
            if add_tags:
                added[member] = sorted(add_tags)
            if rem_tags:
                removed[member] = sorted(rem_tags)
        return ORSet(added=added, removed=removed)


def merge_lww(left: LWWRecord, right: LWWRecord) -> LWWRecord:
    """
    Join two LWW registers. Equal ranks keep left (idempotent).

    Args:
        left: First register.
        right: Second register.

    Returns:
        The dominating register.
    """
    if right.rank() > left.rank():
        return right
    return left


class MasterDatabase:
    """Local CRDT replica persisted through PANPersistenceStore."""

    def __init__(self, replica_id: str, persistence: PANPersistenceStore) -> None:
        """
        Open a replica on an existing sqlite store.

        Args:
            replica_id: Stable replica identity hash.
            persistence: PAN sqlite store. This class does not open a second engine.

        Returns:
            None
        """
        if not replica_id:
            raise MasterDatabaseError("replica_id is required")
        if persistence is None:
            raise MasterDatabaseError("MasterDatabase requires PANPersistenceStore")
        self.replica_id = replica_id
        self.persistence = persistence
        self._lock = threading.RLock()
        self.documents: dict[str, LWWRecord] = {}
        self.counters: dict[str, GCounter] = {}
        self.sets: dict[str, ORSet] = {}
        self._sequence = 0
        self.hydrate_from_persistence()
        LOGGER.info(
            "MasterDatabase online replica=%s docs=%s counters=%s sets=%s",
            replica_id[:12],
            len(self.documents),
            len(self.counters),
            len(self.sets),
        )

    def hydrate_from_persistence(self) -> None:
        """
        Reload documents, counters, sets, and the local sequence from sqlite.

        Args:
            None

        Returns:
            None
        """
        docs = self.persistence.load_component(DOC_COMPONENT)
        self.documents = {}
        for key, raw in (docs or {}).items():
            if isinstance(raw, dict):
                self.documents[str(key)] = LWWRecord.from_mapping(raw)
        counters = self.persistence.load_component(COUNTER_COMPONENT)
        self.counters = {}
        for key, raw in (counters or {}).items():
            if isinstance(raw, dict):
                self.counters[str(key)] = GCounter.from_mapping(raw)
        sets = self.persistence.load_component(SET_COMPONENT)
        self.sets = {}
        for key, raw in (sets or {}).items():
            if isinstance(raw, dict):
                self.sets[str(key)] = ORSet.from_mapping(raw)
        meta = self.persistence.read_state(META_COMPONENT, self.replica_id)
        if isinstance(meta, dict):
            self._sequence = int(meta.get("sequence") or 0)

    def put(self, key: str, value: object) -> LWWRecord:
        """
        Write a document locally. Visible immediately, even while partitioned.

        Args:
            key: Document id.
            value: JSON-stable payload.

        Returns:
            The new LWW record.
        """
        return self._write_doc(key, value, tombstone=False)

    def delete(self, key: str) -> LWWRecord:
        """
        Tombstone a document. The tombstone still joins with peers.

        Args:
            key: Document id.

        Returns:
            The tombstone record.
        """
        return self._write_doc(key, None, tombstone=True)

    def get(self, key: str) -> object | None:
        """
        Return a live document value, or None if missing or tombstoned.

        Args:
            key: Document id.

        Returns:
            Stored value or None.
        """
        record = self.documents.get(key)
        if record is None or record.tombstone:
            return None
        return record.value

    def increment(self, name: str, amount: int = 1) -> int:
        """
        Increment this replica's G-counter shard.

        Args:
            name: Counter id.
            amount: Positive increment.

        Returns:
            The merged counter value after the increment.
        """
        if amount < 1:
            raise MasterDatabaseError("increment amount must be >= 1")
        with self._lock:
            counter = self.counters.get(name) or GCounter()
            current = counter.counts.get(self.replica_id, 0)
            counter.counts[self.replica_id] = current + amount
            self.counters[name] = counter
            self.persistence.write_state(COUNTER_COMPONENT, name, counter.to_mapping())
            return counter.value()

    def counter_value(self, name: str) -> int:
        """
        Return a G-counter's joined value.

        Args:
            name: Counter id.

        Returns:
            Integer sum of replica shards.
        """
        counter = self.counters.get(name)
        return counter.value() if counter else 0

    def add(self, name: str, member: str) -> None:
        """
        Observe-add a set member with a unique tag.

        Args:
            name: Set id.
            member: Member string.

        Returns:
            None
        """
        if not member:
            raise MasterDatabaseError("set member must be non-empty")
        with self._lock:
            orset = self.sets.get(name) or ORSet()
            seq = self._next_sequence()
            tag = f"{self.replica_id}:{seq}"
            tags = set(orset.added.get(member, []))
            tags.add(tag)
            orset.added[member] = sorted(tags)
            self.sets[name] = orset
            self.persistence.write_state(SET_COMPONENT, name, orset.to_mapping())

    def remove(self, name: str, member: str) -> None:
        """
        Observe-remove a set member by collecting currently known add tags.

        Args:
            name: Set id.
            member: Member string.

        Returns:
            None
        """
        with self._lock:
            orset = self.sets.get(name) or ORSet()
            known = set(orset.added.get(member, []))
            if not known:
                return
            removed = set(orset.removed.get(member, [])) | known
            orset.removed[member] = sorted(removed)
            self.sets[name] = orset
            self.persistence.write_state(SET_COMPONENT, name, orset.to_mapping())

    def members(self, name: str) -> set[str]:
        """
        Return live OR-set members.

        Args:
            name: Set id.

        Returns:
            Set of live member strings.
        """
        orset = self.sets.get(name)
        return orset.elements() if orset else set()

    def page_hashes(self) -> dict[str, str]:
        """
        Hash every stored page so peers can skip identical state.

        Args:
            None

        Returns:
            Mapping of page id to SHA-256 hex.
        """
        pages: dict[str, str] = {}
        with self._lock:
            for key, record in self.documents.items():
                pages[f"doc:{key}"] = sha256_hex(canonical(record.to_mapping()))
            for key, counter in self.counters.items():
                pages[f"ctr:{key}"] = sha256_hex(canonical(counter.to_mapping()))
            for key, orset in self.sets.items():
                pages[f"set:{key}"] = sha256_hex(canonical(orset.to_mapping()))
        return pages

    def pages_needed(self, peer_hashes: Mapping[str, str]) -> list[str]:
        """
        Return page ids this replica should fetch from the peer.

        Args:
            peer_hashes: Digest advertised by a peer.

        Returns:
            Page ids whose peer payload differs from local state.
        """
        local = self.page_hashes()
        needed: list[str] = []
        for page_id, digest in peer_hashes.items():
            if local.get(page_id) != digest:
                needed.append(page_id)
        return sorted(set(needed))

    def export_pages(self, page_ids: Sequence[str]) -> dict[str, dict[str, object]]:
        """
        Export the named pages for transmission.

        Args:
            page_ids: Page ids from pages_needed.

        Returns:
            Mapping of page id to typed payload.
        """
        exported: dict[str, dict[str, object]] = {}
        with self._lock:
            for page_id in page_ids:
                kind, _, key = page_id.partition(":")
                if kind == "doc" and key in self.documents:
                    exported[page_id] = {"kind": "doc", "key": key, "record": self.documents[key].to_mapping()}
                elif kind == "ctr" and key in self.counters:
                    exported[page_id] = {"kind": "ctr", "key": key, "record": self.counters[key].to_mapping()}
                elif kind == "set" and key in self.sets:
                    exported[page_id] = {"kind": "set", "key": key, "record": self.sets[key].to_mapping()}
        return exported

    def merge_pages(self, pages: Mapping[str, Mapping[str, object]]) -> None:
        """
        Join remote pages into this replica.

        Args:
            pages: Typed payloads from export_pages.

        Returns:
            None
        """
        with self._lock:
            for page_id, payload in pages.items():
                kind = str(payload.get("kind") or page_id.split(":", 1)[0])
                key = str(payload.get("key") or "")
                record = payload.get("record")
                if not key or not isinstance(record, dict):
                    raise MasterDatabaseError(f"malformed page {page_id}")
                if kind == "doc":
                    incoming = LWWRecord.from_mapping(record)
                    current = self.documents.get(key)
                    winner = incoming if current is None else merge_lww(current, incoming)
                    self.documents[key] = winner
                    self.persistence.write_state(DOC_COMPONENT, key, winner.to_mapping())
                elif kind == "ctr":
                    incoming = GCounter.from_mapping(record)
                    current = self.counters.get(key) or GCounter()
                    winner = current.merge(incoming)
                    self.counters[key] = winner
                    self.persistence.write_state(COUNTER_COMPONENT, key, winner.to_mapping())
                elif kind == "set":
                    incoming = ORSet.from_mapping(record)
                    current = self.sets.get(key) or ORSet()
                    winner = current.merge(incoming)
                    self.sets[key] = winner
                    self.persistence.write_state(SET_COMPONENT, key, winner.to_mapping())
                else:
                    raise MasterDatabaseError(f"unknown page kind {kind}")

    def export_bundle(self) -> dict[str, dict[str, object]]:
        """
        Export the full replica state for a complete join.

        Args:
            None

        Returns:
            Bundle of all pages.
        """
        return self.export_pages(list(self.page_hashes().keys()))

    def merge_bundle(self, bundle: Mapping[str, Mapping[str, object]]) -> None:
        """
        Join a full replica bundle.

        Args:
            bundle: Output of export_bundle.

        Returns:
            None
        """
        self.merge_pages(bundle)

    def snapshot(self) -> dict[str, object]:
        """
        Return a comparable view of live state for convergence tests.

        Args:
            None

        Returns:
            Canonical live documents, counters, and sets.
        """
        docs = {
            key: record.value
            for key, record in sorted(self.documents.items())
            if not record.tombstone
        }
        counters = {key: counter.value() for key, counter in sorted(self.counters.items())}
        sets = {key: sorted(orset.elements()) for key, orset in sorted(self.sets.items())}
        return {"documents": docs, "counters": counters, "sets": sets}

    def _write_doc(self, key: str, value: object, *, tombstone: bool) -> LWWRecord:
        """Persist one LWW write under the replica lock."""
        if not key:
            raise MasterDatabaseError("document key must be non-empty")
        payload = None if tombstone else _jsonable(value)
        with self._lock:
            record = LWWRecord(
                value=payload,
                timestamp=utc_now_iso(),
                writer=self.replica_id,
                sequence=self._next_sequence(),
                tombstone=tombstone,
            )
            current = self.documents.get(key)
            winner = record if current is None else merge_lww(current, record)
            self.documents[key] = winner
            self.persistence.write_state(DOC_COMPONENT, key, winner.to_mapping())
            return winner

    def _next_sequence(self) -> int:
        """Increment and persist this replica's monotonic sequence."""
        self._sequence += 1
        self.persistence.write_state(
            META_COMPONENT,
            self.replica_id,
            {"sequence": self._sequence, "replica_id": self.replica_id},
        )
        return self._sequence


def converge(*replicas: MasterDatabase) -> None:
    """
    Join every replica with every other replica's bundle until they share state.

    Args:
        replicas: Two or more MasterDatabase instances.

    Returns:
        None
    """
    if len(replicas) < 2:
        raise MasterDatabaseError("converge requires at least two replicas")
    bundles = [replica.export_bundle() for replica in replicas]
    for replica in replicas:
        for bundle in bundles:
            replica.merge_bundle(bundle)


def _jsonable(value: object) -> object:
    """Convert a document payload into JSON-stable primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    raise MasterDatabaseError(f"document value is not JSON-stable: {type(value).__name__}")


def _bootstrap_path() -> None:
    """Ensure repo root is importable when this file is executed directly."""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


if __name__ == "__main__":
    _bootstrap_path()
    raise SystemExit("MasterDatabase is a library; run test/master_db/test_master_db.py")
