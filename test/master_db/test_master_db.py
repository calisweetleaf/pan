"""Direct consumer for the CRDT master database.

Real tempdir SQLite via PANPersistenceStore / DHTNode. No mocks.
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

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PAN_SDK import DHTNode, PANPersistenceStore, SovereignIdentity
from PAN_SDK.master_db import (
    MasterDatabase,
    MasterDatabaseError,
    converge,
)


class CheckFailure(Exception):
    """A named master_db check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _open_db(tmpdir: str, name: str) -> tuple[MasterDatabase, PANPersistenceStore]:
    """Open a replica on its own sqlite file."""
    identity = SovereignIdentity(name)
    store = PANPersistenceStore(base_path=Path(tmpdir) / name)
    return MasterDatabase(identity.identity_hash, store), store


def _sync(left: MasterDatabase, right: MasterDatabase) -> None:
    """Exchange only pages whose hashes differ, then join both ways."""
    from_right = right.export_pages(left.pages_needed(right.page_hashes()))
    from_left = left.export_pages(right.pages_needed(left.page_hashes()))
    print(f"sync pages left<-right={len(from_right)} right<-left={len(from_left)}")
    left.merge_pages(from_right)
    right.merge_pages(from_left)


def check_offline_nodes_converge(details: dict[str, object]) -> None:
    """Two partitioned replicas write, then converge to one document set."""
    with tempfile.TemporaryDirectory(prefix="mdb_conv_") as tmpdir:
        db_a, store_a = _open_db(tmpdir, "ReplicaA")
        db_b, store_b = _open_db(tmpdir, "ReplicaB")
        try:
            db_a.put("citizen:ann", {"role": "chair", "tokens": 1})
            db_b.put("citizen:bea", {"role": "verifier", "tokens": 2})
            db_a.increment("inference_cycles", 4)
            db_b.increment("inference_cycles", 7)
            db_a.add("validators", "ann")
            db_b.add("validators", "bea")
            before_a = db_a.snapshot()
            before_b = db_b.snapshot()
            print(f"before A docs={list(before_a['documents'])} ctr={before_a['counters']}")
            print(f"before B docs={list(before_b['documents'])} ctr={before_b['counters']}")
            if "citizen:bea" in before_a["documents"] or "citizen:ann" in before_b["documents"]:
                raise CheckFailure("replicas were not partitioned")
            _sync(db_a, db_b)
            after_a = db_a.snapshot()
            after_b = db_b.snapshot()
            print(f"after A={after_a}")
            print(f"after B={after_b}")
            if after_a != after_b:
                raise CheckFailure("replicas diverged after sync")
            if after_a["documents"].get("citizen:ann", {}).get("role") != "chair":
                raise CheckFailure("ann document missing after join")
            if after_a["documents"].get("citizen:bea", {}).get("role") != "verifier":
                raise CheckFailure("bea document missing after join")
            if after_a["counters"].get("inference_cycles") != 11:
                raise CheckFailure(f"G-counter did not sum, got {after_a['counters']}")
            if set(after_a["sets"].get("validators") or []) != {"ann", "bea"}:
                raise CheckFailure("OR-set did not union")
            identical = db_a.pages_needed(db_b.page_hashes())
            if identical:
                raise CheckFailure(f"page hashes still differ: {identical}")
            details["counter"] = after_a["counters"]["inference_cycles"]
            details["docs"] = sorted(after_a["documents"])
        finally:
            store_a.close()
            store_b.close()


def check_join_algebra(details: dict[str, object]) -> None:
    """Join is idempotent, commutative, and associative across three replicas."""
    with tempfile.TemporaryDirectory(prefix="mdb_alg_") as tmpdir:
        db_a, sa = _open_db(tmpdir, "AlgA")
        db_b, sb = _open_db(tmpdir, "AlgB")
        db_c, sc = _open_db(tmpdir, "AlgC")
        db_a2, sa2 = _open_db(tmpdir, "AlgA2")
        db_b2, sb2 = _open_db(tmpdir, "AlgB2")
        db_c2, sc2 = _open_db(tmpdir, "AlgC2")
        try:
            db_a.put("k", "alpha")
            db_b.put("k", "beta")
            db_c.put("k", "gamma")
            db_a2.put("k", "alpha")
            db_b2.put("k", "beta")
            db_c2.put("k", "gamma")
            # Force identical payloads onto the second trio by copying bundles is
            # not possible after distinct timestamps. Use dedicated keys instead.
            for db in (db_a, db_b, db_c, db_a2, db_b2, db_c2):
                db.delete("k")
            db_a.put("from_a", 1)
            db_b.put("from_b", 2)
            db_c.put("from_c", 3)
            db_a2.put("from_a", 1)
            db_b2.put("from_b", 2)
            db_c2.put("from_c", 3)

            bundle_a = db_a.export_bundle()
            db_a.merge_bundle(bundle_a)
            db_a.merge_bundle(bundle_a)
            if db_a.snapshot()["documents"] != {"from_a": 1}:
                raise CheckFailure("idempotent join mutated local state")

            converge(db_a, db_b)
            snap_ab = db_a.snapshot()
            converge(db_b2, db_a2)
            snap_ba = db_a2.snapshot()
            if snap_ab != snap_ba:
                raise CheckFailure("join was not commutative")
            print(f"commutative snapshot docs={snap_ab['documents']}")

            converge(db_a, db_b, db_c)
            left = db_a.snapshot()
            converge(db_c2, db_b2, db_a2)
            right = db_c2.snapshot()
            print(f"associative left={left['documents']} right={right['documents']}")
            if left != right:
                raise CheckFailure("join was not associative")
            if set(left["documents"]) != {"from_a", "from_b", "from_c"}:
                raise CheckFailure("three-way join dropped a document")
            details["commutative"] = True
            details["associative"] = True
            details["idempotent"] = True
        finally:
            for store in (sa, sb, sc, sa2, sb2, sc2):
                store.close()


