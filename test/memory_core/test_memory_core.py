"""Direct consumer for Thyris VM memory (memory_core + system_cache).

Real tempdir sqlite/cache fixtures. No mocks.
USMS is imported only to prove it is a separate class.
Prints a run report and writes JSON/MD/LOG artifacts.
"""

from __future__ import annotations

import asyncio
import io
import json
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

from memory.memory_core import (
    LocalHashEmbeddingModel,
    MemoryConfiguration,
    MemoryImportance,
    MemoryManager,
    MemoryType,
)
from memory.system_cache import CacheNamespace, SomnusCache
from memory.unified_memory_system import UnifiedMemorySystem


class CheckFailure(Exception):
    """A named Thyris memory check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def check_owners_are_not_usms(details: dict[str, object]) -> None:
    """Thyris MemoryManager and USMS are different classes in the same package."""
    if MemoryManager is UnifiedMemorySystem:
        raise CheckFailure("MemoryManager collapsed into UnifiedMemorySystem")
    if LocalHashEmbeddingModel is UnifiedMemorySystem:
        raise CheckFailure("embedding fallback collapsed into USMS")
    details["memory_manager"] = MemoryManager.__module__
    details["usms"] = UnifiedMemorySystem.__module__
    print(f"thyris owner={MemoryManager.__module__}")
    print(f"usms owner={UnifiedMemorySystem.__module__}")


def check_memory_store_retrieve(details: dict[str, object]) -> None:
    """Construct MemoryManager on a tempdir and store/retrieve a real entry."""

    async def _run(tmpdir: str) -> None:
        config = MemoryConfiguration(
            vector_db_path=str(Path(tmpdir) / "vectors"),
            metadata_db_path=str(Path(tmpdir) / "metadata.db"),
            encryption_enabled=True,
            semantic_clustering=False,
        )
        manager = MemoryManager(config)
        print(f"metadata_db={manager.metadata_db_path}")
        try:
            await manager.initialize()
            if not isinstance(manager.embedding_model, LocalHashEmbeddingModel):
                print(
                    f"embedding_model={type(manager.embedding_model).__name__} "
                    "(transformer present; hash fallback not required)"
                )
            else:
                print("embedding_model=LocalHashEmbeddingModel")
            memory_id = await manager.store_memory(
                user_id="citizen:ann",
                content="sovereign phone session token alpha",
                memory_type=MemoryType.SYSTEM_EVENT,
                importance=MemoryImportance.HIGH,
                tags=["thyris", "gate"],
            )
            print(f"stored memory_id={memory_id}")
            rows = await manager.retrieve_memories(
                user_id="citizen:ann",
                query="phone session",
                limit=5,
                include_content=True,
            )
            print(f"retrieved count={len(rows)}")
            if not rows:
                raise CheckFailure("store_memory produced no retrievable row")
            contents = [row.get("content") for row in rows]
            if "sovereign phone session token alpha" not in contents:
                raise CheckFailure(f"stored content missing from retrieve: {contents}")
            details["memory_id"] = str(memory_id)
            details["retrieved"] = len(rows)
            details["embedding"] = type(manager.embedding_model).__name__
        finally:
            await manager.shutdown()

    with tempfile.TemporaryDirectory(prefix="thyris_mem_") as tmpdir:
        asyncio.run(_run(tmpdir))


def check_cache_set_get(details: dict[str, object]) -> None:
    """Construct SomnusCache on a tempdir and round-trip a value through disk."""
    with tempfile.TemporaryDirectory(prefix="thyris_cache_") as tmpdir:
        cache = SomnusCache(
            {
                "cache_dir": str(Path(tmpdir) / "runtime_cache"),
                "persistence_enabled": True,
                "max_memory_mb": 16,
                "max_entries": 32,
            },
            memory_manager=None,
        )
        written = cache.set(
            "phone.boot",
            {"vm": "android-13", "ready": True},
            namespace=CacheNamespace.VM,
        )
        print(f"cache set ok={written}")
        if not written:
            raise CheckFailure("SomnusCache.set returned False")
        loaded = cache.get("phone.boot", namespace=CacheNamespace.VM)
        print(f"cache get={loaded}")
        if loaded != {"vm": "android-13", "ready": True}:
            raise CheckFailure(f"cache round-trip mismatch: {loaded}")
        meta_db = Path(tmpdir) / "runtime_cache" / "cache_metadata.db"
        if not meta_db.exists():
            raise CheckFailure("cache metadata sqlite was not created")
        details["cache_get"] = loaded
        details["metadata_db"] = str(meta_db)
        cache.stop_background_cleanup()


def run() -> dict[str, object]:
    """Run Thyris memory checks and persist artifacts."""
    _print_banner("THYRIS MEMORY CONSUMER")
    checks: list[dict[str, object]] = []
    started = time.time()
    passed_count = 0
    failed_count = 0
    runners = (
        ("owners_are_not_usms", check_owners_are_not_usms),
        ("memory_store_retrieve", check_memory_store_retrieve),
        ("cache_set_get", check_cache_set_get),
    )
    for name, fn in runners:
        detail: dict[str, object] = {}
        try:
            fn(detail)
            print(f"PASS {name}")
            checks.append({"name": name, "status": "pass", "detail": detail})
            passed_count += 1
        except (
            CheckFailure,
            AssertionError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
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
        "name": "thyris_memory",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
    }
    if not passed:
        payload["error"] = f"{failed_count} thyris memory checks failed"
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
        f"# Thyris memory run {timestamp}",
        "",
        f"I ran `python test/memory_core/test_memory_core.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required MemoryManager to store and retrieve on a tempdir sqlite/vector",
        "path, and SomnusCache to round-trip a value through its sqlite shelf.",
        "I required USMS to remain a separate class.",
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
        print(f"thyris memory consumer start {timestamp}")
        payload = run()
        print(f"thyris memory consumer status={payload.get('status')}")
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
