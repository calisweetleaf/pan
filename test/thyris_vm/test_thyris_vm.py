"""Direct consumer for Thyris VM owners (supervisor, image manager, phone).

Real tempdir fixtures. No mocks. Does not boot QEMU.
Prints a run report and writes JSON/MD/LOG artifacts.
"""

from __future__ import annotations

import ast
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
from memory.unified_memory_system import UnifiedMemorySystem
from PAN_SDK.PAN_SDK import UnifiedDataPacket
from security.planetary_immune_system import PlanetaryImmuneSystem
from telecom.phone_orchestrator import (
    THYRIS_REQUIRED_HOST_TOOLS,
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
)
import telecom.vm_supervisor as vm_supervisor_module


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


def check_aipc_prompt_unbound(details: dict[str, object]) -> None:
    """Thyris supervisor must not load or require core.prompt_bridge."""
    source_path = Path(vm_supervisor_module.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    prompt_imports: list[str] = []
    prompt_functions: list[str] = []
    supervisor_methods: list[str] = []
    prompt_attrs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "") == "core.prompt_bridge":
            prompt_imports.append(node.module or "")
        if isinstance(node, ast.FunctionDef) and node.name == "_load_prompt_bridge":
            prompt_functions.append(node.name)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "VMSupervisor":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    supervisor_methods.append(item.name)
            for item in ast.walk(node):
                if isinstance(item, ast.Attribute) and item.attr == "_vm_prompt_systems":
                    prompt_attrs.append(item.attr)
    forbidden_methods = {"_initialize_prompt_system", "generate_vm_prompt", "_get_prompt_system"}
    leaked_methods = sorted(forbidden_methods.intersection(supervisor_methods))
    if prompt_imports:
        raise CheckFailure(f"vm_supervisor still imports prompt_bridge: {prompt_imports}")
    if prompt_functions:
        raise CheckFailure(f"AIPC prompt loaders still defined: {prompt_functions}")
    if leaked_methods:
        raise CheckFailure(f"AIPC prompt methods still on VMSupervisor: {leaked_methods}")
    if prompt_attrs:
        raise CheckFailure(f"AIPC prompt state still on VMSupervisor: {prompt_attrs}")
    if hasattr(vm_supervisor_module, "_load_prompt_bridge"):
        raise CheckFailure("_load_prompt_bridge is still exported")
    if hasattr(VMSupervisor, "_initialize_prompt_system"):
        raise CheckFailure("_initialize_prompt_system is still a VMSupervisor method")
    if hasattr(VMSupervisor, "generate_vm_prompt"):
        raise CheckFailure("generate_vm_prompt is still a VMSupervisor method")
    with tempfile.TemporaryDirectory(prefix="thyris_unbound_") as tmpdir:
        supervisor = VMSupervisor(Path(tmpdir) / "vms", {"source": "gate"})
        if hasattr(supervisor, "_vm_prompt_systems"):
            raise CheckFailure("VMSupervisor still holds _vm_prompt_systems")
        print(f"supervisor_file={source_path}")
        print(f"active_vms={len(supervisor.active_vms)}")
        details["supervisor_file"] = str(source_path)
        details["prompt_imports"] = prompt_imports
        details["leaked_methods"] = leaked_methods


def check_usms_erebus_has_no_prompt(details: dict[str, object]) -> None:
    """USMS/Erebus cognition is Ed25519+RSA packets, not prompt_bridge."""
    usms_path = ROOT_DIR / "memory" / "unified_memory_system.py"
    immune_path = ROOT_DIR / "security" / "planetary_immune_system.py"
    if not usms_path.is_file():
        raise CheckFailure(f"USMS owner missing at {usms_path}")
    if not immune_path.is_file():
        raise CheckFailure(f"immune owner missing at {immune_path}")
    usms_text = usms_path.read_text(encoding="utf-8")
    immune_text = immune_path.read_text(encoding="utf-8")
    for label, text in (("usms", usms_text), ("immune", immune_text)):
        if "prompt_bridge" in text or "PromptSystemBridge" in text:
            raise CheckFailure(f"{label} names prompt_bridge; Erebus does not need it")
    if "UnifiedMemorySystem" not in immune_text:
        raise CheckFailure("immune system does not bind UnifiedMemorySystem")
    if "UnifiedDataPacket" not in immune_text:
        raise CheckFailure("immune system does not bind UnifiedDataPacket")
    if "Ed25519" not in immune_text:
        raise CheckFailure("immune system does not document Ed25519 USMS identity")
    print(f"usms_module={UnifiedMemorySystem.__module__}")
    print(f"immune_module={PlanetaryImmuneSystem.__module__}")
    print(f"packet_type={UnifiedDataPacket.__name__}")
    details["usms_module"] = UnifiedMemorySystem.__module__
    details["immune_module"] = PlanetaryImmuneSystem.__module__
    details["packet"] = UnifiedDataPacket.__name__
    details["prompt_bridge_in_usms"] = False
    details["prompt_bridge_in_immune"] = False


def check_telecom_host_tools_contract(details: dict[str, object]) -> None:
    """Thyris fails loud for qemu/adb, not for AIPC prompts."""
    expected = ("qemu-system-x86_64", "qemu-img", "adb")
    if THYRIS_REQUIRED_HOST_TOOLS != expected:
        raise CheckFailure(
            f"host tools {THYRIS_REQUIRED_HOST_TOOLS!r} != telecom contract {expected!r}"
        )
    if any("prompt" in tool.lower() for tool in THYRIS_REQUIRED_HOST_TOOLS):
        raise CheckFailure("prompt tooling leaked into Thyris host-tool contract")
    with tempfile.TemporaryDirectory(prefix="thyris_tools_") as tmpdir:
        orch = ThyrisPhoneOrchestrator(
            vm_storage_path=str(Path(tmpdir) / "phones"),
            android_images_path=str(Path(tmpdir) / "images"),
        )
        try:
            ok, missing = orch._ensure_host_tools()
            print(f"required_host_tools={list(THYRIS_REQUIRED_HOST_TOOLS)}")
            print(f"host_tools_ok={ok} missing={missing}")
            extra = [item for item in missing if item not in THYRIS_REQUIRED_HOST_TOOLS]
            if extra:
                raise CheckFailure(f"host-tool check reported non-telecom tools: {extra}")
            details["required"] = list(THYRIS_REQUIRED_HOST_TOOLS)
            details["ok"] = ok
            details["missing"] = list(missing)
            details["orchestrator"] = type(orch).__name__
        finally:
            orch.pan_registry.persistence.close()
            orch.cache.shutdown()


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
        ("aipc_prompt_unbound", check_aipc_prompt_unbound),
        ("usms_erebus_has_no_prompt", check_usms_erebus_has_no_prompt),
        ("telecom_host_tools_contract", check_telecom_host_tools_contract),
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
        "owners, VMImageManager and VMSupervisor to construct on tempdirs, AIPC",
        "prompt_bridge to be unbound from the Thyris seam, USMS/Erebus to own",
        "cognition without prompt_bridge, and host-tool fail-loud to name qemu/adb.",
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
