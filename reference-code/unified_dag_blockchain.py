"""
Unified DAG Blockchain Implementation

This file combines concepts from:
1. Mycelial Temporal Lattice - A sovereign, fork-aware, auto-reflexive, belief-anchored memory fabric
2. Sovereign Cognitive Lattice - A post-blockchain framework for sovereign temporal record-keeping
3. NMCA Memory - Neural Memory Controller Architecture with quantum-inspired techniques

The implementation creates a Directed Acyclic Graph (DAG) based blockchain that supports:
- Multi-parent blocks (strands)
- Belief-based anchoring instead of traditional consensus
- Epistemic linking for knowledge evolution
- Policy mutation through meta-blocks
- Auto-repair mechanisms for contradictions
- Memory management with relevance scoring
"""

import hashlib
import uuid
import sqlite3
import json
import time
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum, auto
from collections import defaultdict
import os
import tempfile
import time
import zlib
import hashlib as _hashlib
import logging

# Configure logging
logger = logging.getLogger("DAG_Blockchain")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s"
    )
    file_handler = logging.FileHandler("dag_blockchain.log")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.info("Logging handlers configured.")

# --------------------------- #
# --------- Utilities --------#
# --------------------------- #


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(obj) -> str:
    """Deterministic JSON for hashing. No whitespace, sorted keys."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha512_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha512(data).hexdigest()


def atomic_write_json(path: str, data: Any) -> None:
    """Atomically write JSON to path using a temp file and os.replace.

    Keeps partial writes from corrupting files when interrupted.
    """
    import json

    dirpath = os.path.dirname(path) or "."
    os.makedirs(dirpath, exist_ok=True)
    fd, tmppath = tempfile.mkstemp(prefix=".tmp", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                data, f, separators=(",", ":"), sort_keys=True, ensure_ascii=False
            )
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmppath, path)
    finally:
        if os.path.exists(tmppath):
            try:
                os.remove(tmppath)
            except Exception:
                pass


class BinaryStorageManager:
    """Small compressed JSON binary store for measured states.

    Files are stored under memory_store/binary/ with stable names (sha512 of content).
    """

    def __init__(self, storage_dir: str = "memory_store/binary"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def _ref_path(self, ref_id: str) -> str:
        return os.path.join(self.storage_dir, f"{ref_id}.bin")

    def store_json_compressed(self, data: Any) -> str:
        import json

        payload = json.dumps(
            data, separators=(",", ":"), sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
        compressed = zlib.compress(payload)
        ref_id = _hashlib.sha256(payload).hexdigest()
        path = self._ref_path(ref_id)
        # atomic write of the binary blob
        fd, tmppath = tempfile.mkstemp(prefix=".tmp", dir=self.storage_dir)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(compressed)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmppath, path)
        finally:
            if os.path.exists(tmppath):
                try:
                    os.remove(tmppath)
                except Exception:
                    pass
        return ref_id

    def load_json_compressed(self, ref_id: str) -> Any:
        import json

        path = self._ref_path(ref_id)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        with open(path, "rb") as f:
            compressed = f.read()
        payload = zlib.decompress(compressed)
        return json.loads(payload.decode("utf-8"))


def derive_uuid(prefix: str = "") -> str:
    """Namespaced deterministic-ish UUID if prefix provided; random otherwise."""
    if prefix:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, prefix))
    return str(uuid.uuid4())


def text_to_semvec(text: str, dims: int = 12) -> list[float]:
    """
    Pseudo-embedding with zero dependencies:
    - Hash the text with SHA-512
    - Slice into dims chunks
    - Map to [-1, 1] floats
    Note: This is NOT semantic magic; it's a stable placeholder to enable vector math locally.
    """
    h = hashlib.sha512(text.encode("utf-8")).digest()
    # repeat digest if dims > 64 bytes/8 = 8 floats; we need dims values
    buf = (h * ((dims * 8) // len(h) + 1))[: dims * 8]
    out = []
    for i in range(0, len(buf), 8):
        chunk = int.from_bytes(buf[i : i + 8], byteorder="big", signed=False)
        # map [0, 2^64-1] -> [-1, 1]
        out.append((chunk / 2**63) - 1.0)
    return out


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity for small vectors (no numpy)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = (sum(x * x for x in a) or 1.0) ** 0.5
    nb = (sum(y * y for y in b) or 1.0) ** 0.5
    return dot / (na * nb)


# --------------------------- #
# --------- Identity ---------#
# --------------------------- #


class Agent:
    """
    Sovereign actor identity (human, AI, script). No PKI ceremony in this prototype.
    We emulate signatures using shared-secrets hashed with message, for local-only assurance.
    """

    def __init__(self, name: str, secret: str | None = None):
        self.name = name
        # Agent ID is a stable hash of the name (you can swap for real keys later).
        self.agent_id = sha512_hex(f"agent::{name}")[:64]
        # Secret is used to create attestation signatures (naive HMAC-like).
        self.secret = secret or sha512_hex(f"seed::{uuid.uuid4()}")[:64]

    def sign(self, payload: str) -> str:
        return sha512_hex(self.secret + "::" + payload)

    def attest(self, block_id: str, belief: float, rationale: str = "") -> dict:
        """
        Belief ∈ [0,1] is the 'epistemic weight' this agent assigns to a block.
        Rationale is hashed; keep it short or persist elsewhere.
        """
        belief = max(0.0, min(1.0, float(belief)))
        rationale_hash = sha512_hex(rationale) if rationale else ""
        payload = canonical(
            {
                "block_id": block_id,
                "agent_id": self.agent_id,
                "belief": belief,
                "rh": rationale_hash,
            }
        )
        signature = self.sign(payload)
        return {
            "attestation_id": sha512_hex(payload)[:64],
            "block_id": block_id,
            "agent_id": self.agent_id,
            "belief": belief,
            "rationale_hash": rationale_hash,
            "signature": signature,
            "ts": utc_now_iso(),
        }


# --------------------------- #
# ---------- Blocks ----------#
# --------------------------- #


class Block:
    """
    A block is a *cognitive residue*, not a transaction.
    Types (kind):
      - "event": factual or experiential record
      - "belief": claim, hypothesis, evaluation, or alignment check
      - "meta": policy patch that mutates ledger rules forward along descendants
      - "repair": synthesis/bridge that resolves contradictions or recontextualizes forks
      - "snapshot": checkpoint/summary for compaction or export
    """

    def __init__(
        self,
        author_id: str,
        kind: str,
        body: dict,
        parents: list[str] | None = None,
        semantics: str | None = None,
        meta_patch: dict | None = None,
    ):
        self.ts = utc_now_iso()
        self.author = author_id
        self.kind = kind
        self.body = body or {}
        self.parents = parents or []  # multi-parent => DAG (lattice), not linear chain
        self.meta_patch = meta_patch or {}
        # Semantic vector is derived from the "semantics" string or from a projection of body.
        semtext = semantics or self._default_semantic_text()
        self.semvec = text_to_semvec(semtext, dims=12)
        # ID is a hash over canonicalized minimal fields.
        self.block_id = self._compute_id()

    def _default_semantic_text(self) -> str:
        head = (
            self.body.get("summary")
            or self.body.get("claim")
            or self.body.get("title")
            or ""
        )
        tail = (
            self.body.get("details")
            or self.body.get("content")
            or canonical(self.body)[:256]
        )
        return f"{self.kind}::{head}::{tail}"

    def _compute_id(self) -> str:
        m = {
            "ts": self.ts,
            "author": self.author,
            "kind": self.kind,
            "parents": self.parents,
            "body": self.body,
            "meta_patch": self.meta_patch,
            "sem": [round(x, 6) for x in self.semvec],
        }
        return sha512_hex(canonical(m))[:64]


# --------------------------- #
# ---------- Memory ----------#
# --------------------------- #

# Constants for memory relevance calculation
ALPHA = 0.4  # Frequency usage weight
BETA = 0.3  # Contextual utility weight
GAMMA = 0.2  # Cross domain connections weight
DELTA = 0.1  # Energy cost weight


@dataclass
class MemoryNode:
    """Represents a node in the memory graph with sophisticated attributes."""

    node_id: str
    frequency_usage: float
    contextual_utility: float
    cross_domain_connections: int
    energy_cost: float
    creation_timestamp: float = None
    last_access_timestamp: float = None
    access_count: int = 0
    metadata: Dict[str, Any] = None
    content_hash: str = None

    def __post_init__(self):
        if self.creation_timestamp is None:
            self.creation_timestamp = time.time()
        if self.last_access_timestamp is None:
            self.last_access_timestamp = self.creation_timestamp
        if self.metadata is None:
            self.metadata = {}
        if self.content_hash is None:
            self.content_hash = hashlib.sha256(self.node_id.encode()).hexdigest()

    def calculate_relevance(self) -> float:
        """Calculate the relevance score for this memory node."""
        age_factor = max(
            0.1,
            min(
                1.0,
                1.0 / (1.0 + 0.01 * (time.time() - self.last_access_timestamp) / 3600),
            ),
        )
        relevance = (
            ALPHA * self.frequency_usage
            + BETA * self.contextual_utility
            + GAMMA * self.cross_domain_connections
            - DELTA * self.energy_cost
        ) * age_factor
        logger.debug(f"Calculated relevance for node {self.node_id}: {relevance}")
        return relevance

    def record_access(self):
        """Record an access to this memory node."""
        self.last_access_timestamp = time.time()
        self.access_count += 1
        self.frequency_usage = min(1.0, self.frequency_usage + 0.01)

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryNode":
        """Create a memory node from dictionary data."""
        return cls(**data)


# --------------------------- #
# ---------- Ledger ----------#
# --------------------------- #


class DAGLedger:
    """
    The DAG Ledger persists a fork-aware DAG of Blocks + Attestations.
    - No global consensus; blocks *anchor* locally if belief stability crosses thresholds
      derived from effective policy (policy is mutable via meta-blocks).
    - Policy composition is lineage-sensitive: effective policy at a node
      = fold(default_policy, all meta_patches along ancestry).
    """

    DEFAULT_POLICY = {
        "anchor_threshold": 0.74,  # min mean belief to become "anchored"
        "anchor_support_min": 2,  # min distinct agents needed to consider anchoring
        "contradiction_cosine": 0.82,  # similarity threshold to consider two claims comparable
        "repair_auto": True,  # produce repair blocks automatically when contradictions found
        "belief_half_life": 0.0,  # set >0 to decay older attestations over time (not implemented here)
        "max_parents": 5,  # guardrail for DAG fan-in
    }

    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_schema()
        # Install genesis meta if DB is empty.
        if not self._has_blocks():
            self.install_genesis()
        # Memory management
        self.memory_nodes: Dict[str, MemoryNode] = {}
        self.boundary_lock = threading.RLock()

    # ---------- Schema ---------- #

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS blocks (
                block_id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                author TEXT NOT NULL,
                kind TEXT NOT NULL,
                parents TEXT NOT NULL,     -- JSON list[str]
                body TEXT NOT NULL,        -- JSON
                semvec TEXT NOT NULL,      -- JSON list[float]
                meta_patch TEXT NOT NULL   -- JSON dict
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS edges (
                parent TEXT NOT NULL,
                child  TEXT NOT NULL,
                PRIMARY KEY (parent, child)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS attestations (
                attestation_id TEXT PRIMARY KEY,
                block_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                belief REAL NOT NULL,
                rationale_hash TEXT,
                signature TEXT NOT NULL,
                ts TEXT NOT NULL
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS anchors (
                block_id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                score REAL NOT NULL
            );
            """
        )
        self.conn.commit()

    def _has_blocks(self) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(1) FROM blocks;")
        return cur.fetchone()[0] > 0

    # ---------- Genesis ---------- #

    def install_genesis(self):
        """
        Genesis is a "meta" block that seeds policy for the local lattice.
        """
        genesis_author = sha512_hex("system::genesis")[:64]
        g = Block(
            author_id=genesis_author,
            kind="meta",
            body={"summary": "Genesis policy", "content": "Initialize lattice"},
            parents=[],
            semantics="genesis::policy",
            meta_patch=self.DEFAULT_POLICY,
        )
        self._insert_block(g)
        # Anchor genesis by fiat (no consensus needed).
        self._anchor_block(g.block_id, score=1.0)

    # ---------- Core ops ---------- #

    def add_block(self, block: Block):
        # Enforce max parents from effective policy at *creation time* based on ancestry of parents (best-effort).
        efp = self.effective_policy(self._pick_reference_ancestor(block.parents))
        if len(block.parents) > efp.get("max_parents", 5):
            raise ValueError("Too many parents for policy.")
        self._insert_block(block)
        if block.parents:
            cur = self.conn.cursor()
            for p in block.parents:
                cur.execute(
                    "INSERT OR IGNORE INTO edges(parent, child) VALUES(?,?)",
                    (p, block.block_id),
                )
            self.conn.commit()
        # If this is meta, it will modify policy downstream for descendants implicitly.
        if block.kind == "meta":
            # Optionally, anchor meta immediately if authored by a trusted root (omitted here).
            pass
        # Auto repair pass if requested.
        efp = self.effective_policy(block.block_id)
        if efp.get("repair_auto", True):
            self.repair_pass(block.block_id)

    def _insert_block(self, block: Block):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO blocks(block_id, ts, author, kind, parents, body, semvec, meta_patch) VALUES (?,?,?,?,?,?,?,?)",
            (
                block.block_id,
                block.ts,
                block.author,
                block.kind,
                canonical(block.parents),
                canonical(block.body),
                canonical(block.semvec),
                canonical(block.meta_patch),
            ),
        )
        self.conn.commit()

    def attest(self, attestation: dict) -> float:
        """
        Record an attestation and possibly anchor the block if stability >= threshold.
        Returns the current stability score post-insert.
        """
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO attestations(attestation_id, block_id, agent_id, belief, rationale_hash, signature, ts) VALUES (?,?,?,?,?,?,?)",
            (
                attestation["attestation_id"],
                attestation["block_id"],
                attestation["agent_id"],
                attestation["belief"],
                attestation.get("rationale_hash", ""),
                attestation["signature"],
                attestation["ts"],
            ),
        )
        self.conn.commit()
        score = self.stability(attestation["block_id"])
        # Maybe anchor
        pol = self.effective_policy(attestation["block_id"])
        if self._eligible_for_anchor(attestation["block_id"], score, pol):
            self._anchor_block(attestation["block_id"], score)
        return score

    # ---------- Policy ---------- #

    def effective_policy(self, at_block_id: str | None) -> dict:
        """
        Compose policy by walking ancestry from genesis to 'at_block_id' and folding meta patches.
        """
        policy = dict(self.DEFAULT_POLICY)
        if not at_block_id:
            return policy

        lineage = self._ancestry_linearization(at_block_id)
        # Fold patches in order.
        for b in lineage:
            if b["kind"] == "meta":
                try:
                    patch = json.loads(b["meta_patch"])
                    for k, v in patch.items():
                        policy[k] = v
                except Exception:
                    continue
        return policy

    def _ancestry_linearization(self, block_id: str) -> list[dict]:
        """
        Linearize a partial order for policy composition. We choose a deterministic DFS with lexical sort of parents.
        Return: list of block rows from oldest -> newest along an arbitrary but stable path to the root.
        """
        cur = self.conn.cursor()
        # Build parent map
        parents = {}
        cur.execute("SELECT parent, child FROM edges")
        for p, c in cur.fetchall():
            parents.setdefault(c, []).append(p)
        # DFS from node to root picking lexicographically smallest parent each hop
        path = []
        current = block_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            row = self._get_block_row(current)
            if row:
                path.append(row)
            ps = sorted(parents.get(current, []))
            current = ps[0] if ps else None
        # Reverse so genesis is first
        return list(reversed(path))

    # ---------- Stability / Anchors ---------- #

    def stability(self, block_id: str) -> float:
        """
        Compute belief stability as simple mean of beliefs from distinct agents.
        Hooks can be added for weighting, decay, or agency trust models.
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT agent_id, belief FROM attestations WHERE block_id = ?",
            (block_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return 0.0
        # Distinct agents only
        by_agent = {}
        for a, b in rows:
            by_agent[a] = float(b)
        return sum(by_agent.values()) / max(1, len(by_agent))

    def _eligible_for_anchor(self, block_id: str, score: float, policy: dict) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(DISTINCT agent_id) FROM attestations WHERE block_id = ?",
            (block_id,),
        )
        supporters = cur.fetchone()[0] or 0
        return (supporters >= policy.get("anchor_support_min", 2)) and (
            score >= policy.get("anchor_threshold", 0.74)
        )

    def _anchor_block(self, block_id: str, score: float):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO anchors(block_id, ts, score) VALUES (?,?,?)",
            (block_id, utc_now_iso(), score),
        )
        self.conn.commit()

    # ---------- Reflex / Repair ---------- #

    def repair_pass(self, pivot_id: str | None = None):
        """
        Scan for high-similarity, oppositely-valenced claims in the neighborhood of 'pivot_id'.
        If found, produce a repair 'synthesis' block with both as parents.
        """
        # Pull recent-ish or related blocks; to keep it simple, we scan all blocks and then focus by cosine to pivot.
        cur = self.conn.cursor()
        cur.execute("SELECT block_id, kind, body, semvec FROM blocks")
        rows = cur.fetchall()
        blocks = []
        for bid, kind, body, semvec in rows:
            blocks.append(
                {
                    "block_id": bid,
                    "kind": kind,
                    "body": json.loads(body),
                    "semvec": json.loads(semvec),
                }
            )

        # If pivot provided, focus on near-neighbors.
        neighborhood = blocks
        if pivot_id:
            pivot = next((b for b in blocks if b["block_id"] == pivot_id), None)
            if pivot:
                scored = [
                    (cosine(pivot["semvec"], b["semvec"]), b)
                    for b in blocks
                    if b["block_id"] != pivot_id
                ]
                scored.sort(key=lambda t: t[0], reverse=True)
                # Take the top 32 by similarity
                neighborhood = [b for _, b in scored[:32]]

        policy = (
            self.effective_policy(pivot_id) if pivot_id else dict(self.DEFAULT_POLICY)
        )
        th = policy.get("contradiction_cosine", 0.82)

        # Detect contradictions: two belief/event blocks with opposing 'polarity' in body.
        # Polarity is a simple prototype: body.get("polarity", +1/-1/0)
        pairs = []
        n = len(neighborhood)
        for i in range(n):
            a = neighborhood[i]
            if a["kind"] not in ("belief", "event"):
                continue
            for j in range(i + 1, n):
                b = neighborhood[j]
                if b["kind"] not in ("belief", "event"):
                    continue
                sim = cosine(a["semvec"], b["semvec"])
                if sim < th:
                    continue
                pa = int(a["body"].get("polarity", 0))
                pb = int(b["body"].get("polarity", 0))
                if pa * pb < 0:  # opposite valence
                    pairs.append((a, b, sim))

        # Create one synthesis per pair if not already bridged.
        for a, b, sim in pairs[:8]:  # soft cap to avoid explosion
            if self._already_bridged(a["block_id"], b["block_id"]):
                continue
            bridge = self._synthesis_block(a, b, sim)
            self.add_block(bridge)

    def _already_bridged(self, a_id: str, b_id: str) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT child FROM edges
            JOIN blocks ON blocks.block_id = edges.child
            WHERE edges.parent IN (?, ?) AND blocks.kind = 'repair'
            GROUP BY child
            HAVING COUNT(DISTINCT parent) = 2
            """,
            (a_id, b_id),
        )
        return cur.fetchone() is not None

    def _synthesis_block(self, a: dict, b: dict, sim: float) -> Block:
        """
        Build a 'repair' block that records the contradiction and proposes a synthesis.
        Synthesis mode is naive: 'coexist' if neither anchored dominates; 'override' if one is anchored with high score.
        """
        a_id, b_id = a["block_id"], b["block_id"]
        a_anchor = self._anchor_score(a_id)
        b_anchor = self._anchor_score(b_id)

        if a_anchor >= 0.9 and b_anchor < 0.5:
            mode = "override_a"
        elif b_anchor >= 0.9 and a_anchor < 0.5:
            mode = "override_b"
        else:
            mode = "coexist"

        summary = f"synthesis::{mode}::sim={round(sim, 3)}"
        content = {
            "contradiction": [a_id, b_id],
            "anchor_scores": {"a": a_anchor, "b": b_anchor},
            "policy_hint": {
                "preferred": "higher_anchor"
                if mode.startswith("override")
                else "coexist"
            },
        }
        sem = f"repair::{summary}::{a['body'].get('summary', '')}::{b['body'].get('summary', '')}"
        author = sha512_hex("system::repair")[:64]
        return Block(
            author_id=author,
            kind="repair",
            body={"summary": summary, "content": content},
            parents=[a_id, b_id],
            semantics=sem,
        )

    def _anchor_score(self, block_id: str) -> float:
        cur = self.conn.cursor()
        cur.execute("SELECT score FROM anchors WHERE block_id = ?", (block_id,))
        row = cur.fetchone()
        return float(row[0]) if row else 0.0

    # ---------- Query / Introspection ---------- #

    def get_block(self, block_id: str) -> dict | None:
        row = self._get_block_row(block_id)
        if not row:
            return None
        return {
            "block_id": row["block_id"],
            "ts": row["ts"],
            "author": row["author"],
            "kind": row["kind"],
            "parents": json.loads(row["parents"]),
            "body": json.loads(row["body"]),
            "semvec": json.loads(row["semvec"]),
            "meta_patch": json.loads(row["meta_patch"]),
        }

    def tips(self) -> list[str]:
        """
        Return block_ids with no children (frontier tips).
        """
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT b.block_id
            FROM blocks b
            LEFT JOIN edges e ON b.block_id = e.parent
            WHERE e.parent IS NULL
            """
        )
        return [r[0] for r in cur.fetchall()]

    def anchored(self) -> list[tuple[str, float]]:
        cur = self.conn.cursor()
        cur.execute("SELECT block_id, score FROM anchors ORDER BY ts ASC")
        return [(b, float(s)) for (b, s) in cur.fetchall()]

    # ---------- Memory Management ---------- #

    def create_memory_node(self, node_id: str, **kwargs) -> MemoryNode:
        """Create a new memory node with the given parameters."""
        with self.boundary_lock:
            node = MemoryNode(node_id=node_id, **kwargs)
            self.memory_nodes[node_id] = node
            logger.info(f"Created memory node: {node_id}")
            return node

    def get_memory_node(self, node_id: str) -> MemoryNode | None:
        """Retrieve a memory node by its ID."""
        with self.boundary_lock:
            return self.memory_nodes.get(node_id)

    # --------------------------- #
    # -- Rosemary helpers ------ #
    # --------------------------- #

    def store_rosemary_fixedpoint(
        self,
        definition: Dict[str, Any],
        measured_state: Any,
        author: Agent | None = None,
    ) -> str:
        """Persist a rosemary fixed-point measured_state and create a coherence_state block.

        Steps:
        1. Store measured_state compressed in BinaryStorageManager -> ref_id
        2. Create a Block(kind='coherence_state') with metadata: rosemary_hash, state_hash, ref_id, ts
        3. Insert block into ledger and return block_id
        """
        bsm = BinaryStorageManager()
        ref_id = bsm.store_json_compressed(
            {
                "definition": definition,
                "measured_state": measured_state,
                "ts": utc_now_iso(),
            }
        )
        rosemary_hash = compute_canonical_rosemary_hash(definition)
        state_hash = compute_state_hash(measured_state)
        author_id = (author.agent_id if author else sha512_hex("system::rosemary"))[:64]
        # Include a small, query-friendly snapshot of the canonical definition
        # so downstream tools can inspect sacred constants without decompressing
        # the full binary blob. The full definition+measured_state remains
        # stored in the compressed binary referenced by `binary_ref`.
        body = {
            "rosemary_hash": rosemary_hash,
            "state_hash": state_hash,
            "binary_ref": ref_id,
            "sacred_ratio": definition.get("sacred_ratio")
            if isinstance(definition, dict)
            else None,
            "bands": definition.get("bands") if isinstance(definition, dict) else None,
            "ts": utc_now_iso(),
        }
        # If measured_state contains small summaries like energies or amplitudes,
        # copy them into the block body for quick inspection (avoid large arrays).
        try:
            if isinstance(measured_state, dict):
                if "energies" in measured_state and isinstance(
                    measured_state["energies"], dict
                ):
                    # keep only scalar entries
                    energies_summary = {}
                    for k, v in measured_state["energies"].items():
                        try:
                            energies_summary[k] = float(v)
                        except Exception:
                            # skip non-scalar heavy entries
                            continue
                    if energies_summary:
                        body["energies_summary"] = energies_summary
                if "amplitudes" in measured_state and isinstance(
                    measured_state["amplitudes"], dict
                ):
                    amps = {}
                    for k, v in measured_state["amplitudes"].items():
                        try:
                            amps[k] = float(v)
                        except Exception:
                            continue
                    if amps:
                        body["amplitudes"] = amps
        except Exception:
            # best-effort only; do not let storage fail for metadata extraction
            pass
        block = Block(
            author_id=author_id,
            kind="coherence_state",
            body=body,
            parents=None,
            semantics=f"coherence::{rosemary_hash[:8]}",
        )
        self.add_block(block)
        # Optionally anchor immediately if policies allow; we'll call attest with a system attestation
        att = {
            "attestation_id": sha512_hex(block.block_id + "::attest")[:64],
            "block_id": block.block_id,
            "agent_id": author_id,
            "belief": 1.0,
            "rationale_hash": "",
            "signature": sha512_hex(author_id + "::" + block.block_id),
            "ts": utc_now_iso(),
        }
        # Insert attestation and attempt anchoring
        try:
            self.attest(att)
        except Exception:
            # best-effort: don't fail the whole operation
            pass
        return block.block_id

    def attach_rosemary_diff_to_node(
        self, node_id: str, rosemary_block_id: str, creator: Agent | None = None
    ) -> bool:
        """Attach an epistemic link between an existing node and a rosemary coherence_state block.

        Creates an epistemic_link block with both as parents, recording the relationship.
        """
        try:
            # Ensure nodes exist
            if not self._get_block_row(node_id):
                raise ValueError(f"node {node_id} not found")
            if not self._get_block_row(rosemary_block_id):
                raise ValueError(f"rosemary block {rosemary_block_id} not found")
            author_id = (creator.agent_id if creator else sha512_hex("system::attach"))[
                :64
            ]
            content = {
                "link_type": "rosemary_attachment",
                "rosemary_block": rosemary_block_id,
                "attached_node": node_id,
                "ts": utc_now_iso(),
            }
            link_block = Block(
                author_id=author_id,
                kind="epistemic_link",
                body=content,
                parents=[node_id, rosemary_block_id],
                semantics=f"attach::rosemary::{rosemary_block_id[:8]}",
            )
            self.add_block(link_block)
            # Auto-attest by creator/system to increase anchor chance
            att = {
                "attestation_id": sha512_hex(link_block.block_id + "::att")[:64],
                "block_id": link_block.block_id,
                "agent_id": author_id,
                "belief": 1.0,
                "rationale_hash": "",
                "signature": sha512_hex(author_id + "::" + link_block.block_id),
                "ts": utc_now_iso(),
            }
            try:
                self.attest(att)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def update_memory_node_relevance(self, node_id: str) -> float:
        """Update and return the relevance score for a memory node."""
        with self.boundary_lock:
            node = self.memory_nodes.get(node_id)
            if node:
                relevance = node.calculate_relevance()
                logger.info(f"Updated relevance for node {node_id}: {relevance}")
                return relevance
            return 0.0

    def record_memory_access(self, node_id: str):
        """Record an access to a memory node."""
        with self.boundary_lock:
            node = self.memory_nodes.get(node_id)
            if node:
                node.record_access()
                logger.debug(f"Recorded access for memory node: {node_id}")

    # ---------- Internals ---------- #

    def _get_block_row(self, block_id: str) -> dict | None:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT block_id, ts, author, kind, parents, body, semvec, meta_patch FROM blocks WHERE block_id = ?",
            (block_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        keys = [
            "block_id",
            "ts",
            "author",
            "kind",
            "parents",
            "body",
            "semvec",
            "meta_patch",
        ]
        return dict(zip(keys, row))

    def _pick_reference_ancestor(self, parents: list[str]) -> str | None:
        """Pick an arbitrary but stable ancestor for policy gating (lexicographically smallest)."""
        if not parents:
            # Fallback to the (only) genesis in a fresh DB.
            cur = self.conn.cursor()
            cur.execute("SELECT block_id FROM blocks ORDER BY ts ASC LIMIT 1")
            r = cur.fetchone()
            return r[0] if r else None
        return sorted(parents)[0]


# --------------------------- #
# --------- Helpers ----------#
# --------------------------- #


def make_event(
    ledger: DAGLedger,
    author: Agent,
    summary: str,
    content: dict,
    parents: list[str] | None = None,
    polarity: int = 0,
) -> Block:
    body = {"summary": summary, "content": content, "polarity": int(polarity)}
    return Block(
        author_id=author.agent_id,
        kind="event",
        body=body,
        parents=parents,
        semantics=f"event::{summary}",
    )


def make_belief(
    ledger: DAGLedger,
    author: Agent,
    claim: str,
    details: str = "",
    parents: list[str] | None = None,
    polarity: int = 0,
) -> Block:
    body = {
        "summary": claim,
        "claim": claim,
        "details": details,
        "polarity": int(polarity),
    }
    return Block(
        author_id=author.agent_id,
        kind="belief",
        body=body,
        parents=parents,
        semantics=f"belief::{claim}",
    )


def make_meta(
    author: Agent,
    patch: dict,
    summary: str = "policy update",
    parents: list[str] | None = None,
) -> Block:
    return Block(
        author_id=author.agent_id,
        kind="meta",
        body={"summary": summary},
        parents=parents,
        semantics=f"meta::{summary}",
        meta_patch=patch,
    )


def reflect(ledger: DAGLedger, source_block: Block, author: Agent) -> Block:
    """
    Auto-reflection: create a 'snapshot' that summarizes the source block in a compact form to help downstream context.
    """
    summary = f"reflect::{source_block.kind}::{source_block.block_id[:10]}"
    digest = sha512_hex(canonical(source_block.body))[:16]
    body = {"summary": summary, "digest": digest, "of": source_block.block_id}
    return Block(
        author_id=author.agent_id,
        kind="snapshot",
        body=body,
        parents=[source_block.block_id],
        semantics=summary,
    )


# --------------------------- #
# -- Rosemary / Coherence -- #
# --------------------------- #


# Simple canonical rosemary hash using deterministic canonicalization
def compute_canonical_rosemary_hash(definition: Dict[str, Any]) -> str:
    return sha512_hex(canonical(definition))[:64]


def compute_state_hash(state: Any) -> str:
    """Compute a stable hash for measured_state (JSON-serializable)."""
    import json

    try:
        s = json.dumps(state, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    except Exception:
        s = repr(state)
    return _hashlib.sha256(s.encode("utf-8")).hexdigest()


# --------------------------- #
# ------------ Demo ----------#
# --------------------------- #

if __name__ == "__main__":
    # Minimal demo of cognitive flow.
    ledger = DAGLedger(":memory:")

    # Two agents with different views.
    alice = Agent("Alice", secret="alice::secret")
    bob = Agent("Bob", secret="bob::secret")

    # 1) Alice records an event.
    e1 = make_event(
        ledger,
        alice,
        "File ingested",
        {"path": "/notes/ethics.md"},
        parents=None,
        polarity=0,
    )
    ledger.add_block(e1)

    # 2) Bob asserts a belief about the event (positive polarity).
    b1 = make_belief(
        ledger,
        bob,
        "This file strengthens alignment",
        details="Ethical commitments reinforced.",
        parents=[e1.block_id],
        polarity=+1,
    )
    ledger.add_block(b1)

    # 3) Alice asserts a contradictory belief (negative polarity) about the same theme.
    b2 = make_belief(
        ledger,
        alice,
        "This file weakens alignment",
        details="Ambiguity increases risk.",
        parents=[e1.block_id],
        polarity=-1,
    )
    ledger.add_block(b2)

    # 4) Agents attest (belief-stability sign-offs).
    ledger.attest(
        alice.attest(b1.block_id, belief=0.40, rationale="Skeptical but open")
    )
    ledger.attest(bob.attest(b1.block_id, belief=0.95, rationale="Strong evidence"))
    ledger.attest(
        alice.attest(b2.block_id, belief=0.92, rationale="Risk pattern observed")
    )
    ledger.attest(bob.attest(b2.block_id, belief=0.10, rationale="Overstated"))

    # 5) Auto-repair pass should synthesize a bridge block (coexist/override).
    #    Called automatically by add_block; run again explicitly:
    ledger.repair_pass(b1.block_id)

    # 6) Policy mutation via meta-block (raise anchor threshold).
    pol_patch = {"anchor_threshold": 0.80, "contradiction_cosine": 0.78}
    m1 = make_meta(alice, pol_patch, summary="tighten_anchoring", parents=[b1.block_id])
    ledger.add_block(m1)

    # 7) Reflect to create snapshots for compaction/navigation.
    s1 = reflect(ledger, b1, author=bob)
    ledger.add_block(s1)

    # 8) Create some memory nodes
    memory_node1 = ledger.create_memory_node(
        node_id="memory_1",
        frequency_usage=0.8,
        contextual_utility=0.7,
        cross_domain_connections=5,
        energy_cost=0.2,
    )
    memory_node2 = ledger.create_memory_node(
        node_id="memory_2",
        frequency_usage=0.5,
        contextual_utility=0.9,
        cross_domain_connections=3,
        energy_cost=0.1,
    )

    # 9) Record access and calculate relevance
    ledger.record_memory_access("memory_1")
    relevance1 = ledger.update_memory_node_relevance("memory_1")
    relevance2 = ledger.update_memory_node_relevance("memory_2")

    # Print a brief view:
    print("Anchored blocks (id, score):")
    for bid, score in ledger.anchored():
        print("  ", bid[:12], score)

    print("\nFrontier tips:")
    for t in ledger.tips():
        print("  ", t[:12])

    # Inspect one block:
    any_block = ledger.get_block(b1.block_id)
    print("\nBelief block details (truncated):")
    print(
        json.dumps(
            {k: (v if k != "semvec" else "[..]") for k, v in any_block.items()},
            indent=2,
        )
    )

    # Print memory node information
    print("\nMemory node relevance scores:")
    print(f"  {memory_node1.node_id}: {relevance1}")
    print(f"  {memory_node2.node_id}: {relevance2}")
