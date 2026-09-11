"""PAN SDK project gate.

Direct Python only. Real tempdir/SQLite consumers. Fail loud.
Writes dated JSON and Markdown artifacts under results/.
"""

from __future__ import annotations

import importlib.util
import json
import py_compile
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(1, str(CURRENT_DIR))

from test_pan_persistence import run as run_persistence
from test_pan_manifest import run as run_manifest
from probe_name_registry import run as run_name_registry
from probe_personal_data import run as run_personal_data
from pan_sdk_system_scenario import run_scenario, write_scenario_artifacts


COMPILE_TARGETS = (
    ROOT_DIR / "PAN_SDK" / "PAN_SDK.py",
    ROOT_DIR / "PAN_SDK" / "personal_data.py",
    ROOT_DIR / "PAN_SDK" / "citizen_simulator.py",
    ROOT_DIR / "PAN_SDK" / "sovereign_firewall.py",
    ROOT_DIR / "PAN_SDK" / "__init__.py",
)

SKIPPED_COMPILE = (
    {
        "path": str(ROOT_DIR / "telecom" / "phone_orchestrator.py"),
        "reason": "Thyris vm_supervisor / memory_system owners are not in this repository",
    },
)


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def slice_compile() -> Dict[str, Any]:
    _print_banner("SLICE: py_compile")
    compiled: List[str] = []
    try:
        for path in COMPILE_TARGETS:
            py_compile.compile(str(path), doraise=True)
            print(f"compiled {path.relative_to(ROOT_DIR)}")
            compiled.append(str(path.relative_to(ROOT_DIR)))
        for skipped in SKIPPED_COMPILE:
            print(f"SKIP compile {skipped['path']}: {skipped['reason']}")
        return {
            "name": "compile",
            "passed": True,
            "details": {"compiled": compiled, "skipped": SKIPPED_COMPILE},
        }
    except Exception as exc:
        print(f"FAIL compile: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return {"name": "compile", "passed": False, "error": f"{type(exc).__name__}: {exc}", "details": {"compiled": compiled}}


def slice_import() -> Dict[str, Any]:
    _print_banner("SLICE: import PAN_SDK")
    try:
        import PAN_SDK
        from PAN_SDK import DHTNode, PANNameRegistry, PANPersistenceStore, SovereignIdentity
        details = {
            "package": getattr(PAN_SDK, "__file__", None),
            "has_persist_name": "persist_name" in PANNameRegistry.__dict__,
            "has_store_name": "store_name" in PANPersistenceStore.__dict__,
            "has_get_name": "get_name" in PANPersistenceStore.__dict__,
            "dht_node": DHTNode.__name__,
            "identity": SovereignIdentity.__name__,
        }
        print(json.dumps(details, indent=2))
        if not details["has_persist_name"] or not details["has_store_name"]:
            raise AssertionError("name persistence methods are not on the owning classes")
        spec = importlib.util.find_spec("PAN_SDK.citizen_simulator")
        if spec is None:
            raise AssertionError("PAN_SDK.citizen_simulator is not importable")
        import PAN_SDK.citizen_simulator as citizen_simulator
        print(f"citizen_simulator={citizen_simulator.__file__}")
        details["citizen_simulator"] = citizen_simulator.__file__
        return {"name": "import", "passed": True, "details": details}
    except Exception as exc:
        print(f"FAIL import: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return {"name": "import", "passed": False, "error": f"{type(exc).__name__}: {exc}"}


def slice_scenario() -> Dict[str, Any]:
    _print_banner("SLICE: system scenario")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    try:
        with tempfile.TemporaryDirectory(prefix="pan_sdk_system_") as tmpdir:
            report = run_scenario(Path(tmpdir))
        txt_path, json_path, md_path = write_scenario_artifacts(report, timestamp)
        print(f"scenario artifacts: {txt_path.name}, {json_path.name}, {md_path.name}")
        return {
            "name": "system_scenario",
            "passed": bool(report.get("passed")),
            "details": {
                "comparisons": report.get("comparisons"),
                "operations": report.get("operations"),
                "artifacts": [str(txt_path), str(json_path), str(md_path)],
            },
        }
    except Exception as exc:
        print(f"FAIL system_scenario: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        failed = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        try:
            write_scenario_artifacts(failed, timestamp)
        except Exception:
            traceback.print_exc()
        return {"name": "system_scenario", "passed": False, "error": f"{type(exc).__name__}: {exc}"}


def write_gate_artifacts(slices: List[Dict[str, Any]], timestamp: str, elapsed_s: float) -> Dict[str, Path]:
    results_dir = ROOT_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    passed = all(item.get("passed") for item in slices)
    payload = {
        "gate": "run_pan_gate",
        "timestamp": timestamp,
        "passed": passed,
        "elapsed_seconds": elapsed_s,
        "python": sys.version,
        "slices": slices,
        "skipped": SKIPPED_COMPILE,
    }
    json_path = results_dir / f"pan_gate_{timestamp}.json"
    md_path = results_dir / f"pan_gate_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [
        f"# PAN gate {timestamp}",
        "",
        f"**Result:** {'PASS' if passed else 'FAIL'}",
        f"**Elapsed:** {elapsed_s:.3f}s",
        "",
        "## Slices",
        "",
    ]
    for item in slices:
        status = "PASS" if item.get("passed") else "FAIL"
        lines.append(f"- `{item.get('name')}`: {status}")
        if item.get("error"):
            lines.append(f"  - error: `{item['error']}`")
    lines.extend(
        [
            "",
            "## Skipped",
            "",
        ]
    )
    for skipped in SKIPPED_COMPILE:
        lines.append(f"- `{skipped['path']}`: {skipped['reason']}")
    lines.extend(["", "## JSON", "", f"`{json_path}`", ""])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "md": md_path}


def main() -> int:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    started = time.time()
    slices: List[Dict[str, Any]] = []
    runners: List[Callable[[], Dict[str, Any]]] = [
        slice_compile,
        slice_import,
        run_persistence,
        run_name_registry,
        run_manifest,
        run_personal_data,
        slice_scenario,
    ]
    for runner in runners:
        _print_banner(f"RUNNING {getattr(runner, '__name__', runner)}")
        result = runner()
        slices.append(result)
        print(f"slice {result.get('name')} -> {'PASS' if result.get('passed') else 'FAIL'}")
        if not result.get("passed"):
            # Continue remaining slices so the artifact records the full red set,
            # but the process still exits non-zero.
            continue
    elapsed = time.time() - started
    artifacts = write_gate_artifacts(slices, timestamp, elapsed)
    _print_banner("GATE SUMMARY")
    for item in slices:
        print(f"{item.get('name')}: {'PASS' if item.get('passed') else 'FAIL'}")
        if item.get("error"):
            print(f"  {item['error']}")
    print(f"artifacts: {artifacts['json']}")
    print(f"artifacts: {artifacts['md']}")
    passed = all(item.get("passed") for item in slices)
    print(f"GATE {'PASSED' if passed else 'FAILED'} in {elapsed:.3f}s")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