def check_tombstone_and_orset_remove(details: dict[str, object]) -> None:
    """Later tombstones win; OR-set remove observes add tags after a join."""
    with tempfile.TemporaryDirectory(prefix="mdb_tomb_") as tmpdir:
        db_a, sa = _open_db(tmpdir, "TombA")
        db_b, sb = _open_db(tmpdir, "TombB")
        try:
            db_a.put("note", "live")
            db_a.add("roster", "citizen-1")
            _sync(db_a, db_b)
            if db_b.get("note") != "live":
                raise CheckFailure("peer did not receive document")
            db_b.delete("note")
            db_b.remove("roster", "citizen-1")
            _sync(db_a, db_b)
            print(f"after tombstone A.get={db_a.get('note')} members={db_a.members('roster')}")
            if db_a.get("note") is not None or db_b.get("note") is not None:
                raise CheckFailure("tombstone did not win")
            if db_a.members("roster") or db_b.members("roster"):
                raise CheckFailure("OR-set remove did not converge empty")
            details["tombstone"] = True
        finally:
            sa.close()
            sb.close()


def check_dht_bind_and_restart(details: dict[str, object]) -> None:
    """DHTNode owns MasterDatabase on the same sqlite; restart hydrates."""
    chair = SovereignIdentity("MasterChair")
    pem = chair.serialize_private_key()
    with tempfile.TemporaryDirectory(prefix="mdb_dht_") as tmpdir:
        store = PANPersistenceStore(base_path=Path(tmpdir) / "pan")
        node = DHTNode(chair, persistence=store, enable_consensus=False)
        try:
            if node.master_db is None:
                raise CheckFailure("DHTNode did not bind MasterDatabase")
            node.master_db.put("policy", {"emission": 1})
            node.master_db.increment("cycles", 3)
            details["before"] = node.master_db.get("policy")
        finally:
            store.close()

        restored = SovereignIdentity("MasterChair", private_key_pem=pem)
        store2 = PANPersistenceStore(base_path=Path(tmpdir) / "pan")
        node2 = DHTNode(restored, persistence=store2, enable_consensus=False)
        try:
            value = node2.master_db.get("policy")
            cycles = node2.master_db.counter_value("cycles")
            print(f"reopened policy={value} cycles={cycles}")
            if value != {"emission": 1}:
                raise CheckFailure("document did not hydrate")
            if cycles != 3:
                raise CheckFailure("counter did not hydrate")
            details["after"] = value
            details["cycles"] = cycles
        finally:
            store2.close()


CHECKS = (
    ("offline_nodes_converge", check_offline_nodes_converge),
    ("join_algebra", check_join_algebra),
    ("tombstone_and_orset_remove", check_tombstone_and_orset_remove),
    ("dht_bind_and_restart", check_dht_bind_and_restart),
)


def run() -> dict[str, object]:
    """Execute every master_db check and return a gate-shaped payload."""
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
            checks.append({"name": name, "status": "fail", "error": str(exc), "detail": detail})
            failed_count += 1
        except (
            MasterDatabaseError,
            AssertionError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
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
        "name": "master_db",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
    }
    if not passed:
        payload["error"] = f"{failed_count} master_db checks failed"
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
        f"# Master database CRDT run {timestamp}",
        "",
        f"I ran `python test/master_db/test_master_db.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required offline writes, commutative/associative/idempotent join,",
        "page-hash skip of identical replicas, tombstones, and DHTNode hydrate.",
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
    lines.extend(["", "## Artifacts", "", f"- `{json_path}`", f"- `{md_path}`", f"- `{log_path}`", ""])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "md": md_path, "log": log_path, "run_dir": run_dir}


def main() -> int:
    """Run checks, persist artifacts, print a gate-shaped summary."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        print(f"master_db consumer start {timestamp}")
        payload = run()
        print(f"master_db consumer status={payload.get('status')}")
    log_text = buffer.getvalue()
    sys.stdout.write(log_text)
    artifacts = write_artifacts(payload, timestamp, log_text)
    payload["artifacts"] = {key: str(path) for key, path in artifacts.items()}
    artifacts["json"].write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"artifacts json={artifacts['json']}")
    print(f"artifacts md={artifacts['md']}")
    print(f"artifacts log={artifacts['log']}")
    return 0 if payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
