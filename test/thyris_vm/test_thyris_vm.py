"""Direct consumer for Thyris VM owners (supervisor, image manager, phone).

Real tempdir fixtures. No mocks. Does not boot QEMU.
Prints a run report and writes JSON/MD/LOG artifacts.
"""

from __future__ import annotations

import asyncio
import importlib
import io
import json
import sys
import tempfile
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from uuid import uuid4

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from memory.memory_core import MemoryManager
from memory.system_cache import SomnusCache
from telecom.phone_orchestrator import (
    CustomNetworkManager as OrchestratorNetwork,
    CustomVMManager as OrchestratorVM,
    ThyrisPhoneOrchestrator,
)
from telecom.vm_image_manager import OSFamily, VMImageManager
from telecom.vm_supervisor import (
    AIVMInstance,
    CustomNetworkManager,
    CustomVMManager,
    ResourceProfile,
    VMState,
    VMSupervisor,
    _load_prompt_bridge,
)


class CheckFailure(Exception):
    """A named Thyris VM check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def check_phone_orchestrator_imports(details: dict[str, object]) -> None:
    """telecom.phone_orchestrator imports without memory_system or dummies."""
    module = importlib.import_module("telecom.phone_orchestrator")
    print(f"phone_orchestrator={module.__file__}")
    if module.MemoryManager is not MemoryManager:
        raise CheckFailure("phone_orchestrator MemoryManager is not memory.memory_core")
    if module.SomnusCache is not SomnusCache:
        raise CheckFailure("phone_orchestrator SomnusCache is not memory.system_cache")
    if module.CustomVMManager is not CustomVMManager:
        raise CheckFailure("CustomVMManager is not the vm_supervisor owner")
    if module.CustomNetworkManager is not CustomNetworkManager:
        raise CheckFailure("CustomNetworkManager is not the vm_supervisor owner")
    details["module"] = module.__file__
    details["thyris_class"] = ThyrisPhoneOrchestrator.__name__
    details["vm_state"] = VMState.CREATING.value


def check_image_manager_constructs(details: dict[str, object]) -> None:
    """VMImageManager constructs against a tempdir and writes metadata."""
    with tempfile.TemporaryDirectory(prefix="thyris_img_") as tmpdir:
        storage = Path(tmpdir) / "images"
        manager = VMImageManager(storage)
        print(f"image storage={manager.storage_path}")
        if not manager.storage_path.is_dir():
            raise CheckFailure("image storage directory was not created")
        if OSFamily.UBUNTU.value != "ubuntu":
            raise CheckFailure("OSFamily.UBUNTU is not ubuntu")
        manager.metadata["probe"] = {"name": "gate-probe", "os_family": OSFamily.ALPINE.value}
        manager._save_metadata()
        if not manager.metadata_file.exists():
            raise CheckFailure("image_metadata.json was not written")
        reloaded = VMImageManager(storage)
        if reloaded.metadata.get("probe", {}).get("name") != "gate-probe":
            raise CheckFailure("image metadata did not round-trip")
        details["metadata_file"] = str(manager.metadata_file)
        details["os_families"] = [item.value for item in OSFamily]


def check_supervisor_constructs(details: dict[str, object]) -> None:
    """VMSupervisor and custom managers construct on a tempdir without QEMU."""
    with tempfile.TemporaryDirectory(prefix="thyris_sup_") as tmpdir:
        storage = Path(tmpdir) / "vms"
        vm_manager = CustomVMManager(storage)
        network = CustomNetworkManager()
        print(f"custom vm storage={vm_manager.storage_path}")
        ip = network.get_vm_ip(uuid4())
        print(f"assigned ip={ip}")
        if not ip or not ip.startswith("192.168.122."):
            raise CheckFailure(f"unexpected user-net IP: {ip}")
        supervisor = VMSupervisor(storage, {"source": "gate"})
        print(f"supervisor vms={len(supervisor.active_vms)}")
        print(f"memory_db={supervisor.memory_manager.metadata_db_path}")
        if not isinstance(supervisor.memory_manager, MemoryManager):
            raise CheckFailure("VMSupervisor did not bind live MemoryManager")
        if not isinstance(supervisor.cache, SomnusCache):
            raise CheckFailure("VMSupervisor did not bind live SomnusCache")
        if not isinstance(supervisor.image_manager, VMImageManager):
            raise CheckFailure("VMSupervisor did not bind live VMImageManager")
        if "idle" not in supervisor.resource_profiles:
            raise CheckFailure("idle ResourceProfile missing")
        idle = supervisor.resource_profiles["idle"]
        if not isinstance(idle, ResourceProfile):
            raise CheckFailure("idle profile is not ResourceProfile")
        profile_json = idle.model_dump()
        print(f"idle profile={profile_json}")
        instance = AIVMInstance(instance_name="gate-probe", vm_disk_path=str(storage / "probe.qcow2"))
        print(f"instance state={instance.vm_state.value}")
        if instance.vm_state != VMState.CREATING:
            raise CheckFailure("new AIVMInstance is not CREATING")
        details["ip"] = ip
        details["memory_db"] = str(supervisor.memory_manager.metadata_db_path)
        details["profiles"] = sorted(supervisor.resource_profiles)
        details["orchestrator_aliases"] = {
            "vm_manager": OrchestratorVM is CustomVMManager,
            "network": OrchestratorNetwork is CustomNetworkManager,
        }


def check_prompt_bridge_fail_loud(details: dict[str, object]) -> None:
    """Missing core.prompt_bridge must raise ImportError, not a dummy prompt."""
    try:
        _load_prompt_bridge()
    except ImportError as exc:
        message = str(exc)
        print(f"prompt_bridge ImportError={message}")
        if "core.prompt_bridge" not in message:
            raise CheckFailure(f"ImportError did not name core.prompt_bridge: {message}")
        details["error"] = message
        return
    raise CheckFailure("core.prompt_bridge imported; expected it to be absent")


def check_prompt_init_fail_loud(details: dict[str, object]) -> None:
    """VMSupervisor._initialize_prompt_system fails loud without a dummy bridge."""

    async def _run(tmpdir: str) -> None:
        supervisor = VMSupervisor(Path(tmpdir) / "vms", {"source": "gate"})
        instance = AIVMInstance(
            instance_name="gate-prompt",
            vm_disk_path=str(Path(tmpdir) / "probe.qcow2"),
        )
        try:
            await supervisor._initialize_prompt_system(instance)
        except ImportError as exc:
            print(f"initialize_prompt ImportError={exc}")
            details["error"] = str(exc)
            return
        raise CheckFailure("prompt init returned a dummy instead of ImportError")

    with tempfile.TemporaryDirectory(prefix="thyris_prompt_") as tmpdir:
        asyncio.run(_run(tmpdir))
    if "error" not in details:
        raise CheckFailure("prompt init did not record an ImportError")


def run() -> dict[str, object]:
    """Run Thyris VM owner checks and persist artifacts."""
    _print_banner("THYRIS VM CONSUMER")
    checks: list[dict[str, object]] = []
    started = time.time()
    passed_count = 0
    failed_count = 0
    runners = (
        ("phone_orchestrator_imports", check_phone_orchestrator_imports),
        ("image_manager_constructs", check_image_manager_constructs),
        ("supervisor_constructs", check_supervisor_constructs),
        ("prompt_bridge_fail_loud", check_prompt_bridge_fail_loud),
        ("prompt_init_fail_loud", check_prompt_init_fail_loud),
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
            ImportError,
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
        "name": "thyris_vm",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
    }
    if not passed:
        payload["error"] = f"{failed_count} thyris vm checks failed"
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
        f"# Thyris VM owners run {timestamp}",
        "",
        f"I ran `python test/thyris_vm/test_thyris_vm.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required phone_orchestrator to import against live memory/ and telecom/",
        "owners, VMImageManager and VMSupervisor to construct on tempdirs, and",
        "core.prompt_bridge to fail loud instead of a dummy prompt class.",
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
        print(f"thyris vm consumer start {timestamp}")
        payload = run()
        print(f"thyris vm consumer status={payload.get('status')}")
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
