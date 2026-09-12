"""Direct consumer for Thyris Android-x86 guest boot.

Uses the landed ISOConverter._create_disk owner for the qcow2, then boots the
official android-x86_64-9.0-r2.iso with qemu-system-x86_64. No mocks. No dummy
boot. JSON+MD+LOG artifacts.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
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

_WINDOWS_QEMU = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "qemu"
if (_WINDOWS_QEMU / "qemu-img.exe").is_file():
    os.environ["PATH"] = str(_WINDOWS_QEMU) + os.pathsep + os.environ.get("PATH", "")

from telecom.phone_orchestrator import (
    ANDROID_X86_9_R2_ISO,
    ANDROID_X86_9_R2_SHA1,
    ISO_BOOTLOADER_MARKERS,
    ThyrisBootError,
    ThyrisPhoneOrchestrator,
    build_android_qemu_argv,
    ensure_windows_qemu_on_path,
    resolve_qemu_system,
    select_qemu_accelerator,
    sha1_file,
)
from telecom.vm_image_manager import ISOConverter, QemuImgError


class CheckFailure(Exception):
    """A named Thyris Android boot check failed."""


def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _android_iso() -> Path:
    """Return the legal Android-x86 ISO or fail loud."""
    iso = ROOT_DIR / "android_images" / ANDROID_X86_9_R2_ISO
    env_iso = os.environ.get("THYRIS_ANDROID_ISO", "").strip()
    if env_iso:
        iso = Path(env_iso)
    if not iso.is_file():
        raise CheckFailure(
            f"Android ISO missing at {iso}. Obtain the official file from "
            "https://www.android-x86.org/download (android-x86_64-9.0-r2.iso)."
        )
    return iso


def check_qemu_system_resolves(details: dict[str, object]) -> None:
    """qemu-system-x86_64 must be a real file."""
    ensure_windows_qemu_on_path()
    qemu_system = resolve_qemu_system()
    print(f"qemu-system-x86_64={qemu_system}")
    if not qemu_system.is_file():
        raise CheckFailure(f"qemu-system-x86_64 is not a file: {qemu_system}")
    accel = list(select_qemu_accelerator())
    print(f"accelerator={accel}")
    details["qemu_system"] = str(qemu_system)
    details["accelerator"] = accel
    if sys.platform == "win32" and accel != ["-accel", "tcg"] and os.environ.get("THYRIS_QEMU_ACCEL", "").strip() == "":
        raise CheckFailure(f"Windows default accelerator is not tcg: {accel}")


def check_android_iso_authentic(details: dict[str, object]) -> None:
    """On-disk ISO must match the official android-x86 9.0-r2 SHA-1."""
    iso = _android_iso()
    digest = sha1_file(iso)
    print(f"iso={iso}")
    print(f"bytes={iso.stat().st_size}")
    print(f"sha1={digest}")
    print(f"expected={ANDROID_X86_9_R2_SHA1}")
    if digest != ANDROID_X86_9_R2_SHA1:
        raise CheckFailure(f"ISO SHA-1 {digest} != official {ANDROID_X86_9_R2_SHA1}")
    if iso.stat().st_size < 100_000_000:
        raise CheckFailure(f"ISO too small to be android-x86_64-9.0-r2: {iso.stat().st_size}")
    details["iso_path"] = str(iso)
    details["iso_bytes"] = iso.stat().st_size
    details["sha1"] = digest


def check_nographic_argv(details: dict[str, object]) -> None:
    """Boot argv must be nographic and must not pass -enable-kvm on Windows."""
    qemu_system = resolve_qemu_system()
    argv = build_android_qemu_argv(
        qemu_system=qemu_system,
        disk_path=Path("disk.qcow2"),
        iso_path=Path("android.iso"),
        name="thyris-argv-probe",
        memory_mb=2048,
        vcpus=2,
        nographic=True,
    )
    print("argv=" + " ".join(argv))
    details["argv"] = argv
    if "-nographic" not in argv:
        raise CheckFailure("boot argv is missing -nographic")
    if sys.platform == "win32" and "-enable-kvm" in argv:
        raise CheckFailure("Windows qemu argv still contains -enable-kvm")


def check_android_installer_boot(details: dict[str, object]) -> None:
    """Create a disk via landed _create_disk, then boot the real ISO."""
    iso = _android_iso()
    with tempfile.TemporaryDirectory(prefix="thyris_boot_") as tmpdir:
        work = Path(tmpdir)
        orch = ThyrisPhoneOrchestrator(
            vm_storage_path=str(work / "phones"),
            android_images_path=str(iso.parent),
        )
        try:
            disk = work / "phone-boot.qcow2"
            created = asyncio.run(ISOConverter()._create_disk(disk, 1))
            if created is not True or not disk.is_file():
                raise CheckFailure("landed ISOConverter._create_disk did not write a qcow2")
            console = work / "console.log"
            stderr_path = work / "qemu.stderr.log"
            print(f"disk={disk} iso={iso}")
            print("starting qemu-system-x86_64 -nographic Android-x86 installer...")
            evidence = asyncio.run(
                orch.boot_android_installer(
                    disk,
                    iso,
                    console,
                    memory_mb=2048,
                    vcpus=2,
                    timeout_seconds=90.0,
                    qemu_stderr_path=stderr_path,
                )
            )
            printable = {key: value for key, value in evidence.items() if key != "argv"}
            print(json.dumps(printable, indent=2, default=str))
            print("argv=" + " ".join(str(item) for item in evidence.get("argv", [])))
            if evidence.get("phone_ready"):
                raise CheckFailure("boot proof claimed phone_ready; ADB userspace was not proven")
            if evidence.get("adb_proven"):
                raise CheckFailure("boot proof claimed adb_proven without an ADB check")
            markers = evidence.get("markers") or []
            if not markers:
                raise CheckFailure("boot returned no markers")
            iso_markers = [
                marker
                for marker in markers
                if str(marker).lower() in {item.lower() for item in ISO_BOOTLOADER_MARKERS}
            ]
            if not iso_markers:
                raise CheckFailure(
                    "boot lacked ISOLINUX/Android-x86; SeaBIOS-only is not Android ISO proof"
                )
            excerpt = str(evidence.get("console_excerpt") or "")
            if not excerpt.strip():
                raise CheckFailure("console excerpt is empty")
            for dummy in ("dummy boot", "simulated qemu", "prompt_bridge"):
                if dummy in excerpt.lower():
                    raise CheckFailure(f"console contains dummy marker {dummy!r}")
            details.update(
                {
                    "pid": evidence.get("pid"),
                    "markers": markers,
                    "iso_bootloader_markers": iso_markers,
                    "iso_bytes": evidence.get("iso_bytes"),
                    "accelerator": evidence.get("accelerator"),
                    "console_excerpt": excerpt[-1500:],
                    "phone_ready": evidence.get("phone_ready"),
                    "adb_proven": evidence.get("adb_proven"),
                    "qemu_system": evidence.get("qemu_system"),
                    "disk_owner": "telecom.vm_image_manager.ISOConverter._create_disk",
                }
            )
        except ThyrisBootError as exc:
            raise CheckFailure(f"Android installer boot failed loud: {exc}") from exc
        finally:
            orch.pan_registry.persistence.close()
            orch.cache.shutdown()


def run() -> dict[str, object]:
    """Run Thyris Android boot checks and persist artifacts."""
    _print_banner("THYRIS ANDROID GUEST BOOT CONSUMER")
    checks: list[dict[str, object]] = []
    started = time.time()
    passed_count = 0
    failed_count = 0
    runners = (
        ("qemu_system_resolves", check_qemu_system_resolves),
        ("android_iso_authentic", check_android_iso_authentic),
        ("nographic_argv", check_nographic_argv),
        ("android_installer_boot", check_android_installer_boot),
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
            QemuImgError,
            ThyrisBootError,
            AssertionError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            ImportError,
            json.JSONDecodeError,
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
        "name": "thyris_android_boot",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
        "claim": (
            "qemu-system-x86_64 -nographic booted official "
            "android-x86_64-9.0-r2.iso far enough for SeaBIOS/ISOLINUX console "
            "evidence. Disk came from landed ISOConverter._create_disk. "
            "This is not PhoneVMState.READY or ADB userspace."
        ),
    }
    if not passed:
        payload["error"] = f"{failed_count} thyris android boot checks failed"
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
        f"# Thyris Android guest boot run {timestamp}",
        "",
        f"I ran `python test/thyris_vm/test_thyris_android_boot.py` at {timestamp}.",
        f"I found status `{payload.get('status')}` with "
        f"{payload.get('pass_count')} passed, {payload.get('fail_count')} failed, "
        f"{payload.get('skip_count')} skipped.",
        "",
        "## What I required",
        "",
        "I required qemu-system-x86_64, the official android-x86_64-9.0-r2.iso",
        "(SHA-1 1cc85b5ed7c830ff71aecf8405c7281a9c995aa0), a qcow2 from landed",
        "ISOConverter._create_disk, and SeaBIOS/ISOLINUX on -nographic stdout.",
        "I refused a dummy boot, prompt_bridge, a second disk-create owner, and",
        "a READY-phone claim.",
        "",
        f"Claim: {payload.get('claim')}",
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
        print(f"thyris android boot consumer start {timestamp}")
        payload = run()
        print(f"thyris android boot consumer status={payload.get('status')}")
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
