"""Direct consumer for Thyris Android-x86 guest boot.

Uses the landed ISOConverter._create_disk owner for the qcow2, then boots the
official android-x86_64-9.0-r2.iso with qemu-system-x86_64. No mocks. No dummy
boot. JSON+MD+LOG artifacts.
"""

from __future__ import annotations

import asyncio
import gzip
import io
import json
import os
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

_WINDOWS_QEMU = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "qemu"
if (_WINDOWS_QEMU / "qemu-img.exe").is_file():
    os.environ["PATH"] = str(_WINDOWS_QEMU) + os.pathsep + os.environ.get("PATH", "")

from telecom.phone_orchestrator import (
    ADB_HEALTH_TOKEN,
    ANDROID_ISOLINUX_DEBUG_APPEND,
    ANDROID_ISOLINUX_LIVE_APPEND,
    ANDROID_LIVE_CMDLINE,
    ANDROID_LIVE_INITRD,
    ANDROID_LIVE_KERNEL,
    ANDROID_AUTO_INSTALL_CMDLINE,
    ANDROID_DISK_BOOT_CMDLINE,
    ANDROID_INSTALL_DISK_GB,
    ANDROID_INSTALL_PREFIX,
    ANDROID_X86_9_R2_ISO,
    ANDROID_X86_9_R2_SHA1,
    AndroidPhoneVM,
    ISO_BOOTLOADER_MARKERS,
    PhoneVMState,
    QEMU_USERNET_GUEST_IP,
    ThyrisAdbError,
    ThyrisBootError,
    ThyrisPhoneOrchestrator,
    WINDOWS_WHPX_ACCEL,
    apply_adb_ready,
    build_android_qemu_argv,
    ensure_windows_qemu_on_path,
    extract_android_live_boot_files,
    require_windows_whpx_accelerator,
    resolve_adb,
    resolve_qemu_system,
    run_android_adb_userspace_boot,
    select_qemu_accelerator,
    sha1_file,
    terminate_stale_adb,
    terminate_stale_thyris_qemu,
    _adb_output_is_offline,
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
    accel = list(require_windows_whpx_accelerator(select_qemu_accelerator()))
    print(f"accelerator={accel}")
    details["qemu_system"] = str(qemu_system)
    details["accelerator"] = accel
    if sys.platform == "win32":
        joined = " ".join(str(part).lower() for part in accel)
        if "whpx" not in joined or "kernel-irqchip=off" not in joined:
            raise CheckFailure(f"Windows accelerator is not WHPX kernel-irqchip=off: {accel}")
        if os.environ.get("THYRIS_QEMU_ACCEL", "").strip() == "" and accel != ["-accel", WINDOWS_WHPX_ACCEL]:
            raise CheckFailure(f"Windows default accelerator is not WHPX: {accel}")
    elif "whpx" in " ".join(str(part).lower() for part in accel):
        raise CheckFailure(f"POSIX accelerator selected WHPX: {accel}")


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
    if "-kernel" in argv:
        raise CheckFailure("installer argv unexpectedly contains -kernel")


def check_adb_resolves(details: dict[str, object]) -> None:
    """Host adb must be a real file. READY cannot be claimed without it."""
    adb = resolve_adb()
    print(f"adb={adb}")
    if not adb.is_file():
        raise CheckFailure(f"adb is not a file: {adb}")
    details["adb"] = str(adb)


def check_extract_live_boot_files(details: dict[str, object]) -> None:
    """Kernel and initrd come from the same official ISO, not a second image."""
    iso = _android_iso()
    with tempfile.TemporaryDirectory(prefix="thyris_liveboot_") as tmpdir:
        kernel, initrd = extract_android_live_boot_files(iso, Path(tmpdir))
        print(f"kernel={kernel} bytes={kernel.stat().st_size}")
        print(f"initrd={initrd} bytes={initrd.stat().st_size}")
        if kernel.name != ANDROID_LIVE_KERNEL:
            raise CheckFailure(f"unexpected kernel name {kernel.name}")
        if initrd.name != ANDROID_LIVE_INITRD:
            raise CheckFailure(f"unexpected initrd name {initrd.name}")
        if kernel.stat().st_size < 1_000_000:
            raise CheckFailure("extracted kernel is too small")
        if initrd.stat().st_size < 100_000:
            raise CheckFailure("extracted initrd is too small")
        init_text = gzip.decompress(initrd.read_bytes()).decode("latin-1", "replace")
        if "service.adb.tcp.port=5555" not in init_text:
            raise CheckFailure("live initrd was not injected with ADB TCP default.prop writes")
        if "persist.sys.usb.config=adb" not in init_text:
            raise CheckFailure("live initrd was not injected with persist.sys.usb.config=adb")
        if "ro.adb.secure=0" not in init_text:
            raise CheckFailure("live initrd was not injected with ro.adb.secure=0")
        if "setprop service.adb.tcp.port" in init_text:
            raise CheckFailure("live initrd still uses serial setprop spam")
        if "setprop persist.sys.usb.config" in init_text:
            raise CheckFailure("live initrd used serial setprop for usb.config")
        details["kernel_bytes"] = kernel.stat().st_size
        details["initrd_bytes"] = initrd.stat().st_size
        details["iso_path"] = str(iso)


def check_live_argv_forwards_adb(details: dict[str, object]) -> None:
    """Live userspace argv must skip vesamenu and forward host ADB to guest 5555."""
    iso = _android_iso()
    qemu_system = resolve_qemu_system()
    with tempfile.TemporaryDirectory(prefix="thyris_liveargv_") as tmpdir:
        work = Path(tmpdir)
        kernel, initrd = extract_android_live_boot_files(iso, work / "boot")
        argv = build_android_qemu_argv(
            qemu_system=qemu_system,
            disk_path=work / "disk.qcow2",
            iso_path=iso,
            name="thyris-live-argv",
            memory_mb=2048,
            vcpus=2,
            nographic=True,
            adb_port=15555,
            kernel_path=kernel,
            initrd_path=initrd,
            kernel_append=ANDROID_LIVE_CMDLINE,
        )
        print("live_argv=" + " ".join(argv))
        details["argv"] = argv
        if "-kernel" not in argv:
            raise CheckFailure("live argv is missing -kernel")
        if "-initrd" not in argv:
            raise CheckFailure("live argv is missing -initrd")
        if ANDROID_LIVE_CMDLINE not in argv:
            raise CheckFailure("live argv is missing isolinux livem/nosetup append")
        if ANDROID_ISOLINUX_LIVE_APPEND not in ANDROID_LIVE_CMDLINE:
            raise CheckFailure("ANDROID_LIVE_CMDLINE drifted off isolinux livem/nosetup")
        if "DEBUG=2" in ANDROID_LIVE_CMDLINE:
            raise CheckFailure("live ADB cmdline still uses DEBUG=2 chroot instead of switch_root")
        if "SETUPWIZARD=0" not in ANDROID_LIVE_CMDLINE or "SRC=" not in ANDROID_LIVE_CMDLINE:
            raise CheckFailure("live cmdline is missing isolinux nosetup SETUPWIZARD=0 SRC=")
        if "nomodeset" not in ANDROID_LIVE_CMDLINE:
            raise CheckFailure("live cmdline is missing isolinux vesa nomodeset")
        if "vga=ask" in ANDROID_LIVE_CMDLINE:
            raise CheckFailure("live cmdline used vga=ask which blocks nographic boot")
        if ANDROID_ISOLINUX_DEBUG_APPEND in ANDROID_LIVE_CMDLINE:
            raise CheckFailure("live cmdline still uses isolinux label debug")
        if "AUTO_INSTALL" in ANDROID_LIVE_CMDLINE:
            raise CheckFailure("live cmdline used AUTO_INSTALL; that is not this unit")
        if "setprop" in ANDROID_LIVE_CMDLINE:
            raise CheckFailure("live cmdline still carries setprop spam")
        argv_text = " ".join(str(item).lower() for item in argv)
        if sys.platform == "win32":
            if WINDOWS_WHPX_ACCEL not in argv_text:
                raise CheckFailure("Windows live argv is missing WHPX kernel-irqchip=off")
            if " -accel tcg" in f" {argv_text} " or argv_text.endswith("-accel tcg"):
                raise CheckFailure("Windows live argv still selected TCG")
        elif "whpx" in argv_text:
            raise CheckFailure("POSIX live argv selected WHPX")
        if "-boot" in argv:
            raise CheckFailure("live argv still uses CDROM -boot order=d")
        if "-nographic" not in argv:
            raise CheckFailure("live argv is missing -nographic; create_phone_vm must match")
        forwarded = [item for item in argv if "hostfwd=tcp::15555-:5555" in item]
        if not forwarded:
            raise CheckFailure("live argv does not forward host 15555 to guest 5555")
        if sys.platform == "win32" and "-enable-kvm" in argv:
            raise CheckFailure("Windows live argv still contains -enable-kvm")


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


def check_android_adb_userspace(details: dict[str, object]) -> None:
    """Install the same ISO to qcow, boot that disk, and demand adb shell."""
    iso = _android_iso()
    work_parent = ROOT_DIR / "thyris-disks"
    tmp_dir = str(work_parent) if work_parent.is_dir() else None
    with tempfile.TemporaryDirectory(prefix="thyris_adb_", dir=tmp_dir) as tmpdir:
        work = Path(tmpdir)
        disk = work / "phone-adb.qcow2"
        created = asyncio.run(ISOConverter()._create_disk(disk, ANDROID_INSTALL_DISK_GB))
        if created is not True or not disk.is_file():
            raise CheckFailure("landed ISOConverter._create_disk did not write a qcow2")
        console = work / "adb-console.log"
        stderr_path = work / "adb-qemu.stderr.log"
        print(f"disk={disk} iso={iso} adb={resolve_adb()}")
        killed = terminate_stale_thyris_qemu()
        killed_adb = terminate_stale_adb()
        print(f"stale_qemu_killed={killed}")
        print(f"stale_adb_killed={killed_adb}")
        print("starting live kernel qemu-system-x86_64 for ADB userspace...")
        try:
            evidence = asyncio.run(
                run_android_adb_userspace_boot(
                    disk,
                    iso,
                    console,
                    memory_mb=2048,
                    vcpus=2,
                    timeout_seconds=1800.0,
                    install_timeout_seconds=900.0,
                    qemu_stderr_path=stderr_path,
                    live_boot_dir=work / "liveboot",
                )
            )
        except ThyrisAdbError as exc:
            raise CheckFailure(f"Android ADB userspace failed loud: {exc}") from exc
        except ThyrisBootError as exc:
            raise CheckFailure(f"Android live boot failed before ADB: {exc}") from exc
        printable = {key: value for key, value in evidence.items() if key != "argv"}
        print(json.dumps(printable, indent=2, default=str))
        print("argv=" + " ".join(str(item) for item in evidence.get("argv", [])))
        if not evidence.get("adb_proven"):
            raise CheckFailure("ADB userspace returned without adb_proven")
        if not evidence.get("phone_ready"):
            raise CheckFailure("ADB userspace returned without phone_ready")
        if evidence.get("vm_state") != PhoneVMState.READY.value:
            raise CheckFailure("ADB proof did not set PhoneVMState.READY")
        probe = AndroidPhoneVM(
            vm_id=uuid4(),
            sovereign_id="thyris-adb-probe",
            instance_name="thyris-adb-probe",
            pan_phone_address="probe",
            vm_state=PhoneVMState.BOOTING,
        )
        apply_adb_ready(probe, str(evidence.get("internal_ip")))
        if probe.vm_state != PhoneVMState.READY:
            raise CheckFailure("apply_adb_ready did not flip AndroidPhoneVM.vm_state to READY")
        if evidence.get("internal_ip") != QEMU_USERNET_GUEST_IP:
            raise CheckFailure("ADB proof used a fabricated libvirt IP")
        if not str(evidence.get("adb_detail") or ""):
            raise CheckFailure("ADB proof omitted connect/shell detail")
        if ADB_HEALTH_TOKEN not in str(evidence.get("guest_response") or "") and ADB_HEALTH_TOKEN not in str(
            evidence.get("adb_detail") or ""
        ):
            raise CheckFailure("ADB proof omitted guest_response thyris_adb_health")
        host_command = str(evidence.get("host_command") or "")
        if "adb" not in host_command or "shell" not in host_command or ADB_HEALTH_TOKEN not in host_command:
            raise CheckFailure("ADB proof omitted host adb shell command")
        if _adb_output_is_offline(str(evidence.get("adb_detail") or "")):
            raise CheckFailure("ADB proof accepted a device-offline transport")
        append = " ".join(str(item) for item in evidence.get("argv") or [])
        install_append = " ".join(str(item) for item in evidence.get("install_argv") or [])
        if "AUTO_INSTALL=force" not in install_append:
            raise CheckFailure("ADB path did not run this ISO's AUTO_INSTALL=force installer")
        if f"INSTALL_PREFIX={ANDROID_INSTALL_PREFIX}" not in install_append:
            raise CheckFailure("AUTO_INSTALL did not pin INSTALL_PREFIX=thyris")
        boot_mode = str(evidence.get("boot_mode") or "")
        if boot_mode == "installed_disk":
            if ANDROID_DISK_BOOT_CMDLINE not in append:
                raise CheckFailure("disk-boot argv is missing SRC=/thyris")
            if "media=cdrom" in append:
                raise CheckFailure("disk-boot still attached live /dev/sr0 ISO")
            if "-nographic" in (evidence.get("argv") or []):
                raise CheckFailure("disk-boot still uses -nographic stdio")
            if "-vga" not in (evidence.get("argv") or []):
                raise CheckFailure("disk-boot argv is missing hidden VGA")
            if "-serial" not in (evidence.get("argv") or []):
                raise CheckFailure("disk-boot argv is missing serial file capture")
            if "-no-reboot" in (evidence.get("argv") or []):
                raise CheckFailure("disk-boot argv still has -no-reboot")
            if "nomodeset" in ANDROID_DISK_BOOT_CMDLINE:
                raise CheckFailure("disk-boot cmdline still uses nomodeset")
        elif boot_mode == "auto_install_run":
            if ANDROID_AUTO_INSTALL_CMDLINE not in append:
                raise CheckFailure("install-run argv lost AUTO_INSTALL=force")
        else:
            raise CheckFailure(f"ADB proof used unknown boot_mode {boot_mode!r}")
        if "DEBUG=2" in append or "DEBUG=2" in install_append:
            raise CheckFailure("ADB guest still used DEBUG=2 chroot")
        if sys.platform == "win32":
            if WINDOWS_WHPX_ACCEL not in append.lower() and WINDOWS_WHPX_ACCEL not in install_append.lower():
                raise CheckFailure("ADB guest was not launched with WHPX kernel-irqchip=off")
        elif "whpx" in append.lower():
            raise CheckFailure("POSIX ADB guest selected WHPX")
        if "setprop" in append or "setprop" in install_append:
            raise CheckFailure("ADB argv still contains setprop")
        details.update(
            {
                "pid": evidence.get("pid"),
                "adb": evidence.get("adb"),
                "adb_port": evidence.get("adb_port"),
                "adb_serial": evidence.get("adb_serial"),
                "android_release": evidence.get("android_release"),
                "userspace_markers": evidence.get("userspace_markers"),
                "kernel_bytes": evidence.get("kernel_bytes"),
                "initrd_bytes": evidence.get("initrd_bytes"),
                "internal_ip": evidence.get("internal_ip"),
                "phone_ready": evidence.get("phone_ready"),
                "adb_proven": evidence.get("adb_proven"),
                "host_command": evidence.get("host_command"),
                "guest_response": evidence.get("guest_response"),
                "vm_state": evidence.get("vm_state"),
                "stale_qemu_killed": evidence.get("stale_qemu_killed"),
                "stale_adb_killed": evidence.get("stale_adb_killed"),
                "accelerator": evidence.get("accelerator"),
                "debug_exits_sent": evidence.get("debug_exits_sent"),
                "install_markers": evidence.get("install_markers"),
                "boot_mode": evidence.get("boot_mode"),
                "console_excerpt": str(evidence.get("console_excerpt") or "")[-1500:],
                "disk_owner": "telecom.vm_image_manager.ISOConverter._create_disk",
            }
        )

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
        ("adb_resolves", check_adb_resolves),
        ("extract_live_boot_files", check_extract_live_boot_files),
        ("live_argv_forwards_adb", check_live_argv_forwards_adb),
        ("android_installer_boot", check_android_installer_boot),
        ("android_adb_userspace", check_android_adb_userspace),
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
            ThyrisAdbError,
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
    adb_check = next(
        (
            item
            for item in checks
            if isinstance(item, dict) and item.get("name") == "android_adb_userspace"
        ),
        {},
    )
    adb_ready = isinstance(adb_check, dict) and adb_check.get("status") == "pass"
    payload: dict[str, object] = {
        "name": "thyris_android_boot",
        "passed": passed,
        "status": "pass" if passed else "fail",
        "pass_count": passed_count,
        "fail_count": failed_count,
        "skip_count": 0,
        "elapsed_seconds": elapsed,
        "checks": checks,
        "phone_ready": adb_ready,
        "adb_proven": adb_ready,
        "claim": (
            "qemu-system-x86_64 live-booted official android-x86_64-9.0-r2.iso "
            "via kernel/initrd extracted from that same ISO. Disk came from "
            "landed ISOConverter._create_disk. PhoneVMState.READY is claimed "
            "only after adb connect + adb shell on the qemu user-net forward."
            if adb_ready
            else
            "Installer ISOLINUX remains a non-READY proof. ADB userspace was "
            "not proven; phone_ready stays false."
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
        "ISOConverter._create_disk, SeaBIOS/ISOLINUX on installer -nographic stdout,",
        "and a disk-install via this ISO's AUTO_INSTALL=force, then a disk boot",
        "with hidden VGA + serial file that only sets phone_ready after adb",
        "connect + adb shell. Windows install still uses",
        "-accel whpx,kernel-irqchip=off. POSIX disk-boot uses KVM or TCG, not",
        "WHPX. I refused a dummy boot, prompt_bridge,",
        "a second disk-create owner, and READY from ISOLINUX.",
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
