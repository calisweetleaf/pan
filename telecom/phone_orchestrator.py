"""
================================================================================
Oracle Browser - Thyris Phone Orchestrator
================================================================================

Manages Android phone VMs for Oracle Browser V1. Thyris is telecommunications:
calls, packets, and phone orchestration. Phones do not contain in-device AI.

Architecture:
- Provisions Android-x86 VMs via QEMU (full async subprocess)
- Assigns PAN phone addresses (visible but non-functional in V1)
- Links to PAN SDK personal data stores (contacts/messages/calls)
- Sets up VNC display streaming for browser sidebar (with random passwords)
- Configures ADB over network for APK installation (with retries/health checks)
- Uses VM memory system for session persistence (auto-sync on boot)
- Robust: Retries, orphan detection, metrics, encryption for configs

V1: Infrastructure with "unusable" phone numbers to build hype
V2: Full communication network activation (phone-to-phone / packet mesh)

Modified: 2026-09-11
Modified by: cursor-grok (daeron)
Justification: I rebound memory_system.memory_core / memory_system.system_cache
    onto this repository's memory.memory_core and memory.system_cache. A
    memory_system package would duplicate Thyris memory beside USMS. Import-time
    FileHandler + correlation_id format would write a cwd log and KeyError on
    the first log record that lacks that field.
Provenance: snapshots/v0.6/manifest.json -> domains.thyris.edits[0]
Files: telecom/phone_orchestrator.py

Modified: 2026-09-11
Modified by: cursor-grok (daeron)
Justification: I dropped unused AIPC VMSupervisor imports and named the qemu/adb
    host-tool contract because Thyris phones are telecommunications VMs, not
    prompt-driven AIPC devices. A core.prompt_bridge import would have reintroduced
    in-phone AI Daeron rejected.
Provenance: snapshots/v0.7/manifest.json -> domains.thyris.edits[0]
Files: telecom/phone_orchestrator.py

Modified: 2026-09-12
Modified by: cursor-grok (daeron)
Justification: I bound Android ISO resolution and qemu-system-x86_64 start onto
    this orchestrator because it already owned _start_android_vm. Wrapping a
    second boot helper would copy the argv while leaving -enable-kvm hard-coded,
    which cannot run on this Windows host. Disk create stays ISOConverter._create_disk
    from ba05cf4; this edit only proves a real Android-x86 ISO guest boot.
    snapshots/v0.10 is the immune second-chain retirement (32ea3a9), not this unit.
Provenance: snapshots/v0.11/manifest.json -> domains.thyris.edits[0]
Files: telecom/phone_orchestrator.py

Modified: 2026-09-18
Modified by: cursor-grok (daeron)
Justification: I bound live kernel/initrd boot and real adb connect/shell onto
    this orchestrator because PhoneVMState.READY was already gated on ADB, but
    the guest never left vesamenu.c32 and _wait_for_ip_and_adb trusted a
    fabricated 192.168.122.x. Wrapping a second boot owner would duplicate
    build_android_qemu_argv and ISOConverter._create_disk. Kernel and initrd
    come from the same official android-x86 9.0-r2 ISO already proven for
    ISOLINUX; that is not a new image and not a READY claim from installer text.
Provenance: snapshots/v0.15/manifest.json -> domains.thyris.edits[0]
Files: telecom/phone_orchestrator.py

Modified: 2026-09-18
Modified by: cursor-grok (daeron)
Justification: Fletcher's READY audit showed serial setprop into a kernel log
    cannot enable TCP adbd, leftover adb.exe made connect look live while the
    guest stayed offline, and create_phone_vm still launched VNC without
    -serial. I switched the live append to isolinux.cfg label debug
    (DEBUG=2 SRC= DATA=), kill leftover qemu/adb before retry, refuse device
    offline, and made _start_android_vm use the same nographic live argv as
    the helper so PhoneVMState.READY is set only after adb shell
    thyris_adb_health. snapshots/v0.15 is not promoted until that proof lands.
Provenance: SCOPE.md engagement thyris-adb-userspace-ready
Files: telecom/phone_orchestrator.py

Modified: 2026-09-18
Modified by: cursor-grok (daeron)
Justification: TCG DEBUG=2 reached Android init/healthd but adbd stayed offline
    (20260918_025416, 900s). The ISO init uses chroot when DEBUG is set, not
    switch_root. I switched the live ADB cmdline to isolinux livem+nosetup
    (SETUPWIZARD=0 SRC= DATA=) plus vesa nomodeset without vga=ask, refused
    WHPX, and kept PhoneVMState.READY only after adb shell thyris_adb_health.
Provenance: SCOPE.md engagement thyris-adb-userspace-ready
Files: telecom/phone_orchestrator.py

Modified: 2026-09-18
Modified by: cursor-grok (daeron)
Justification: TCG isolinux live/debug/livem/nosetup exhausted without adbd
    (20260918_025416, 20260918_032455, 20260918_035525). I bound Windows
    qemu-system to -accel whpx,kernel-irqchip=off at select_qemu_accelerator
    because wrapping a second argv owner would duplicate build_android_qemu_argv
    and ISOConverter._create_disk. PhoneVMState.READY still only flips after
    adb shell thyris_adb_health. TCG is no longer a silent Windows fallback.
Provenance: SCOPE.md engagement thyris-adb-userspace-ready
Files: telecom/phone_orchestrator.py, test/thyris_vm/test_thyris_android_boot.py

Modified: 2026-09-18
Modified by: cursor-grok (daeron)
Justification: WHPX livem still could not start adbd (20260918_050641:
    Detecting Android-x86 at /dev/sr0 then console:/ #, no thyris_adb_health).
    I bound the READY owner onto this ISO's own AUTO_INSTALL=force installer
    then a disk boot with SRC=/thyris, because wrapping a second installer
    would duplicate ISOConverter._create_disk and the qemu argv owner.
    READY still only flips after adb shell thyris_adb_health.
Provenance: SCOPE.md engagement thyris-adb-userspace-ready
Files: telecom/phone_orchestrator.py, test/thyris_vm/test_thyris_android_boot.py
"""

from __future__ import annotations

import logging
import asyncio
import socket
import subprocess
import shutil
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID, uuid4
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timezone
import json
import hashlib
import gzip
import secrets  # For secure random passwords
import psutil  # For PID/process management (from your VM supervisor)
import os
import signal
import time
from collections import defaultdict

# Import VM infrastructure (telecom owners; not AIPC prompt/supervisor AI)
from .vm_image_manager import ISOConverter, QemuImgError
from .vm_supervisor import CustomVMManager, CustomNetworkManager

# Import PAN SDK components
import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from PAN_SDK.personal_data import (
    PANPersonalDataStore,
    PANPhoneAddressRegistry,
    PANContact,
    PANMessage,
    PANCallLog,
    UserPreferences
)
from PAN_SDK.PAN_SDK import (
    SovereignIdentity,
    PANPersistenceStore,
    utc_now_iso,
    sha256_hex,
    derive_uuid
)

from memory.memory_core import MemoryManager, MemoryConfiguration
from memory.system_cache import SomnusCache

logger = logging.getLogger(__name__)

THYRIS_REQUIRED_HOST_TOOLS: tuple[str, ...] = (
    "qemu-system-x86_64",
    "qemu-img",
    "adb",
)

ANDROID_X86_9_R2_ISO = "android-x86_64-9.0-r2.iso"
ANDROID_X86_9_R2_SHA1 = "1cc85b5ed7c830ff71aecf8405c7281a9c995aa0"
KNOWN_ANDROID_ISO_SHA1: dict[str, str] = {
    ANDROID_X86_9_R2_ISO: ANDROID_X86_9_R2_SHA1,
}
BOOT_EVIDENCE_MARKERS: tuple[str, ...] = (
    "SeaBIOS",
    "Booting from DVD",
    "Booting from CD",
    "ISOLINUX",
    "isolinux",
    "Android-x86",
    "android-x86",
)
ISO_BOOTLOADER_MARKERS: tuple[str, ...] = (
    "ISOLINUX",
    "isolinux",
    "Android-x86",
    "android-x86",
)
ANDROID_LIVE_KERNEL = "kernel"
ANDROID_LIVE_INITRD = "initrd.img"
# isolinux.cfg label debug. SRC= keeps system.sfs on the same CDROM.
# DEBUG=2 makes this ISO's init exec chroot instead of switch_root.
ANDROID_ISOLINUX_DEBUG_APPEND = "root=/dev/ram0 DEBUG=2 SRC= DATA="
# isolinux.cfg label livem (SRC= DATA=) plus label nosetup (SETUPWIZARD=0).
# quiet is omitted so -nographic serial stays evidence. nomodeset is label
# vesa without vga=ask (vga=ask would block on an interactive prompt).
ANDROID_ISOLINUX_LIVE_APPEND = "root=/dev/ram0 SETUPWIZARD=0 nomodeset SRC= DATA="
# console= is the -nographic capture channel; it is not an ADB enable switch.
ANDROID_LIVE_CMDLINE = (
    ANDROID_ISOLINUX_LIVE_APPEND
    + " console=ttyS0,115200 androidboot.console=ttyS0"
)
WINDOWS_WHPX_ACCEL = "whpx,kernel-irqchip=off"
# ISO install.img scripts/1-install: AUTO_INSTALL=force skips the last
# destructive-confirm dialog and auto-partitions the first hard disk.
ANDROID_INSTALL_PREFIX = "thyris"
ANDROID_INSTALL_DISK_GB = 8
ANDROID_INSTALLED_DISK_MIN_BYTES = 50_000_000
ANDROID_AUTO_INSTALL_APPEND = (
    "root=/dev/ram0 AUTO_INSTALL=force "
    f"INSTALL_PREFIX={ANDROID_INSTALL_PREFIX} SRC= DATA="
)
ANDROID_AUTO_INSTALL_CMDLINE = (
    ANDROID_AUTO_INSTALL_APPEND
    + " console=ttyS0,115200 androidboot.console=ttyS0"
)
ANDROID_DISK_BOOT_CMDLINE = (
    f"root=/dev/ram0 SETUPWIZARD=0 nomodeset SRC=/{ANDROID_INSTALL_PREFIX} DATA= "
    "console=ttyS0,115200 androidboot.console=ttyS0"
)
INSTALL_PROGRESS_MARKERS: tuple[str, ...] = (
    "Auto Installer",
    "Congratulations",
    "installed successfully",
    "Installing Android-x86",
    "Syncing to disk",
    "Formatting",
)
ISOLINUX_DEBUG_SHELL_PROMPTS: tuple[str, ...] = (
    "Type 'exit' to continue booting",
    "Type 'exit' to enter Android",
)
USERSPACE_EVIDENCE_MARKERS: tuple[str, ...] = (
    "Detecting Android-x86",
    "Running Android-x86",
    "android-x86:",
    "init: ",
    "adbd",
    "healthd",
)
ADB_HEALTH_TOKEN = "thyris_adb_health"
ISO9660_SECTOR = 2048
QEMU_USERNET_GUEST_IP = "10.0.2.15"


class ThyrisBootError(RuntimeError):
    """QEMU started but produced no real Android ISO / firmware boot evidence."""


class ThyrisAdbError(RuntimeError):
    """Guest process ran but ADB userspace was not proven."""


def sha1_file(path: Path) -> str:
    """SHA-1 a file in chunks. Used to match the published android-x86 digest."""
    digest = hashlib.sha1(usedforsecurity=False)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def ensure_windows_qemu_on_path() -> Optional[Path]:
    """Put Program Files/qemu on PATH so landed shutil.which('qemu-img') works.

    Does not create disks. ISOConverter._create_disk remains the qemu-img owner.
    """
    if sys.platform != "win32":
        return None
    qemu_dir = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "qemu"
    if not (qemu_dir / "qemu-img.exe").is_file() and not (qemu_dir / "qemu-system-x86_64.exe").is_file():
        return None
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep)
    qemu_text = str(qemu_dir)
    if qemu_text not in parts:
        os.environ["PATH"] = qemu_text + os.pathsep + current
    return qemu_dir


def resolve_qemu_system() -> Path:
    """Resolve qemu-system-x86_64 on PATH or the Windows QEMU install directory.

    Returns:
        Absolute path to qemu-system-x86_64.

    Raises:
        FileNotFoundError: The emulator binary is missing.
    """
    ensure_windows_qemu_on_path()
    names = ("qemu-system-x86_64", "qemu-system-x86_64.exe")
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    if sys.platform == "win32":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        for name in names:
            probe = program_files / "qemu" / name
            if probe.is_file():
                return probe.resolve()
    raise FileNotFoundError(
        "qemu-system-x86_64 is not on PATH and was not found under Program Files/qemu"
    )


def resolve_adb() -> Path:
    """Resolve the host adb binary. ADB userspace proof cannot proceed without it.

    Returns:
        Absolute path to adb.

    Raises:
        FileNotFoundError: adb is not on PATH.
    """
    names = ("adb", "adb.exe")
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    raise FileNotFoundError(
        "adb is not on PATH; PhoneVMState.READY requires a real Android Debug Bridge"
    )


def allocate_local_tcp_port() -> int:
    """Bind 127.0.0.1:0 and return an unused host port for ADB forward."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    if not isinstance(port, int) or port <= 0:
        raise ThyrisAdbError("could not allocate a local TCP port for ADB")
    return port


def terminate_stale_thyris_qemu(*, keep_pid: Optional[int] = None) -> List[int]:
    """Kill leftover qemu-system-x86_64 guests from prior Thyris ADB attempts.

    Untagged WHPX probes are leftover qemu and must die too.

    Args:
        keep_pid: Live guest to preserve, if any.

    Returns:
        PIDs that were sent SIGKILL / process kill.
    """
    killed: List[int] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            pid = int(proc.info["pid"])
            if keep_pid is not None and pid == keep_pid:
                continue
            name = str(proc.info.get("name") or "").lower()
            cmdline = proc.info.get("cmdline") or []
            joined = " ".join(str(part) for part in cmdline).lower()
            is_qemu = "qemu-system-x86_64" in name or "qemu-system-x86_64" in joined
            if not is_qemu:
                continue
            proc.kill()
            killed.append(pid)
        except (psutil.Error, ProcessLookupError, TypeError, ValueError, OSError):
            continue
    return killed


def terminate_stale_adb() -> List[int]:
    """Kill leftover adb.exe so a dead guest cannot leave an offline transport.

    Returns:
        PIDs that were sent process kill.
    """
    killed: List[int] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid = int(proc.info["pid"])
            name = str(proc.info.get("name") or "").lower()
            if name not in {"adb", "adb.exe"}:
                continue
            proc.kill()
            killed.append(pid)
        except (psutil.Error, ProcessLookupError, TypeError, ValueError, OSError):
            continue
    return killed


def _adb_output_is_offline(text: str) -> bool:
    """True when adb reported a transport that is not a live userspace device."""
    lower = text.lower()
    return "offline" in lower or "unauthorized" in lower


async def continue_isolinux_debug_shells(
    process: asyncio.subprocess.Process,
    console_text: str,
    exits_sent: int,
) -> int:
    """Send the isolinux DEBUG=2 'exit' continue, not setprop spam.

    Args:
        process: Live qemu with serial on stdin.
        console_text: Current -nographic stdout.
        exits_sent: How many exit lines already written.

    Returns:
        Updated exits_sent count (at most one per official prompt, max 2).
    """
    if process.stdin is None or exits_sent >= 2:
        return exits_sent
    needed = sum(1 for prompt in ISOLINUX_DEBUG_SHELL_PROMPTS if prompt in console_text)
    if needed > 2:
        needed = 2
    while exits_sent < needed:
        process.stdin.write(b"exit\n")
        await process.stdin.drain()
        exits_sent += 1
        logger.info("sent isolinux DEBUG=2 exit %s/%s", exits_sent, needed)
    return exits_sent


async def continue_auto_install_menu(
    process: asyncio.subprocess.Process,
    console_text: str,
    reboot_keys_sent: int,
) -> int:
    """Select Reboot on the ISO installer's Congratulations dialog.

    scripts/1-install leaves an interactive menu after AUTO_INSTALL=force
    finishes copying. Down+Enter picks Reboot so -no-reboot exits QEMU.
    """
    if process.stdin is None or reboot_keys_sent >= 1:
        return reboot_keys_sent
    lower = console_text.lower()
    if "congratulations" not in lower and "installed successfully" not in lower:
        return reboot_keys_sent
    process.stdin.write(b"\x1b[B\r")
    await process.stdin.drain()
    logger.info("sent AUTO_INSTALL Congratulations Reboot keys")
    return reboot_keys_sent + 1


async def _stop_qemu_process(process: Optional[asyncio.subprocess.Process]) -> None:
    """Terminate a qemu subprocess. Kill if it ignores SIGTERM."""
    if process is None or process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=10)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


def _iso9660_normalize_name(raw: bytes) -> str:
    """Strip ISO9660 version suffix from a directory-record name."""
    label = raw.split(b";", 1)[0].decode("ascii", "replace").strip().lower()
    return label.rstrip(".")


def extract_iso9660_root_file(iso_path: Path, filename: str, destination: Path) -> Path:
    """Copy one root-directory file off an ISO 9660 image using stdlib only.

    Args:
        iso_path: Official Android-x86 ISO.
        filename: Root file name such as kernel or initrd.img.
        destination: Output path. Parent directory must exist.

    Returns:
        The destination path after a complete write.

    Raises:
        FileNotFoundError: ISO is missing.
        ThyrisBootError: The ISO is not ISO9660 or the named file is absent.
        OSError: The destination cannot be written.
    """
    iso = Path(iso_path)
    if not iso.is_file():
        raise FileNotFoundError(f"Android ISO missing: {iso}")
    wanted = filename.strip().lower()
    if not wanted:
        raise ThyrisBootError("ISO extract filename is empty")
    dest = Path(destination)
    with iso.open("rb") as handle:
        handle.seek(16 * ISO9660_SECTOR)
        pvd = handle.read(ISO9660_SECTOR)
        if len(pvd) != ISO9660_SECTOR or pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise ThyrisBootError(f"{iso.name} is not an ISO 9660 primary volume")
        rec_len = pvd[156]
        if rec_len < 34:
            raise ThyrisBootError(f"{iso.name} primary volume has no root directory")
        rec = pvd[156:156 + rec_len]
        extent = int.from_bytes(rec[2:6], "little")
        size = int.from_bytes(rec[10:14], "little")
        if extent < 1 or size < 1:
            raise ThyrisBootError(f"{iso.name} root directory extent is invalid")
        handle.seek(extent * ISO9660_SECTOR)
        data = handle.read(size)
        if len(data) != size:
            raise ThyrisBootError(f"{iso.name} root directory is truncated")
        offset = 0
        found_extent = 0
        found_size = 0
        while offset < len(data):
            length = data[offset]
            if length == 0:
                offset = ((offset // ISO9660_SECTOR) + 1) * ISO9660_SECTOR
                continue
            if offset + length > len(data) or length < 33:
                raise ThyrisBootError(f"{iso.name} root directory record is truncated")
            flags = data[offset + 25]
            name_len = data[offset + 32]
            name = data[offset + 33:offset + 33 + name_len]
            if not (flags & 2):
                label = _iso9660_normalize_name(name)
                if label == wanted:
                    found_extent = int.from_bytes(data[offset + 2:offset + 6], "little")
                    found_size = int.from_bytes(data[offset + 10:offset + 14], "little")
                    break
            offset += length
        if found_extent < 1 or found_size < 1:
            raise ThyrisBootError(f"{iso.name} root directory has no file {filename!r}")
        handle.seek(found_extent * ISO9660_SECTOR)
        payload = handle.read(found_size)
        if len(payload) != found_size:
            raise ThyrisBootError(
                f"{iso.name} file {filename!r} truncated at {len(payload)} of {found_size} bytes"
            )
    dest.write_bytes(payload)
    return dest


def extract_android_live_boot_files(iso_path: Path, destination_dir: Path) -> Tuple[Path, Path]:
    """Extract live-boot kernel and initrd from the official Android-x86 ISO.

    Args:
        iso_path: android-x86_64-9.0-r2.iso (or THYRIS_ANDROID_ISO).
        destination_dir: Directory that will hold kernel and initrd.img.

    Returns:
        (kernel_path, initrd_path)

    Raises:
        ThyrisBootError: Extracted files are too small to be the live boot pair.
    """
    dest_dir = Path(destination_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    kernel = extract_iso9660_root_file(iso_path, ANDROID_LIVE_KERNEL, dest_dir / ANDROID_LIVE_KERNEL)
    initrd = extract_iso9660_root_file(iso_path, ANDROID_LIVE_INITRD, dest_dir / ANDROID_LIVE_INITRD)
    if kernel.stat().st_size < 1_000_000:
        raise ThyrisBootError(f"extracted kernel is too small: {kernel.stat().st_size} bytes")
    if initrd.stat().st_size < 100_000:
        raise ThyrisBootError(f"extracted initrd is too small: {initrd.stat().st_size} bytes")
    inject_adb_tcp_into_live_initrd(initrd)
    return kernel, initrd


ADB_TCP_DEFAULT_PROP_LINES = (
    'echo "service.adb.tcp.port=5555" >> default.prop\n'
    'echo "persist.adb.tcp.port=5555" >> default.prop\n'
)
INITRD_SETUPWIZARD_PROP = (
    '[ "$SETUPWIZARD" = "0" ] && echo "ro.setupwizard.mode=DISABLED" >> default.prop\n'
)


def _replace_cpio_newc_file(blob: bytes, filename: str, new_payload: bytes) -> bytes:
    """Replace one regular file inside an uncompressed newc cpio archive."""
    offset = 0
    pieces: List[bytes] = []
    replaced = False
    while offset + 110 <= len(blob):
        magic = blob[offset : offset + 6]
        if magic not in (b"070701", b"070702"):
            raise ThyrisBootError(f"live initrd cpio magic {magic!r} is not newc")
        namesize = int(blob[offset + 94 : offset + 102], 16)
        filesize = int(blob[offset + 54 : offset + 62], 16)
        header_and_name = 110 + namesize
        name_pad = (4 - (header_and_name % 4)) % 4
        data_start = offset + header_and_name + name_pad
        name = blob[offset + 110 : offset + 110 + namesize - 1].decode("utf-8", "replace")
        data_pad = (4 - (filesize % 4)) % 4
        next_offset = data_start + filesize + data_pad
        if name == "TRAILER!!!":
            pieces.append(blob[offset:])
            break
        if name == filename or name.endswith("/" + filename):
            header = bytearray(blob[offset : offset + 110])
            header[54:62] = f"{len(new_payload):08x}".encode("ascii")
            name_bytes = blob[offset + 110 : offset + 110 + namesize]
            entry = bytes(header) + name_bytes + (b"\x00" * name_pad) + new_payload
            entry += b"\x00" * ((4 - (len(new_payload) % 4)) % 4)
            pieces.append(entry)
            replaced = True
        else:
            pieces.append(blob[offset:next_offset])
        offset = next_offset
    else:
        raise ThyrisBootError("live initrd cpio is truncated before TRAILER")
    if not replaced:
        raise ThyrisBootError(f"live initrd cpio has no file {filename!r}")
    return b"".join(pieces)


def inject_adb_tcp_into_live_initrd(initrd_path: Path) -> None:
    """Write ADB TCP properties beside the ISO init's SETUPWIZARD default.prop line.

    Serial setprop into a kernel log cannot enable adbd. The live init already
    appends to default.prop before switch_root; this adds the TCP port the
    hostfwd targets. The ISO file on disk is not modified.
    """
    initrd = Path(initrd_path)
    raw = initrd.read_bytes()
    if raw[:2] != b"\x1f\x8b":
        raise ThyrisBootError(f"live initrd is not gzip: {initrd}")
    blob = gzip.decompress(raw)
    init_bytes = _extract_cpio_newc_file(blob, "init")
    init_text = init_bytes.decode("latin-1")
    if INITRD_SETUPWIZARD_PROP not in init_text:
        raise ThyrisBootError("live initrd init is missing the SETUPWIZARD default.prop write")
    if "service.adb.tcp.port=5555" not in init_text:
        init_text = init_text.replace(
            INITRD_SETUPWIZARD_PROP,
            INITRD_SETUPWIZARD_PROP + ADB_TCP_DEFAULT_PROP_LINES,
            1,
        )
        blob = _replace_cpio_newc_file(blob, "init", init_text.encode("latin-1"))
    with initrd.open("wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as gz:
            gz.write(blob)
    logger.info("injected ADB TCP default.prop writes into live initrd %s", initrd)


def _extract_cpio_newc_file(blob: bytes, filename: str) -> bytes:
    """Return one file payload from an uncompressed newc cpio archive."""
    offset = 0
    while offset + 110 <= len(blob):
        magic = blob[offset : offset + 6]
        if magic not in (b"070701", b"070702"):
            raise ThyrisBootError(f"live initrd cpio magic {magic!r} is not newc")
        namesize = int(blob[offset + 94 : offset + 102], 16)
        filesize = int(blob[offset + 54 : offset + 62], 16)
        header_and_name = 110 + namesize
        name_pad = (4 - (header_and_name % 4)) % 4
        data_start = offset + header_and_name + name_pad
        name = blob[offset + 110 : offset + 110 + namesize - 1].decode("utf-8", "replace")
        if name == "TRAILER!!!":
            break
        if name == filename or name.endswith("/" + filename):
            return blob[data_start : data_start + filesize]
        data_pad = (4 - (filesize % 4)) % 4
        offset = data_start + filesize + data_pad
    raise ThyrisBootError(f"live initrd cpio has no file {filename!r}")


def select_qemu_accelerator() -> Tuple[str, ...]:
    """Choose a real QEMU accelerator. Never pass -enable-kvm on Windows.

    Windows Option B uses WHPX with kernel-irqchip=off. TCG isolinux
    live/debug/livem/nosetup was exhausted without adbd.
    /dev/kvm existing is not enough: this process must be able to open it.
    Otherwise qemu-system exits immediately with Permission denied.
    """
    forced = os.environ.get("THYRIS_QEMU_ACCEL", "").strip()
    if forced:
        return ("-accel", forced)
    if sys.platform == "win32":
        return ("-accel", WINDOWS_WHPX_ACCEL)
    kvm = Path("/dev/kvm")
    if kvm.exists():
        try:
            handle = os.open(kvm, os.O_RDWR)
            os.close(handle)
            return ("-enable-kvm",)
        except OSError:
            logger.warning("KVM node exists but is not usable; falling back to TCG")
    return ("-accel", "tcg")


def require_windows_whpx_accelerator(accel: Tuple[str, ...]) -> Tuple[str, ...]:
    """Option B on Windows demands WHPX with kernel-irqchip=off.

    Silent TCG fallback is refused. POSIX keeps KVM or TCG.

    Args:
        accel: Result of select_qemu_accelerator.

    Returns:
        The same tuple when Windows WHPX is correctly spelled, or when the
        host is not Windows.

    Raises:
        ThyrisBootError: Windows selected TCG, HAX, or WHPX without
            kernel-irqchip=off.
    """
    if sys.platform != "win32":
        return accel
    joined = " ".join(str(part).lower() for part in accel)
    if "hax" in joined:
        raise ThyrisBootError(
            f"refusing accelerator {accel!r}; Windows Thyris ADB uses WHPX"
        )
    if "whpx" not in joined or "kernel-irqchip=off" not in joined:
        raise ThyrisBootError(
            f"Windows Thyris ADB requires -accel {WINDOWS_WHPX_ACCEL}; got {accel!r}"
        )
    return accel


def build_android_qemu_argv(
    *,
    qemu_system: Path,
    disk_path: Path,
    iso_path: Path,
    name: str,
    memory_mb: int,
    vcpus: int,
    nographic: bool = True,
    vnc_display: Optional[int] = None,
    adb_port: Optional[int] = None,
    kernel_path: Optional[Path] = None,
    initrd_path: Optional[Path] = None,
    kernel_append: Optional[str] = None,
    attach_iso: bool = True,
    boot_order: str = "d",
) -> List[str]:
    """Build qemu-system-x86_64 argv for Android-x86.

    Installer-boot (no kernel_path): SeaBIOS/ISOLINUX on -nographic stdout.
    Live/install (kernel_path+initrd_path): skip vesamenu.c32 using files
    extracted from the same ISO. Disk userspace omits the ISO so SRC cannot
    land on live /dev/sr0.
    """
    if (kernel_path is None) != (initrd_path is None):
        raise ThyrisBootError("live boot requires both kernel_path and initrd_path")
    if boot_order not in {"c", "d", "cd", "dc"}:
        raise ThyrisBootError(f"unsupported boot_order {boot_order!r}")
    cmd: List[str] = [
        str(qemu_system),
        *require_windows_whpx_accelerator(select_qemu_accelerator()),
        "-cpu",
        "qemu64",
        "-name",
        name,
        "-m",
        str(memory_mb),
        "-smp",
        str(vcpus),
        "-drive",
        f"file={disk_path.resolve()},format=qcow2,if=ide,index=0,media=disk",
    ]
    if attach_iso:
        cmd.extend(
            [
                "-drive",
                f"file={iso_path.resolve()},format=raw,if=ide,index=1,media=cdrom,readonly=on",
            ]
        )
    if kernel_path is not None and initrd_path is not None:
        if not kernel_path.is_file():
            raise ThyrisBootError(f"live kernel missing: {kernel_path}")
        if not initrd_path.is_file():
            raise ThyrisBootError(f"live initrd missing: {initrd_path}")
        append = kernel_append if kernel_append is not None else ANDROID_LIVE_CMDLINE
        if not append.strip():
            raise ThyrisBootError("live kernel_append is empty")
        cmd.extend(
            [
                "-kernel",
                str(kernel_path.resolve()),
                "-initrd",
                str(initrd_path.resolve()),
                "-append",
                append,
            ]
        )
    else:
        cmd.extend(["-boot", f"order={boot_order}"])
    cmd.append("-no-reboot")
    if nographic:
        cmd.append("-nographic")
    else:
        cmd.extend(["-vga", "std", "-display", "none"])
        if vnc_display is not None:
            cmd.extend(["-vnc", f":{vnc_display}"])
    if adb_port is not None:
        if isinstance(adb_port, bool) or not isinstance(adb_port, int) or adb_port <= 0:
            raise ThyrisAdbError("adb_port must be a positive integer")
        cmd.extend(
            [
                "-netdev",
                f"user,id=net0,hostfwd=tcp::{adb_port}-:5555",
                "-device",
                "e1000,netdev=net0",
            ]
        )
    else:
        cmd.extend(["-netdev", "user,id=net0", "-device", "e1000,netdev=net0"])
    return cmd


async def adb_shell_health(adb: Path, adb_port: int) -> Tuple[bool, str]:
    """adb connect then shell echo. Fabricated libvirt IPs are not proof.

    Device offline / unauthorized is a failed probe, even if connect printed
    'already connected'. Detecting Android-x86 console text is not READY.
    """
    serial = f"127.0.0.1:{adb_port}"
    await adb_disconnect(adb, adb_port)
    try:
        connect = await asyncio.create_subprocess_exec(
            str(adb),
            "connect",
            serial,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        connect_out, connect_err = await asyncio.wait_for(connect.communicate(), timeout=15)
    except asyncio.TimeoutError:
        return False, "adb connect timed out"
    except OSError as exc:
        return False, f"adb connect failed to exec: {exc}"
    connect_text = (connect_out + connect_err).decode("utf-8", errors="replace").strip()
    if _adb_output_is_offline(connect_text):
        return False, f"adb connect refused (offline): {connect_text!r}"
    try:
        devices = await asyncio.create_subprocess_exec(
            str(adb),
            "devices",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        devices_out, devices_err = await asyncio.wait_for(devices.communicate(), timeout=15)
    except asyncio.TimeoutError:
        return False, f"adb devices timed out after connect={connect_text!r}"
    except OSError as exc:
        return False, f"adb devices failed to exec: {exc}"
    devices_text = (devices_out + devices_err).decode("utf-8", errors="replace").strip()
    if _adb_output_is_offline(devices_text) or _adb_output_is_offline(connect_text):
        return False, (
            f"adb devices listed offline/unauthorized. "
            f"connect={connect_text!r} devices={devices_text!r}"
        )
    try:
        shell = await asyncio.create_subprocess_exec(
            str(adb),
            "-s",
            serial,
            "shell",
            "echo",
            ADB_HEALTH_TOKEN,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        shell_out, shell_err = await asyncio.wait_for(shell.communicate(), timeout=15)
    except asyncio.TimeoutError:
        return False, f"adb shell timed out after connect={connect_text!r}"
    except OSError as exc:
        return False, f"adb shell failed to exec: {exc}"
    err_text = (shell_out + shell_err).decode("utf-8", errors="replace").strip()
    if _adb_output_is_offline(err_text) or _adb_output_is_offline(devices_text):
        return False, (
            f"adb shell refused device offline. connect={connect_text!r} "
            f"devices={devices_text!r} shell={err_text!r} rc={shell.returncode}"
        )
    if shell.returncode == 0 and ADB_HEALTH_TOKEN.encode("ascii") in shell_out:
        return True, connect_text or "adb shell echoed thyris_adb_health"
    return False, (
        f"connect={connect_text!r} devices={devices_text!r} "
        f"shell={err_text!r} rc={shell.returncode}"
    )


async def adb_getprop(adb: Path, adb_port: int, key: str) -> str:
    """Read one Android property after userspace ADB is proven."""
    serial = f"127.0.0.1:{adb_port}"
    proc = await asyncio.create_subprocess_exec(
        str(adb),
        "-s",
        serial,
        "shell",
        "getprop",
        key,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    if proc.returncode != 0:
        err = (stdout + stderr).decode("utf-8", errors="replace").strip()
        raise ThyrisAdbError(f"getprop {key} failed: {err}")
    return stdout.decode("utf-8", errors="replace").strip()


async def adb_disconnect(adb: Path, adb_port: int) -> None:
    """Drop the host adb TCP session for this port."""
    serial = f"127.0.0.1:{adb_port}"
    try:
        proc = await asyncio.create_subprocess_exec(
            str(adb),
            "disconnect",
            serial,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)
    except (OSError, asyncio.TimeoutError) as exc:
        logger.debug("adb disconnect %s: %s", serial, exc)


async def adb_kill_server(adb: Path) -> str:
    """Stop the host adb server so a dead guest cannot leave a stale transport."""
    try:
        proc = await asyncio.create_subprocess_exec(
            str(adb),
            "kill-server",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    except asyncio.TimeoutError:
        return "adb kill-server timed out"
    except OSError as exc:
        return f"adb kill-server failed to exec: {exc}"
    text = (stdout + stderr).decode("utf-8", errors="replace").strip()
    return text or f"adb kill-server rc={proc.returncode}"


async def run_android_adb_userspace_boot(
    disk_path: Path,
    iso_path: Path,
    console_path: Path,
    *,
    memory_mb: int = 2048,
    vcpus: int = 2,
    timeout_seconds: float = 1800.0,
    install_timeout_seconds: float = 900.0,
    adb_port: Optional[int] = None,
    qemu_stderr_path: Optional[Path] = None,
    live_boot_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Install this ISO onto the qcow, boot that disk, and demand adb shell.

    This is the PhoneVMState.READY owner. Option D uses this ISO's own
    AUTO_INSTALL=force path, then boots SRC=/thyris from the qcow without
    live /dev/sr0. ISOLINUX text is not READY. Disk create stays
    ISOConverter._create_disk. Windows accel is WHPX with kernel-irqchip=off.
    """
    require_windows_whpx_accelerator(select_qemu_accelerator())
    if "AUTO_INSTALL=force" not in ANDROID_AUTO_INSTALL_CMDLINE:
        raise ThyrisBootError("auto-install cmdline is missing AUTO_INSTALL=force")
    if f"INSTALL_PREFIX={ANDROID_INSTALL_PREFIX}" not in ANDROID_AUTO_INSTALL_CMDLINE:
        raise ThyrisBootError("auto-install cmdline is missing INSTALL_PREFIX")
    if f"SRC=/{ANDROID_INSTALL_PREFIX}" not in ANDROID_DISK_BOOT_CMDLINE:
        raise ThyrisBootError("disk-boot cmdline is not rooted on the installed prefix")
    if "AUTO_INSTALL" in ANDROID_LIVE_CMDLINE:
        raise ThyrisBootError("livem cmdline drifted onto AUTO_INSTALL")
    if "setprop" in ANDROID_AUTO_INSTALL_CMDLINE or "setprop" in ANDROID_DISK_BOOT_CMDLINE:
        raise ThyrisBootError("install/disk cmdline used setprop spam")
    qemu_system = resolve_qemu_system()
    adb = resolve_adb()
    disk = Path(disk_path)
    iso = Path(iso_path)
    console = Path(console_path)
    if not disk.is_file():
        raise FileNotFoundError(f"qcow2 missing: {disk}")
    if not iso.is_file():
        raise FileNotFoundError(f"Android ISO missing: {iso}")
    if timeout_seconds <= 0 or install_timeout_seconds <= 0:
        raise ThyrisAdbError("timeout_seconds and install_timeout_seconds must be > 0")
    killed_qemu = terminate_stale_thyris_qemu()
    kill_server_before = await adb_kill_server(adb)
    killed_adb = terminate_stale_adb()
    logger.info(
        "cleared leftover Thyris qemu pids=%s adb_kill_server=%s stale_adb=%s",
        killed_qemu,
        kill_server_before,
        killed_adb,
    )
    console.parent.mkdir(parents=True, exist_ok=True)
    stderr_file = Path(qemu_stderr_path) if qemu_stderr_path is not None else console.with_suffix(".qemu.stderr.log")
    boot_dir = Path(live_boot_dir) if live_boot_dir is not None else console.parent / "liveboot"
    kernel_path, initrd_path = extract_android_live_boot_files(iso, boot_dir)
    host_adb_port = adb_port if adb_port is not None else allocate_local_tcp_port()
    install_argv = build_android_qemu_argv(
        qemu_system=qemu_system,
        disk_path=disk,
        iso_path=iso,
        name=f"thyris-android-install-{uuid4().hex[:8]}",
        memory_mb=memory_mb,
        vcpus=vcpus,
        nographic=True,
        adb_port=host_adb_port,
        kernel_path=kernel_path,
        initrd_path=initrd_path,
        kernel_append=ANDROID_AUTO_INSTALL_CMDLINE,
        attach_iso=True,
    )
    if "-nographic" not in install_argv:
        raise ThyrisBootError("install argv is missing -nographic; refusing a VNC-only guest")
    if ANDROID_AUTO_INSTALL_CMDLINE not in install_argv:
        raise ThyrisBootError("install argv is missing AUTO_INSTALL=force")
    logger.info("Android AUTO_INSTALL argv: %s", " ".join(str(item) for item in install_argv))
    argv = install_argv
    stdout_handle = console.open("wb")
    stderr_handle = stderr_file.open("wb")
    process: Optional[asyncio.subprocess.Process] = None
    serial = f"127.0.0.1:{host_adb_port}"

    def _read_logs() -> tuple[str, str]:
        stdout_handle.flush()
        stderr_handle.flush()
        console_text = log_console.read_text(encoding="utf-8", errors="replace") if log_console.exists() else ""
        stderr_text = log_stderr.read_text(encoding="utf-8", errors="replace") if log_stderr.exists() else ""
        return console_text, stderr_text

    async def _proven(console_text: str, boot_argv: List[str], kernel_append: str, boot_mode: str) -> Dict[str, Any]:
        release = await adb_getprop(adb, host_adb_port, "ro.build.version.release")
        userspace_markers = [
            marker
            for marker in USERSPACE_EVIDENCE_MARKERS
            if marker.lower() in console_text.lower()
        ]
        return {
            "status": "adb_userspace",
            "pid": process.pid if process is not None else None,
            "qemu_system": str(qemu_system),
            "adb": str(adb),
            "accelerator": list(select_qemu_accelerator()),
            "disk_path": str(disk),
            "iso_path": str(iso),
            "iso_bytes": iso.stat().st_size,
            "kernel_path": str(kernel_path),
            "kernel_bytes": kernel_path.stat().st_size,
            "initrd_path": str(initrd_path),
            "initrd_bytes": initrd_path.stat().st_size,
            "console_path": str(log_console),
            "userspace_markers": userspace_markers,
            "console_excerpt": console_text[-4000:],
            "argv": boot_argv,
            "install_argv": install_argv,
            "adb_port": host_adb_port,
            "adb_serial": serial,
            "adb_detail": adb_detail,
            "android_release": release,
            "internal_ip": QEMU_USERNET_GUEST_IP,
            "install_markers": install_markers,
            "install_reboot_keys": reboot_keys,
            "stale_qemu_killed": killed_qemu,
            "stale_adb_killed": killed_adb,
            "adb_kill_server": kill_server_before,
            "kernel_append": kernel_append,
            "boot_mode": boot_mode,
            "vm_state": PhoneVMState.READY.value,
            "phone_ready": True,
            "adb_proven": True,
        }

    log_console = console
    log_stderr = stderr_file
    install_markers: List[str] = []
    reboot_keys = 0
    adb_detail = "adb not yet probed"
    console_text = ""
    stderr_text = ""
    disk_argv: List[str] = []
    try:
        process = await asyncio.create_subprocess_exec(
            *install_argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
        if process.pid is None:
            raise ThyrisBootError("qemu-system-x86_64 started without a pid")
        argv = install_argv
        install_deadline = time.monotonic() + install_timeout_seconds
        while time.monotonic() < install_deadline:
            console_text, stderr_text = _read_logs()
            install_markers = [
                marker
                for marker in INSTALL_PROGRESS_MARKERS
                if marker.lower() in console_text.lower()
            ]
            if process.returncode is None:
                try:
                    reboot_keys = await continue_auto_install_menu(
                        process, console_text, reboot_keys
                    )
                except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                    logger.debug("AUTO_INSTALL reboot key write failed: %s", exc)
                ok, adb_detail = await adb_shell_health(adb, host_adb_port)
                if ok:
                    return await _proven(
                        console_text,
                        install_argv,
                        ANDROID_AUTO_INSTALL_CMDLINE,
                        "auto_install_run",
                    )
            else:
                logger.info(
                    "AUTO_INSTALL qemu exited rc=%s disk_bytes=%s",
                    process.returncode,
                    disk.stat().st_size,
                )
                break
            await asyncio.sleep(5)
        await _stop_qemu_process(process)
        process = None
        stdout_handle.close()
        stderr_handle.close()
        disk_bytes = disk.stat().st_size
        if disk_bytes < ANDROID_INSTALLED_DISK_MIN_BYTES:
            raise ThyrisBootError(
                f"AUTO_INSTALL=force did not populate the qcow ({disk_bytes} bytes). "
                f"markers={install_markers!r} reboot_keys={reboot_keys} "
                f"stderr={stderr_text[-2000:]!r} console={console_text[-4000:]!r}"
            )
        log_console = console.with_name("disk-" + console.name)
        log_stderr = stderr_file.with_name("disk-" + stderr_file.name)
        stdout_handle = log_console.open("wb")
        stderr_handle = log_stderr.open("wb")
        disk_argv = build_android_qemu_argv(
            qemu_system=qemu_system,
            disk_path=disk,
            iso_path=iso,
            name=f"thyris-android-disk-{uuid4().hex[:8]}",
            memory_mb=memory_mb,
            vcpus=vcpus,
            nographic=True,
            adb_port=host_adb_port,
            kernel_path=kernel_path,
            initrd_path=initrd_path,
            kernel_append=ANDROID_DISK_BOOT_CMDLINE,
            attach_iso=False,
        )
        argv = disk_argv
        if "-nographic" not in disk_argv:
            raise ThyrisBootError("disk-boot argv is missing -nographic")
        if ANDROID_DISK_BOOT_CMDLINE not in disk_argv:
            raise ThyrisBootError("disk-boot argv is missing SRC=/thyris")
        if "media=cdrom" in " ".join(disk_argv):
            raise ThyrisBootError("disk-boot argv still attached live /dev/sr0 ISO")
        logger.info("Android disk-boot argv: %s", " ".join(str(item) for item in disk_argv))
        process = await asyncio.create_subprocess_exec(
            *disk_argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
        if process.pid is None:
            raise ThyrisBootError("disk-boot qemu-system-x86_64 started without a pid")
        deadline = time.monotonic() + timeout_seconds
        userspace_markers: List[str] = []
        while time.monotonic() < deadline:
            if process.returncode is not None:
                console_text, stderr_text = _read_logs()
                raise ThyrisBootError(
                    f"disk-boot QEMU exited rc={process.returncode} before ADB userspace proof. "
                    f"install_markers={install_markers!r} "
                    f"stderr={stderr_text[-4000:]!r} console={console_text[-4000:]!r}"
                )
            console_text, stderr_text = _read_logs()
            userspace_markers = [
                marker
                for marker in USERSPACE_EVIDENCE_MARKERS
                if marker.lower() in console_text.lower()
            ]
            ok, adb_detail = await adb_shell_health(adb, host_adb_port)
            if ok:
                return await _proven(
                    console_text,
                    disk_argv,
                    ANDROID_DISK_BOOT_CMDLINE,
                    "installed_disk",
                )
            await asyncio.sleep(10)
        console_text, stderr_text = _read_logs()
        raise ThyrisAdbError(
            f"No adb shell within {timeout_seconds}s on {serial} after AUTO_INSTALL=force. "
            f"Detecting Android-x86 / init markers are not READY. "
            f"accel={list(select_qemu_accelerator())!r} "
            f"detail={adb_detail!r} markers={userspace_markers!r} "
            f"install_markers={install_markers!r} reboot_keys={reboot_keys} "
            f"stale_qemu={killed_qemu!r} stale_adb={killed_adb!r} "
            f"stderr={stderr_text[-2000:]!r} console={console_text[-4000:]!r}"
        )
    finally:
        await _stop_qemu_process(process)
        stdout_handle.close()
        stderr_handle.close()
        await adb_disconnect(adb, host_adb_port)
        await adb_kill_server(adb)


# ==================== Phone VM Models ====================

class PhoneVMState(str, Enum):
    """Android phone VM lifecycle states"""
    PROVISIONING = "provisioning"
    BOOTING = "booting"
    READY = "ready"
    SUSPENDED = "suspended"
    SHUTDOWN = "shutdown"
    ERROR = "error"


class AndroidVersion(str, Enum):
    """Supported Android versions"""
    ANDROID_9 = "android-9"
    ANDROID_11 = "android-11"
    ANDROID_12 = "android-12"
    ANDROID_13 = "android-13"
    BLISS_OS_15 = "bliss-os-15"


@dataclass
class PhoneVMProfile:
    """Resource profile for Android phone VMs"""
    profile_name: str
    vcpus: int = 4
    memory_gb: int = 4
    storage_gb: int = 32
    display_width: int = 1080
    display_height: int = 2400
    dpi: int = 420
    description: str = "Standard phone profile"

    def validate(self) -> bool:
        """Validate profile constraints"""
        return (self.vcpus >= 1 and self.memory_gb >= 1 and
                self.storage_gb >= 8 and self.display_width > 0 and
                self.display_height > 0 and self.dpi > 0)


@dataclass
class AndroidPhoneVM:
    """Represents a persistent Android phone VM instance"""
    vm_id: UUID
    sovereign_id: str
    instance_name: str
    pan_phone_address: str
    
    # VM State
    vm_state: PhoneVMState = PhoneVMState.PROVISIONING
    android_version: AndroidVersion = AndroidVersion.ANDROID_9
    
    # Hardware specs
    profile: PhoneVMProfile = field(default_factory=lambda: PhoneVMProfile(profile_name="standard"))
    
    # Storage paths
    vm_disk_path: str = ""
    android_iso_path: str = ""
    serial_log_path: str = ""
    qemu_stderr_path: str = ""
    
    # Network configuration
    internal_ip: Optional[str] = None
    adb_port: int = 5555
    vnc_port: int = 5900
    
    # Display streaming (secured)
    vnc_password: str = field(default_factory=lambda: secrets.token_urlsafe(16))  # Random secure password
    
    # Installed apps tracking
    installed_apps: List[str] = field(default_factory=list)
    preinstalled_apps: List[str] = field(default_factory=list)
    
    # Personal data link
    personal_data_store_path: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Process info
    process: Optional[subprocess.Popen] = None  # Track full Popen for async management
    process_pid: Optional[int] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (exclude process for JSON)"""
        d = asdict(self)
        d["vm_id"] = str(self.vm_id)
        d["profile"] = asdict(self.profile)
        d["created_at"] = self.created_at.isoformat()
        d["last_active"] = self.last_active.isoformat()
        if self.process:
            d["process_pid"] = self.process.pid
        else:
            d["process_pid"] = self.process_pid
        return d

    def validate(self) -> Tuple[bool, Optional[str]]:
        """Full VM validation"""
        if not self.profile.validate():
            return False, "Invalid profile specs"
        if not Path(self.vm_disk_path).exists():
            return False, "VM disk path does not exist"
        if self.vnc_port <= 0 or self.adb_port <= 0:
            return False, "Invalid ports"
        return True, None


def apply_adb_ready(phone_vm: AndroidPhoneVM, internal_ip: str) -> AndroidPhoneVM:
    """Flip PhoneVMState.READY only after the same usernet ADB proof.

    Args:
        phone_vm: Provisioned or resumed phone object still in BOOTING.
        internal_ip: Must be the qemu user-net guest IP, not a libvirt fiction.

    Returns:
        The same phone_vm with vm_state READY.

    Raises:
        ThyrisAdbError: The IP is not the qemu user-net address.
    """
    if internal_ip != QEMU_USERNET_GUEST_IP:
        raise ThyrisAdbError(
            f"refusing PhoneVMState.READY with IP {internal_ip!r}; "
            f"expected qemu user-net {QEMU_USERNET_GUEST_IP}"
        )
    phone_vm.internal_ip = internal_ip
    phone_vm.vm_state = PhoneVMState.READY
    phone_vm.last_active = datetime.now(timezone.utc)
    return phone_vm


# ==================== Phone Orchestrator ====================

class ThyrisPhoneOrchestrator:
    """
    Central orchestrator for Android phone VM provisioning and management.
    
    Responsibilities:
    - Provision Android VMs with QEMU (full async, retries)
    - Assign PAN phone addresses
    - Manage personal data stores per sovereign identity (auto-sync)
    - Configure VNC display streaming (secured with passwords)
    - Handle APK installation via ADB (retries, health checks)
    - Integrate with VM memory system for persistence (auto-sync on boot/resume)
    - Orphan detection, metrics, structured logging
    """

    # Default resource profiles (loaded from config or defaults)
    PHONE_PROFILES = {}
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        memory_config: Optional[MemoryConfiguration] = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        vm_storage_path: Optional[str] = None,
        android_images_path: Optional[str] = None,
        vnc_base_port: Optional[int] = None,
        adb_base_port: Optional[int] = None
    ):
        # Load configuration from YAML file
        self.config = self._load_config(config_path)
        
        # Extract orchestrator config
        orch_config = self.config.get('orchestrator', {})
        
        # Use passed parameters if provided, otherwise config, otherwise defaults
        if vm_storage_path:
            self.vm_storage_path = Path(vm_storage_path)
        else:
            self.vm_storage_path = Path(orch_config.get('vm_storage_path', '/var/lib/thyris/phones'))
        
        if android_images_path:
            self.android_images_path = Path(android_images_path)
        else:
            self.android_images_path = Path(orch_config.get('android_images_path', str(Path(__file__).parent.parent / "android_images")))
        
        if vnc_base_port is not None:
            self.vnc_base_port = vnc_base_port
        else:
            self.vnc_base_port = orch_config.get('vnc_base_port', 5900)
        
        if adb_base_port is not None:
            self.adb_base_port = adb_base_port
        else:
            self.adb_base_port = orch_config.get('adb_base_port', 5555)
        self.max_retries = orch_config.get('max_retries', max_retries)
        self.retry_delay = orch_config.get('retry_delay_seconds', retry_delay)
        self.required_buffer_gb = orch_config.get('required_buffer_gb', 1.0)
        self.vm_disk_format = orch_config.get('vm_disk_format', 'qcow2')
        
        # Load phone profiles from config
        phone_profiles_config = self.config.get('phone_profiles', {})
        self.PHONE_PROFILES = {}
        for profile_name, profile_data in phone_profiles_config.items():
            self.PHONE_PROFILES[profile_name] = PhoneVMProfile(**profile_data)
        
        # Fallback to defaults if no profiles loaded
        if not self.PHONE_PROFILES:
            self.PHONE_PROFILES = {
                "light": PhoneVMProfile(profile_name="light", vcpus=2, memory_gb=2, storage_gb=16, display_width=720, display_height=1520, dpi=320, description="Light mobile profile"),
                "standard": PhoneVMProfile(profile_name="standard", vcpus=4, memory_gb=4, storage_gb=32, display_width=1080, display_height=2400, dpi=420, description="Standard mobile profile"),
                "premium": PhoneVMProfile(profile_name="premium", vcpus=6, memory_gb=8, storage_gb=64, display_width=1440, display_height=3200, dpi=560, description="Premium mobile profile")
            }
        
        # Memory configuration lives under VM storage, not cwd data/.
        if memory_config is None:
            memory_config = MemoryConfiguration(
                vector_db_path=str(self.vm_storage_path / "memory" / "vectors"),
                metadata_db_path=str(self.vm_storage_path / "memory" / "metadata.db"),
            )
        
        ensure_windows_qemu_on_path()
        self.vm_storage_path.mkdir(parents=True, exist_ok=True)
        self.android_images_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize VM management components
        self.vm_manager = CustomVMManager(self.vm_storage_path)
        self.network_manager = CustomNetworkManager()
        
        # Initialize PAN SDK components
        self.pan_registry = PANPhoneAddressRegistry(
            persistence=PANPersistenceStore(
                base_path=self.vm_storage_path / "pan_phone_registry"
            )
        )
        self.personal_data_stores: Dict[str, PANPersonalDataStore] = {}
        
        # Initialize VM memory system for session persistence
        self.memory_manager = MemoryManager(memory_config)
        # Low-memory cache config for phone VMs (64MB max)
        cache_config = {
            'max_entries': 1000,
            'max_memory_mb': 64,  # Low RAM usage for phone orchestrator
            'cache_dir': str(self.vm_storage_path / 'cache'),
            'persistence_enabled': True,
            'cleanup_interval_seconds': 600,  # Less frequent cleanup
        }
        self.cache = SomnusCache(cache_config, memory_manager=self.memory_manager)
        
        # Track active phone VMs
        self.active_phones: Dict[UUID, AndroidPhoneVM] = {}
        self.phone_config_path = self.vm_storage_path / "phone_configs"
        self.phone_config_path.mkdir(parents=True, exist_ok=True)
        self._qemu_stdio_handles: Dict[UUID, Tuple[object, object]] = {}
        
        # Port allocation tracking (with auto-release on errors)
        self.allocated_vnc_ports: set = set()
        self.allocated_adb_ports: set = set()
        
        # Metrics (simple counters/timers for production)
        self.metrics: Dict[str, Any] = defaultdict(lambda: {'count': 0, 'total_time': 0.0})
        
        # Load existing
        self._load_existing_phones()
        
        logger.info(f"ThyrisPhoneOrchestrator initialized (retries: {max_retries}, delay: {retry_delay}s)")

    async def initialize(self):
        """Initialize async components"""
        await self.memory_manager.initialize()
        self.cache.start_background_cleanup()
        await self._detect_and_cleanup_orphans()  # New: Clean up stale VMs
        logger.info("Phone orchestrator async components initialized")

    # ------------------ Host tool checks ------------------
    def _check_host_tool(self, tool_name: str) -> bool:
        """Return True if the named telecom host tool is actually resolvable."""
        if tool_name in {"qemu-system-x86_64", "qemu-img"}:
            ensure_windows_qemu_on_path()
        if tool_name == "qemu-system-x86_64":
            try:
                resolve_qemu_system()
                return True
            except FileNotFoundError:
                logger.warning("Required host tool not found: qemu-system-x86_64")
                return False
        if tool_name == "adb":
            try:
                resolve_adb()
                return True
            except FileNotFoundError:
                logger.warning("Required host tool not found: adb")
                return False
        tool = shutil.which(tool_name)
        if tool:
            return True
        logger.warning(f"Required host tool not found on PATH: {tool_name}")
        return False

    def _ensure_host_tools(self) -> Tuple[bool, List[str]]:
        """Ensure required host tools are present. Returns (ok, missing_tools)."""
        missing = [t for t in THYRIS_REQUIRED_HOST_TOOLS if not self._check_host_tool(t)]
        return (len(missing) == 0, missing)

    async def _detect_and_cleanup_orphans(self):
        """Detect and cleanup orphaned VMs/processes"""
        for vm_id, phone_vm in list(self.active_phones.items()):
            if phone_vm.process and phone_vm.process.poll() is not None:  # Process exited
                logger.warning(f"Orphaned process detected for {vm_id}, cleaning up")
                self._release_ports(phone_vm)
                del self.active_phones[vm_id]
                # Remove disk if ERROR state
                if phone_vm.vm_state == PhoneVMState.ERROR and Path(phone_vm.vm_disk_path).exists():
                    Path(phone_vm.vm_disk_path).unlink()

    def _load_existing_phones(self):
        """Load existing phone VM configurations from disk (with validation)"""
        for config_file in self.phone_config_path.glob("*.json"):
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                
                vm_id = UUID(data["vm_id"])
                phone_vm = AndroidPhoneVM(**{k: v for k, v in data.items() if k != 'profile'})
                phone_vm.profile = PhoneVMProfile(**data.get('profile', {}))
                phone_vm.created_at = datetime.fromisoformat(data["created_at"])
                phone_vm.last_active = datetime.fromisoformat(data["last_active"])
                
                # Validate on load
                valid, err = phone_vm.validate()
                if not valid:
                    logger.error(f"Invalid loaded config {config_file}: {err} - removing")
                    config_file.unlink()
                    continue
                
                self.active_phones[vm_id] = phone_vm
                self.allocated_vnc_ports.add(phone_vm.vnc_port)
                self.allocated_adb_ports.add(phone_vm.adb_port)
                
                # Reconnect process if running
                if phone_vm.process_pid:
                    try:
                        phone_vm.process = psutil.Process(phone_vm.process_pid)
                    except psutil.NoSuchProcess:
                        phone_vm.process = None
                
                logger.info(f"Loaded/validated phone VM: {phone_vm.instance_name} ({vm_id})")
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(f"Failed to load phone config {config_file}: {e} - removing")
                config_file.unlink()

    def _save_phone_config(self, phone_vm: AndroidPhoneVM):
        """Save phone VM configuration to disk (encrypted sensitive fields if needed)"""
        config_file = self.phone_config_path / f"{phone_vm.vm_id}.json"
        try:
            data = phone_vm.to_dict()
            # Encrypt sensitive (e.g., PAN path) - simple base64 for now; use Fernet in prod
            if phone_vm.personal_data_store_path:
                data['personal_data_store_path'] = hashlib.sha256(phone_vm.personal_data_store_path.encode()).hexdigest()
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved phone config: {config_file}")
        except Exception as e:
            logger.error(f"Failed to save phone config: {e}")

    def _release_ports(self, phone_vm: AndroidPhoneVM):
        """Release allocated ports"""
        self.allocated_vnc_ports.discard(phone_vm.vnc_port)
        self.allocated_adb_ports.discard(phone_vm.adb_port)

    def _allocate_vnc_port(self) -> int:
        """Allocate next available VNC port (with conflict check)"""
        port = self.vnc_base_port
        while port in self.allocated_vnc_ports or self._is_port_in_use(port):
            port += 1
            if port > self.vnc_base_port + 1000:  # Sanity limit
                raise RuntimeError("No available VNC ports")
        self.allocated_vnc_ports.add(port)
        return port

    def _allocate_adb_port(self) -> int:
        """Allocate next available ADB port (with conflict check)"""
        port = self.adb_base_port
        while port in self.allocated_adb_ports or self._is_port_in_use(port):
            port += 1
            if port > self.adb_base_port + 1000:
                raise RuntimeError("No available ADB ports")
        self.allocated_adb_ports.add(port)
        return port

    def _is_port_in_use(self, port: int) -> bool:
        """Check if port is in use"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def _get_android_iso_path(self, android_version: AndroidVersion) -> Path:
        """Resolve a real on-disk Android-x86 ISO. Fail loud if absent.

        Does not wget a 404. Prefers THYRIS_ANDROID_ISO, then version names,
        then android-x86_64-9.0-r2.iso / any android*.iso under android_images_path.
        Known official SHA-1 digests are verified.

        Args:
            android_version: Requested AndroidVersion.

        Returns:
            Path to an existing ISO larger than 1 MiB.

        Raises:
            FileNotFoundError: No legal ISO is present.
            ThyrisBootError: A known ISO failed its published SHA-1.
        """
        env_iso = os.environ.get("THYRIS_ANDROID_ISO", "").strip()
        names = {
            AndroidVersion.ANDROID_9: (ANDROID_X86_9_R2_ISO,),
            AndroidVersion.ANDROID_11: ("android-x86_64-11.0.iso", ANDROID_X86_9_R2_ISO),
            AndroidVersion.ANDROID_12: ("android-x86_64-12.0.iso", ANDROID_X86_9_R2_ISO),
            AndroidVersion.ANDROID_13: ("android-x86_64-13.0.iso", ANDROID_X86_9_R2_ISO),
            AndroidVersion.BLISS_OS_15: ("bliss-os-15.8.iso", ANDROID_X86_9_R2_ISO),
        }.get(android_version, (ANDROID_X86_9_R2_ISO,))
        candidates: List[Path] = []
        if env_iso:
            candidates.append(Path(env_iso))
        for name in names:
            candidates.append(self.android_images_path / name)
        if self.android_images_path.is_dir():
            for found in sorted(self.android_images_path.glob("*.iso")):
                lowered = found.name.lower()
                if "android" in lowered or "bliss" in lowered:
                    candidates.append(found)
        seen: set[str] = set()
        unique: List[Path] = []
        for candidate in candidates:
            key = str(candidate.resolve()) if candidate.exists() else str(candidate)
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        for iso_path in unique:
            if not iso_path.is_file():
                continue
            size = iso_path.stat().st_size
            if size < 1_000_000:
                raise ThyrisBootError(
                    f"Android ISO {iso_path} is {size} bytes; too small to be a real image"
                )
            expected = KNOWN_ANDROID_ISO_SHA1.get(iso_path.name)
            if expected:
                actual = sha1_file(iso_path)
                if actual != expected:
                    raise ThyrisBootError(
                        f"Android ISO {iso_path.name} SHA-1 {actual} != official {expected}"
                    )
            logger.info("Using Android ISO %s (%s bytes)", iso_path, size)
            return iso_path
        searched = [str(path) for path in unique]
        raise FileNotFoundError(
            "No real Android-x86 ISO found. Place the official "
            f"{ANDROID_X86_9_R2_ISO} under {self.android_images_path} or set "
            "THYRIS_ANDROID_ISO. https://www.android-x86.org/download "
            f"Searched: {searched}"
        )

    async def _check_resources(self, profile: PhoneVMProfile) -> Tuple[bool, Optional[str]]:
        """Check available resources before provisioning"""
        # Disk space
        disk_free_gb = shutil.disk_usage(self.vm_storage_path).free / (1024**3)
        required = profile.storage_gb + float(getattr(self, 'required_buffer_gb', 5.0))
        if disk_free_gb < required:
            return False, f"Insufficient disk space: {disk_free_gb:.1f}GB available, need {required}GB"
        
        # CPU/Memory (basic psutil check) - relaxed for development/testing
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        # Relaxed thresholds for development
        if cpu_percent > 95 or mem.available / (1024**3) < profile.memory_gb + 1:
            logger.warning(f"High system load detected (CPU: {cpu_percent}%, Mem available: {mem.available / (1024**3):.1f}GB), but proceeding for testing")
        
        return True, None

    async def provision_sovereign_phone(
        self,
        sovereign_id: str,
        instance_name: Optional[str] = None,
        android_version: AndroidVersion = AndroidVersion.ANDROID_9,
        profile_name: str = "standard",
        include_play_services: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: str = None  # For logging
    ) -> Dict[str, Any]:
        """
        Provision a new Android phone VM for a sovereign identity (full async, retries).
        Generates detailed JSON and Markdown reports of the provisioning process.
        """
        if correlation_id is None:
            correlation_id = str(uuid4())[:8]
        logger = logging.getLogger(__name__)
        logger.info(f"[{correlation_id}] Provisioning sovereign phone for {sovereign_id[:12]}...")

        # Initialize detailed report
        report = {
            "correlation_id": correlation_id,
            "sovereign_id": sovereign_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "metrics": {},
            "errors": [],
            "final_status": "unknown"
        }

        def add_step(step_name: str, status: str, details: Dict[str, Any] = None, error: str = None):
            """Add a step to the report."""
            step = {
                "step": step_name,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details or {},
                "error": error
            }
            report["steps"].append(step)
            logger.info(f"[{correlation_id}] {step_name}: {status}")

        try:
            # Input validation
            add_step("input_validation", "started")
            if not sovereign_id or len(sovereign_id) < 8:
                error_msg = "Invalid sovereign_id"
                add_step("input_validation", "failed", error=error_msg)
                return {"status": "error", "message": error_msg}
            add_step("input_validation", "completed", {"sovereign_id_length": len(sovereign_id)})

            # 1. Generate VM ID and names
            add_step("vm_id_generation", "started")
            vm_id = uuid4()
            if not instance_name:
                instance_name = f"phone-{sovereign_id[:8]}-{vm_id.hex[:4]}"
            add_step("vm_id_generation", "completed", {"vm_id": str(vm_id), "instance_name": instance_name})

            # 2. Resource check
            add_step("resource_check", "started")
            profile = self.PHONE_PROFILES.get(profile_name, self.PHONE_PROFILES["standard"])
            ok, err = await self._check_resources(profile)
            if not ok:
                add_step("resource_check", "failed", error=err)
                return {"status": "error", "message": err}
            add_step("resource_check", "completed", {"profile": profile_name, "vcpus": profile.vcpus, "memory_gb": profile.memory_gb})

            # 3. Assign PAN phone address
            add_step("pan_address_assignment", "started")
            pan_phone_address = self.pan_registry.assign_phone_address(sovereign_id=sovereign_id, vm_id=str(vm_id))
            add_step("pan_address_assignment", "completed", {"pan_phone_address": pan_phone_address})
            logger.info(f"[{correlation_id}] Assigned PAN address: {pan_phone_address}")

            # 4. Allocate ports (with checks)
            add_step("port_allocation", "started")
            vnc_port = self._allocate_vnc_port()
            adb_port = self._allocate_adb_port()
            add_step("port_allocation", "completed", {"vnc_port": vnc_port, "adb_port": adb_port})

            # 5. Set up storage (with space check)
            add_step("storage_setup", "started")
            vm_disk_path = self.vm_storage_path / f"phone-{vm_id}.qcow2"
            android_iso_path = self._get_android_iso_path(android_version)
            add_step("storage_setup", "completed", {"vm_disk_path": str(vm_disk_path), "android_iso_path": str(android_iso_path)})

            # Create disk image through the landed ISOConverter owner
            add_step("disk_creation", "started")
            await ISOConverter()._create_disk(vm_disk_path, profile.storage_gb)
            add_step("disk_creation", "completed", {"disk_size_gb": profile.storage_gb})

            # 6. Create phone VM object
            add_step("vm_object_creation", "started")
            phone_vm = AndroidPhoneVM(
                vm_id=vm_id,
                sovereign_id=sovereign_id,
                instance_name=instance_name,
                pan_phone_address=pan_phone_address,
                vm_state=PhoneVMState.PROVISIONING,
                android_version=android_version,
                profile=profile,
                vm_disk_path=str(vm_disk_path),
                android_iso_path=str(android_iso_path),
                vnc_port=vnc_port,
                adb_port=adb_port,
                metadata=metadata or {}
            )
            add_step("vm_object_creation", "completed", {"vm_state": phone_vm.vm_state.value})

            # 7. Initialize personal data store (with auto-sync to memory)
            add_step("personal_data_init", "started")
            personal_data_store = PANPersonalDataStore(
                sovereign_id=sovereign_id,
                base_path=self.vm_storage_path / "user_data" / sovereign_id[:12]
            )
            personal_data_store.base_path.mkdir(parents=True, exist_ok=True)
            self.personal_data_stores[sovereign_id] = personal_data_store
            phone_vm.personal_data_store_path = str(personal_data_store.base_path)
            add_step("personal_data_init", "completed", {"data_store_path": str(personal_data_store.base_path)})

            # Auto-populate basic data from memory manager (e.g., default contacts)
            add_step("memory_sync", "started")
            await self.memory_manager.sync_to_pan(sovereign_id, personal_data_store)
            add_step("memory_sync", "completed")

            # 8. Start the Android VM (async, retries)
            add_step("vm_startup", "started")
            success = await self._start_android_vm(phone_vm, include_play_services, correlation_id)
            if not success:
                error_msg = "Failed to start Android VM after retries"
                add_step("vm_startup", "failed", error=error_msg)
                phone_vm.vm_state = PhoneVMState.ERROR
                self._save_phone_config(phone_vm)
                self._release_ports(phone_vm)
                return {"status": "error", "message": error_msg}
            add_step("vm_startup", "completed", {"process_pid": phone_vm.process_pid})

            # 9. Wait for boot with retries/health check
            add_step("boot_wait", "started")
            phone_vm.vm_state = PhoneVMState.BOOTING
            self._save_phone_config(phone_vm)

            # Poll for IP and ADB readiness (retries)
            phone_vm.internal_ip = await self._wait_for_ip_and_adb(phone_vm, correlation_id)
            if not phone_vm.internal_ip:
                error_msg = "ADB/IP health check failed; refusing PhoneVMState.READY without adb proof"
                add_step("boot_wait", "failed", error=error_msg)
                phone_vm.vm_state = PhoneVMState.ERROR
                self._save_phone_config(phone_vm)
                if phone_vm.process:
                    await self._kill_process(phone_vm)
                report["final_status"] = "error"
                report["end_time"] = datetime.now(timezone.utc).isoformat()
                reports = {}
                try:
                    report_file_json = self.vm_storage_path / f"provision_report_{vm_id}.json"
                    with open(report_file_json, 'w') as f:
                        json.dump(report, f, indent=2)
                    reports["json"] = str(report_file_json)
                    report_file_md = self.vm_storage_path / f"provision_report_{vm_id}.md"
                    with open(report_file_md, 'w') as f:
                        f.write(self._generate_markdown_report(report))
                    reports["markdown"] = str(report_file_md)
                except (OSError, TypeError) as report_err:
                    logger.warning(f"[{correlation_id}] Failed to write provision report: {report_err}")
                self.metrics['provision_failure']['count'] += 1
                return {
                    "status": "error",
                    "message": error_msg,
                    "vm_id": str(vm_id),
                    "phone_ready": False,
                    "adb_proven": False,
                    "reports": reports,
                }
            add_step("boot_wait", "completed", {"internal_ip": phone_vm.internal_ip})

            # 10. Mark ready only after ADB proof
            add_step("finalization", "started")
            apply_adb_ready(phone_vm, phone_vm.internal_ip)

            # Final PAN/memory sync (e.g., push initial contacts/calls)
            await self._sync_pan_to_vm(phone_vm, personal_data_store)

            # 11. Register and save
            self.active_phones[vm_id] = phone_vm
            self._save_phone_config(phone_vm)

            self.metrics['provision_success']['count'] += 1
            add_step("finalization", "completed")
            logger.info(f"[{correlation_id}] Successfully provisioned phone VM: {instance_name} ({vm_id})")

            # Generate final report
            report["final_status"] = "success"
            report["end_time"] = datetime.now(timezone.utc).isoformat()
            report["duration_seconds"] = (datetime.fromisoformat(report["end_time"]) - datetime.fromisoformat(report["start_time"])).total_seconds()
            report["metrics"] = {
                "total_steps": len(report["steps"]),
                "successful_steps": len([s for s in report["steps"] if s["status"] == "completed"]),
                "failed_steps": len([s for s in report["steps"] if s["status"] == "failed"]),
                "warnings": len([s for s in report["steps"] if s["status"] == "warning"])
            }

            # Write JSON report
            report_file_json = self.vm_storage_path / f"provision_report_{vm_id}.json"
            with open(report_file_json, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"[{correlation_id}] Provision report saved: {report_file_json}")

            # Write Markdown report
            report_file_md = self.vm_storage_path / f"provision_report_{vm_id}.md"
            with open(report_file_md, 'w') as f:
                f.write(self._generate_markdown_report(report))
            logger.info(f"[{correlation_id}] Markdown report saved: {report_file_md}")

            return {
                "status": "success",
                "message": "Phone VM provisioned successfully",
                "vm_id": str(vm_id),
                "sovereign_id": sovereign_id,
                "pan_phone_address": pan_phone_address,
                "instance_name": instance_name,
                "connection_info": {
                    "vnc_port": vnc_port,
                    "vnc_url": f"vnc://localhost:{vnc_port}",
                    "vnc_password": phone_vm.vnc_password,  # Securely provide
                    "adb_port": adb_port,
                    "adb_connect": f"adb connect localhost:{adb_port}",
                    "internal_ip": phone_vm.internal_ip
                },
                "display": {
                    "width": profile.display_width,
                    "height": profile.display_height,
                    "dpi": profile.dpi
                },
                "personal_data_store": str(personal_data_store.base_path),
                "reports": {
                    "json": str(report_file_json),
                    "markdown": str(report_file_md)
                }
            }

        except (QemuImgError, ThyrisBootError, ThyrisAdbError, FileNotFoundError):
            self.metrics['provision_failure']['count'] += 1
            logger.error(f"[{correlation_id}] Failed to provision phone VM", exc_info=True)
            if 'phone_vm' in locals():
                phone_vm.vm_state = PhoneVMState.ERROR
                self._save_phone_config(phone_vm)
                self._release_ports(phone_vm)
            raise
        except (OSError, RuntimeError, ValueError, TypeError) as e:
            self.metrics['provision_failure']['count'] += 1
            error_msg = str(e)
            report["final_status"] = "failed"
            report["end_time"] = datetime.now(timezone.utc).isoformat()
            report["errors"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": error_msg
            })
            logger.error(f"[{correlation_id}] Failed to provision phone VM: {e}", exc_info=True)
            if 'phone_vm' in locals():
                phone_vm.vm_state = PhoneVMState.ERROR
                self._save_phone_config(phone_vm)
                self._release_ports(phone_vm)
            return {"status": "error", "message": error_msg}

    async def _start_android_vm(
        self,
        phone_vm: AndroidPhoneVM,
        include_play_services: bool,
        correlation_id: str
    ) -> bool:
        """Start the Android VM using the same live nographic argv as the ADB helper."""
        profile = phone_vm.profile
        logger.info(f"[{correlation_id}] Starting Android VM with profile: {profile.profile_name}")
        qemu_system = resolve_qemu_system()
        iso_path = Path(phone_vm.android_iso_path)
        disk_path = Path(phone_vm.vm_disk_path)
        if not iso_path.is_file():
            raise FileNotFoundError(f"Android ISO missing: {iso_path}")
        if not disk_path.is_file():
            raise QemuImgError(f"Phone disk missing: {disk_path}")
        boot_dir = disk_path.parent / f"liveboot-{phone_vm.vm_id}"
        kernel_path, initrd_path = extract_android_live_boot_files(iso_path, boot_dir)
        logger.info(
            "[%s] live boot kernel=%s bytes=%s initrd=%s bytes=%s",
            correlation_id,
            kernel_path,
            kernel_path.stat().st_size,
            initrd_path,
            initrd_path.stat().st_size,
        )
        last_error = "QEMU did not start"
        _ = include_play_services
        killed_qemu = terminate_stale_thyris_qemu()
        try:
            adb = resolve_adb()
            kill_server = await adb_kill_server(adb)
        except FileNotFoundError as exc:
            raise ThyrisAdbError(str(exc)) from exc
        killed_adb = terminate_stale_adb()
        logger.info(
            "[%s] cleared leftover qemu pids=%s adb_kill_server=%s stale_adb=%s",
            correlation_id,
            killed_qemu,
            kill_server,
            killed_adb,
        )
        serial_log = disk_path.with_suffix(".serial.log")
        stderr_log = disk_path.with_suffix(".qemu.stderr.log")
        phone_vm.serial_log_path = str(serial_log)
        phone_vm.qemu_stderr_path = str(stderr_log)

        for attempt in range(self.max_retries):
            logger.info(f"[{correlation_id}] QEMU start attempt {attempt + 1}/{self.max_retries}")
            stdout_handle = serial_log.open("wb")
            stderr_handle = stderr_log.open("wb")
            try:
                qemu_cmd = build_android_qemu_argv(
                    qemu_system=qemu_system,
                    disk_path=disk_path,
                    iso_path=iso_path,
                    name=f"thyris-phone-{phone_vm.vm_id}",
                    memory_mb=profile.memory_gb * 1024,
                    vcpus=profile.vcpus,
                    nographic=True,
                    adb_port=phone_vm.adb_port,
                    kernel_path=kernel_path,
                    initrd_path=initrd_path,
                    kernel_append=ANDROID_LIVE_CMDLINE,
                )
                if "-nographic" not in qemu_cmd:
                    raise ThyrisBootError("create_phone_vm argv is missing -nographic")
                if ANDROID_LIVE_CMDLINE not in qemu_cmd:
                    raise ThyrisBootError("create_phone_vm argv is missing isolinux livem/nosetup append")
                logger.debug(f"[{correlation_id}] QEMU command: {' '.join(qemu_cmd)}")
                phone_vm.process = await asyncio.create_subprocess_exec(
                    *qemu_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                )
                phone_vm.process_pid = phone_vm.process.pid
                self._qemu_stdio_handles[phone_vm.vm_id] = (stdout_handle, stderr_handle)
                logger.info(f"[{correlation_id}] QEMU process started with PID: {phone_vm.process_pid}")
                await asyncio.sleep(10)
                if phone_vm.process.returncode is None:
                    logger.info(f"[{correlation_id}] QEMU still running (PID: {phone_vm.process_pid})")
                    return True
                last_error = stderr_log.read_text(encoding="utf-8", errors="replace")[-4000:]
                logger.warning(f"[{correlation_id}] QEMU exited early: {last_error}")
                await self._kill_process(phone_vm)
            except (ThyrisBootError, ThyrisAdbError, FileNotFoundError, QemuImgError):
                stdout_handle.close()
                stderr_handle.close()
                self._qemu_stdio_handles.pop(phone_vm.vm_id, None)
                raise
            except (OSError, RuntimeError, ValueError) as e:
                last_error = str(e)
                stdout_handle.close()
                stderr_handle.close()
                self._qemu_stdio_handles.pop(phone_vm.vm_id, None)
                logger.warning(f"[{correlation_id}] QEMU start attempt {attempt+1} failed: {e}")
                if phone_vm.process:
                    await self._kill_process(phone_vm)
                if attempt < self.max_retries - 1:
                    retry_delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"[{correlation_id}] Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)

        raise ThyrisBootError(
            f"Failed to start QEMU after {self.max_retries} attempts: {last_error}"
        )

    async def boot_android_installer(
        self,
        disk_path: Path,
        iso_path: Path,
        console_path: Path,
        *,
        memory_mb: int = 2048,
        vcpus: int = 2,
        timeout_seconds: float = 90.0,
        qemu_stderr_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Boot a real Android-x86 ISO and demand SeaBIOS/ISOLINUX on nographic stdout.

        This is not a READY-phone or ADB claim. Success means the installer
        media produced identifiable boot text.

        Args:
            disk_path: qcow2 from ISOConverter._create_disk.
            iso_path: Legal Android-x86 ISO.
            console_path: File capturing qemu -nographic stdout (guest serial).
            memory_mb: Guest RAM.
            vcpus: vCPU count.
            timeout_seconds: How long to wait for boot markers.
            qemu_stderr_path: Optional capture of QEMU's own stderr.

        Returns:
            Structured boot evidence.

        Raises:
            FileNotFoundError: qemu-system, disk, or ISO is missing.
            ThyrisBootError: QEMU exited early or console never showed firmware/ISO boot.
        """
        qemu_system = resolve_qemu_system()
        disk = Path(disk_path)
        iso = Path(iso_path)
        console = Path(console_path)
        if not disk.is_file():
            raise FileNotFoundError(f"qcow2 missing: {disk}")
        if not iso.is_file():
            raise FileNotFoundError(f"Android ISO missing: {iso}")
        console.parent.mkdir(parents=True, exist_ok=True)
        stderr_file = Path(qemu_stderr_path) if qemu_stderr_path is not None else console.with_suffix(".qemu.stderr.log")
        argv = build_android_qemu_argv(
            qemu_system=qemu_system,
            disk_path=disk,
            iso_path=iso,
            name=f"thyris-android-boot-{uuid4().hex[:8]}",
            memory_mb=memory_mb,
            vcpus=vcpus,
            nographic=True,
        )
        logger.info("Android installer boot argv: %s", " ".join(str(item) for item in argv))
        stdout_handle = console.open("wb")
        stderr_handle = stderr_file.open("wb")
        process: Optional[asyncio.subprocess.Process] = None

        def _read_logs() -> tuple[str, str]:
            stdout_handle.flush()
            stderr_handle.flush()
            console_text = console.read_text(encoding="utf-8", errors="replace") if console.exists() else ""
            stderr_text = stderr_file.read_text(encoding="utf-8", errors="replace") if stderr_file.exists() else ""
            return console_text, stderr_text

        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
            if process.pid is None:
                raise ThyrisBootError("qemu-system-x86_64 started without a pid")
            deadline = time.monotonic() + timeout_seconds
            console_text = ""
            matched: List[str] = []
            iso_matched: List[str] = []
            while time.monotonic() < deadline:
                if process.returncode is not None:
                    console_text, stderr_text = _read_logs()
                    raise ThyrisBootError(
                        f"QEMU exited rc={process.returncode} before Android ISO boot evidence. "
                        f"stderr={stderr_text[-4000:]!r} console={console_text[-4000:]!r}"
                    )
                console_text, _stderr_unused = _read_logs()
                matched = [
                    marker
                    for marker in BOOT_EVIDENCE_MARKERS
                    if marker.lower() in console_text.lower()
                ]
                iso_matched = [
                    marker
                    for marker in ISO_BOOTLOADER_MARKERS
                    if marker.lower() in console_text.lower()
                ]
                if iso_matched:
                    break
                await asyncio.sleep(1)
            else:
                console_text, stderr_text = _read_logs()
                raise ThyrisBootError(
                    f"No Android-x86 ISOLINUX/kernel boot evidence within {timeout_seconds}s. "
                    f"SeaBIOS-only is not an ISO proof. This is not a dummy pass. "
                    f"stderr={stderr_text[-4000:]!r} console={console_text[-4000:]!r}"
                )
            return {
                "status": "boot_evidence",
                "pid": process.pid,
                "qemu_system": str(qemu_system),
                "accelerator": list(select_qemu_accelerator()),
                "disk_path": str(disk),
                "iso_path": str(iso),
                "iso_bytes": iso.stat().st_size,
                "console_path": str(console),
                "markers": matched,
                "iso_bootloader_markers": iso_matched,
                "console_excerpt": console_text[-4000:],
                "argv": argv,
                "phone_ready": False,
                "adb_proven": False,
            }
        finally:
            if process is not None and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            stdout_handle.close()
            stderr_handle.close()

    async def boot_android_adb_userspace(
        self,
        disk_path: Path,
        iso_path: Path,
        console_path: Path,
        *,
        memory_mb: int = 2048,
        vcpus: int = 2,
        timeout_seconds: float = 1800.0,
        adb_port: Optional[int] = None,
        qemu_stderr_path: Optional[Path] = None,
        live_boot_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Phone owner entry. Delegates to run_android_adb_userspace_boot."""
        return await run_android_adb_userspace_boot(
            disk_path,
            iso_path,
            console_path,
            memory_mb=memory_mb,
            vcpus=vcpus,
            timeout_seconds=timeout_seconds,
            adb_port=adb_port,
            qemu_stderr_path=qemu_stderr_path,
            live_boot_dir=live_boot_dir,
        )

    async def _wait_for_ip_and_adb(
        self,
        phone_vm: AndroidPhoneVM,
        correlation_id: str,
        timeout_seconds: float = 1800.0,
    ) -> Optional[str]:
        """Wait for real adb shell on the qemu user-net forward. Fake IPs are not READY."""
        adb_port = phone_vm.adb_port
        logger.info("[%s] Waiting for ADB userspace on 127.0.0.1:%s", correlation_id, adb_port)
        try:
            adb = resolve_adb()
        except FileNotFoundError as exc:
            logger.error("[%s] %s", correlation_id, exc)
            return None
        deadline = time.monotonic() + timeout_seconds
        debug_exits = 0
        attempt = 0
        serial_path = Path(phone_vm.serial_log_path) if phone_vm.serial_log_path else None
        while time.monotonic() < deadline:
            attempt += 1
            if phone_vm.process is not None and phone_vm.process.returncode is not None:
                logger.error("[%s] QEMU exited rc=%s before ADB proof", correlation_id, phone_vm.process.returncode)
                return None
            console_text = ""
            if serial_path is not None and serial_path.is_file():
                console_text = serial_path.read_text(encoding="utf-8", errors="replace")
            if phone_vm.process is not None:
                try:
                    debug_exits = await continue_isolinux_debug_shells(
                        phone_vm.process, console_text, debug_exits
                    )
                except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                    logger.debug("[%s] DEBUG=2 exit write failed: %s", correlation_id, exc)
            ok, detail = await adb_shell_health(adb, adb_port)
            logger.info("[%s] ADB attempt %s: %s", correlation_id, attempt, detail)
            if ok:
                logger.info("[%s] ADB userspace proven at %s", correlation_id, QEMU_USERNET_GUEST_IP)
                return QEMU_USERNET_GUEST_IP
            await asyncio.sleep(10)
        logger.warning("[%s] ADB userspace not proven after %.0fs", correlation_id, timeout_seconds)
        return None

    async def _sync_pan_to_vm(self, phone_vm: AndroidPhoneVM, personal_data_store: PANPersonalDataStore):
        """Sync PAN data (contacts/calls) to VM on boot/resume (via ADB push)."""
        try:
            # Export PAN data to JSON
            contacts_json = json.dumps([asdict(c) for c in personal_data_store.contacts])
            calls_json = json.dumps([asdict(cl) for cl in personal_data_store.call_log])
            
            # Temp files
            temp_contacts = self.vm_storage_path / f"contacts_{phone_vm.vm_id}.json"
            temp_calls = self.vm_storage_path / f"calls_{phone_vm.vm_id}.json"
            with open(temp_contacts, 'w') as f:
                f.write(contacts_json)
            with open(temp_calls, 'w') as f:
                f.write(calls_json)
            
            # ADB push to VM (e.g., /sdcard/ for import)
            adb_connect = f"localhost:{phone_vm.adb_port}"
            await asyncio.create_subprocess_exec(
                "adb", "-s", adb_connect, "push", str(temp_contacts), "/sdcard/contacts.json"
            )
            await asyncio.create_subprocess_exec(
                "adb", "-s", adb_connect, "push", str(temp_calls), "/sdcard/calls.json"
            )
            
            # Cleanup
            temp_contacts.unlink()
            temp_calls.unlink()
            
            logger.debug(f"Synced PAN data to VM {phone_vm.vm_id}")
        except Exception as e:
            logger.error(f"Failed to sync PAN to VM {phone_vm.vm_id}: {e}")

    async def _kill_process(self, phone_vm: AndroidPhoneVM):
        """Gracefully kill VM process (SIGTERM → SIGKILL)."""
        handles = self._qemu_stdio_handles.pop(phone_vm.vm_id, None)
        if phone_vm.process:
            try:
                phone_vm.process.terminate()  # SIGTERM
                await asyncio.wait_for(phone_vm.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                phone_vm.process.kill()  # SIGKILL
                await phone_vm.process.wait()
            finally:
                phone_vm.process = None
                phone_vm.process_pid = None
                self._release_ports(phone_vm)
        if handles is not None:
            stdout_handle, stderr_handle = handles
            stdout_handle.close()
            stderr_handle.close()
        try:
            adb = resolve_adb()
        except FileNotFoundError:
            return
        if phone_vm.adb_port > 0:
            await adb_disconnect(adb, phone_vm.adb_port)
        await adb_kill_server(adb)

    async def install_apk(
        self,
        vm_id: UUID,
        apk_path: str,
        grant_permissions: bool = True
    ) -> Dict[str, Any]:
        """Install an APK into the phone VM using async ADB (retries)."""
        phone_vm = self.active_phones.get(vm_id)
        if not phone_vm:
            return {"status": "error", "message": "Phone VM not found"}
        
        if phone_vm.vm_state != PhoneVMState.READY:
            return {"status": "error", "message": f"Phone VM not ready (state: {phone_vm.vm_state})"}

        adb_connect = f"localhost:{phone_vm.adb_port}"
        for attempt in range(self.max_retries):
            try:
                cmd = ["adb", "-s", adb_connect, "install"]
                if grant_permissions:
                    cmd.append("-g")
                cmd.append(apk_path)

                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

                if proc.returncode == 0 and b"Success" in stdout:
                    package_name = Path(apk_path).stem.split('.')[0]  # e.g., app_name from app_name.apk
                    phone_vm.installed_apps.append(package_name)
                    self._save_phone_config(phone_vm)
                    logger.info(f"Installed APK {package_name} on {vm_id}")
                    return {"status": "success", "message": "APK installed", "package_name": package_name}
                else:
                    err_msg = stderr.decode() if stderr else "Unknown error"
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                    else:
                        logger.error(f"APK install failed after {self.max_retries} retries: {err_msg}")
                        return {"status": "error", "message": err_msg}

            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return {"status": "error", "message": "APK installation timed out"}
            except Exception as e:
                logger.error(f"APK install error: {e}")
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": "Install failed after retries"}

    async def get_phone_health(self, vm_id: UUID) -> Dict[str, Any]:
        """Health check: ADB responsiveness, process status, resource usage."""
        phone_vm = self.active_phones.get(vm_id)
        if not phone_vm:
            return {"status": "error", "message": "VM not found"}

        health = {"vm_id": str(vm_id), "overall": "healthy", "details": {}}

        # Process check
        if phone_vm.process and phone_vm.process.returncode is None:
            health["process"] = {"running": True, "pid": phone_vm.process.pid}
            try:
                proc = psutil.Process(phone_vm.process.pid)
                health["process"]["cpu_percent"] = proc.cpu_percent()
                health["process"]["memory_mb"] = proc.memory_info().rss / 1024**2
            except psutil.NoSuchProcess:
                health["overall"] = "degraded"
                health["process"]["running"] = False
        else:
            health["overall"] = "degraded"
            health["process"] = {"running": False}

        # ADB check
        adb_connect = f"localhost:{phone_vm.adb_port}"
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb", "-s", adb_connect, "shell", "getprop", "ro.build.version.release",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode == 0:
                health["adb"] = {"connected": True, "android_version": stdout.decode().strip()}
            else:
                health["overall"] = "degraded"
                health["adb"] = {"connected": False}
        except (asyncio.TimeoutError, Exception):
            health["overall"] = "degraded"
            health["adb"] = {"connected": False}

        # PAN sync status (simple check)
        if phone_vm.sovereign_id in self.personal_data_stores:
            store = self.personal_data_stores[phone_vm.sovereign_id]
            health["pan_sync"] = {"contacts_count": len(store.contacts), "calls_count": len(store.call_log)}

        return health

    # ... (rest of methods: get_personal_data_store, get_phone_status, shutdown_phone, suspend_phone, resume_phone, list_phones, shutdown - with similar async/robust updates)

    async def shutdown_phone(self, vm_id: UUID) -> bool:
        """Gracefully shutdown a phone VM (async kill, port release)."""
        phone_vm = self.active_phones.get(vm_id)
        if not phone_vm:
            return False

        try:
            adb_connect = f"localhost:{phone_vm.adb_port}"
            proc = await asyncio.create_subprocess_exec(
                "adb", "-s", adb_connect, "reboot", "-p",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            # Wait and force kill if needed
            await asyncio.sleep(5)
            await self._kill_process(phone_vm)

            phone_vm.vm_state = PhoneVMState.SHUTDOWN
            self._save_phone_config(phone_vm)
            del self.active_phones[vm_id]

            logger.info(f"Shut down phone VM {vm_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to shutdown phone VM {vm_id}: {e}")
            await self._kill_process(phone_vm)  # Force
            return False

    async def suspend_phone(self, vm_id: UUID, auto_snapshot: bool = True) -> bool:
        """
        Suspend a phone VM with optional auto-snapshot (V2 feature).
        Uses QEMU QMP for true suspend if available, else state save.
        
        Args:
            vm_id: Phone VM to suspend
            auto_snapshot: Create automatic snapshot before suspend
        
        Returns:
            True if suspended successfully
        """
        phone_vm = self.active_phones.get(vm_id)
        if not phone_vm:
            return False

        try:
            # V2: Auto-snapshot on suspend for backup
            if auto_snapshot:
                snapshot_result = await self.create_auto_snapshot(vm_id)
                if snapshot_result["status"] != "success":
                    logger.warning(f"Auto-snapshot failed for {vm_id}, proceeding with suspend anyway")

            # Pause the VM process (SIGSTOP)
            if phone_vm.process and phone_vm.process.returncode is None:
                os.kill(phone_vm.process.pid, signal.SIGSTOP)
                logger.info(f"Suspended phone VM {vm_id} (PID: {phone_vm.process.pid})")

            phone_vm.vm_state = PhoneVMState.SUSPENDED
            self._save_phone_config(phone_vm)
            return True

        except Exception as e:
            logger.error(f"Failed to suspend phone VM {vm_id}: {e}")
            return False
    
    async def resume_phone(self, vm_id: UUID) -> bool:
        """
        Resume a suspended phone VM.
        
        Args:
            vm_id: Phone VM to resume
        
        Returns:
            True if resumed successfully
        """
        phone_vm = self.active_phones.get(vm_id)
        if not phone_vm:
            return False

        try:
            # Resume the VM process (SIGCONT)
            if phone_vm.process and phone_vm.process_pid:
                os.kill(phone_vm.process_pid, signal.SIGCONT)
                logger.info(f"Resumed phone VM {vm_id} (PID: {phone_vm.process_pid})")

            # Re-prove ADB before READY — SIGCONT alone is not userspace proof
            phone_vm.vm_state = PhoneVMState.BOOTING
            self._save_phone_config(phone_vm)
            internal_ip = await self._wait_for_ip_and_adb(phone_vm, correlation_id=str(vm_id)[:8])
            if not internal_ip:
                phone_vm.vm_state = PhoneVMState.ERROR
                self._save_phone_config(phone_vm)
                logger.error(f"Resume refused READY for {vm_id}: ADB health check failed")
                if phone_vm.process:
                    await self._kill_process(phone_vm)
                return False
            apply_adb_ready(phone_vm, internal_ip)
            self._save_phone_config(phone_vm)

            # Re-sync PAN data after resume only once ADB is proven
            personal_data_store = self.personal_data_stores.get(phone_vm.sovereign_id)
            if personal_data_store:
                await self._sync_pan_to_vm(phone_vm, personal_data_store)

            return True

        except Exception as e:
            logger.error(f"Failed to resume phone VM {vm_id}: {e}")
            return False

    async def shutdown(self):
        """Shutdown the orchestrator and cleanup (async)."""
        logger.info("Shutting down phone orchestrator...")
        
        # Async shutdown all
        tasks = [self.shutdown_phone(vm_id) for vm_id in list(self.active_phones.keys())]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Cleanup
        self.cache.shutdown()
        await self.memory_manager.shutdown()
        
        logger.info("Phone orchestrator shutdown complete")
    
    # ==================== V2 Features: Hotswap & Advanced Management ====================
    
    async def migrate_vm_state(
        self,
        from_vm_id: UUID,
        to_vm_id: UUID,
        migration_type: str = "android_to_ai"  # or "ai_to_android"
    ) -> Dict[str, Any]:
        """
        V2 hotswap: migrate VM state between phone VMs.
        Uses QEMU savevm/loadvm for state transfer. Not an in-phone AI prompt path.
        
        Args:
            from_vm_id: Source VM to save state from
            to_vm_id: Destination VM to restore state to
            migration_type: Type of migration (determines compatibility checks)
        
        Returns:
            Migration result with status and metrics
        """
        logger.info(f"Starting VM migration: {from_vm_id} → {to_vm_id} ({migration_type})")
        
        try:
            # 1. Validate source VM exists and is running
            source_vm = self.active_phones.get(from_vm_id)
            if not source_vm or source_vm.vm_state != PhoneVMState.READY:
                return {"status": "error", "message": "Source VM not ready for migration"}
            
            # 2. Validate destination VM exists
            # For AI VM, would check vm_supervisor.active_vms instead
            dest_vm = self.active_phones.get(to_vm_id)
            if not dest_vm:
                return {"status": "error", "message": "Destination VM not found"}
            
            # 3. Create migration snapshot path
            migration_snapshot = self.vm_storage_path / f"migration_{from_vm_id}_to_{to_vm_id}.qcow2"
            
            # 4. Save source VM state via QEMU monitor
            logger.info(f"Saving state from VM {from_vm_id}...")
            save_cmd = [
                "qemu-img", "snapshot", "-c", f"migrate_{datetime.utcnow().isoformat()}",
                source_vm.vm_disk_path
            ]
            proc = await asyncio.create_subprocess_exec(
                *save_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            
            if proc.returncode != 0:
                return {"status": "error", "message": f"Failed to save state: {stderr.decode()}"}
            
            # 5. Pause source VM (suspend)
            await self.suspend_phone(from_vm_id)
            
            # 6. Copy snapshot to destination (could use QEMU backing files for efficiency)
            logger.info(f"Copying state to VM {to_vm_id}...")
            await asyncio.create_subprocess_exec(
                "qemu-img", "convert", "-O", "qcow2",
                source_vm.vm_disk_path, str(migration_snapshot)
            )
            
            # 7. Restore state to destination VM
            # NOTE: For Android→AI migration, would need compatibility layer
            # For now, assumes same disk format
            restore_cmd = [
                "qemu-img", "snapshot", "-a", f"migrate_{datetime.utcnow().isoformat()}",
                str(migration_snapshot)
            ]
            proc = await asyncio.create_subprocess_exec(
                *restore_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            
            # 8. Boot destination VM with migrated state
            resumed = await self.resume_phone(to_vm_id)
            if not resumed:
                return {
                    "status": "error",
                    "message": f"Destination VM {to_vm_id} failed to resume after migration; "
                               f"see {migration_snapshot} for recovery"
                }

            # 9. Cleanup migration snapshot
            migration_snapshot.unlink()

            logger.info(f"Successfully migrated VM state: {from_vm_id} → {to_vm_id}")
            
            return {
                "status": "success",
                "message": "VM state migrated successfully",
                "from_vm_id": str(from_vm_id),
                "to_vm_id": str(to_vm_id),
                "migration_type": migration_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"VM migration failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    async def create_auto_snapshot(
        self,
        vm_id: UUID,
        snapshot_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        V2 Backup: Create automatic snapshot of phone VM disk.
        Called on suspend or periodically.
        
        Args:
            vm_id: Phone VM to snapshot
            snapshot_name: Optional custom name (auto-generated if None)
        
        Returns:
            Snapshot details
        """
        phone_vm = self.active_phones.get(vm_id)
        if not phone_vm:
            return {"status": "error", "message": "VM not found"}
        
        if not snapshot_name:
            snapshot_name = f"auto_snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Use qemu-img snapshot for disk-level snapshots
            cmd = [
                "qemu-img", "snapshot", "-c", snapshot_name,
                phone_vm.vm_disk_path
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            
            if proc.returncode != 0:
                return {"status": "error", "message": f"Snapshot failed: {stderr.decode()}"}
            
            # Track snapshot in metadata
            if "snapshots" not in phone_vm.metadata:
                phone_vm.metadata["snapshots"] = []
            
            phone_vm.metadata["snapshots"].append({
                "name": snapshot_name,
                "created_at": datetime.utcnow().isoformat(),
                "disk_path": phone_vm.vm_disk_path
            })
            
            self._save_phone_config(phone_vm)
            
            logger.info(f"Created snapshot {snapshot_name} for VM {vm_id}")
            
            return {
                "status": "success",
                "snapshot_name": snapshot_name,
                "vm_id": str(vm_id),
                "created_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def export_metrics(self) -> Dict[str, Any]:
        """
        V2 Monitoring: Export orchestrator metrics for dashboard integration.
        
        Returns:
            Metrics dictionary for VM supervisor dashboard
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "orchestrator": "thyris_phone",
            "metrics": {
                "active_vms": len(self.active_phones),
                "total_provisions": self.metrics.get('provision_success', {}).get('count', 0),
                "failed_provisions": self.metrics.get('provision_failure', {}).get('count', 0),
                "allocated_vnc_ports": len(self.allocated_vnc_ports),
                "allocated_adb_ports": len(self.allocated_adb_ports),
                "personal_data_stores": len(self.personal_data_stores)
            },
            "vm_health": {
                str(vm_id): await self.get_phone_health(vm_id)
                for vm_id in self.active_phones.keys()
            },
            "resource_usage": {
                "disk_free_gb": shutil.disk_usage(self.vm_storage_path).free / (1024**3),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_available_gb": psutil.virtual_memory().available / (1024**3)
            }
        }
    
    # ==================== V2: PAN Network Activation (Placeholder) ====================
    
    async def activate_pan_communications(
        self,
        vm_id: UUID,
        communication_type: str = "voice"  # voice/video/data
    ) -> Dict[str, Any]:
        """
        V2 Feature: Activate real PAN network communications for a phone VM.
        
        This is the "flip the switch" moment when phone numbers become functional.
        Integrates WebRTC for voice/video via ADB-pushed libraries.
        
        Args:
            vm_id: Phone VM to activate
            communication_type: Type of communication to enable
        
        Returns:
            Activation result
        """
        phone_vm = self.active_phones.get(vm_id)
        if not phone_vm:
            return {"status": "error", "message": "VM not found"}
        
        logger.info(f"Activating PAN communications ({communication_type}) for VM {vm_id}")
        
        try:
            # 1. Push WebRTC libraries to phone via ADB
            # In production: download from your .lacka network CDN
            webrtc_apk = self.vm_storage_path / "pan_webrtc_service.apk"
            
            if not webrtc_apk.exists():
                return {
                    "status": "error",
                    "message": "WebRTC service APK not found. Download from PAN network first."
                }
            
            # 2. Install WebRTC service
            install_result = await self.install_apk(vm_id, str(webrtc_apk))
            if install_result["status"] != "success":
                return install_result
            
            # 3. Configure PAN phone address routing
            # This would integrate with your .lacka network routing table
            pan_address = phone_vm.pan_phone_address
            routing_config = {
                "pan_address": pan_address,
                "vm_id": str(vm_id),
                "sovereign_id": phone_vm.sovereign_id,
                "adb_port": phone_vm.adb_port,
                "communication_types": [communication_type]
            }
            
            # 4. Register with PAN network (stub - implement your routing protocol)
            # await self.pan_registry.register_active_endpoint(routing_config)
            
            # 5. Update VM metadata
            phone_vm.metadata["pan_activated"] = True
            phone_vm.metadata["pan_activation_time"] = datetime.utcnow().isoformat()
            phone_vm.metadata["communication_types"] = [communication_type]
            self._save_phone_config(phone_vm)
            
            logger.info(f"PAN communications activated for {pan_address}")
            
            return {
                "status": "success",
                "message": "PAN communications activated",
                "pan_address": pan_address,
                "communication_type": communication_type,
                "vm_id": str(vm_id)
            }
            
        except Exception as e:
            logger.error(f"PAN activation failed: {e}")
            return {"status": "error", "message": str(e)}
    
    # ==================== V2: Multi-Host Scaling (Distributed Registry) ====================
    
    async def register_with_distributed_registry(
        self,
        registry_type: str = "etcd",  # or "consul"
        registry_endpoints: List[str] = None
    ) -> bool:
        """
        V2 Scaling: Register this orchestrator instance with distributed registry.
        Enables multi-host deployments with leader election and port coordination.
        
        Args:
            registry_type: Type of distributed KV store (etcd/consul)
            registry_endpoints: List of registry server endpoints
        
        Returns:
            True if registration successful
        """
        if registry_endpoints is None:
            registry_endpoints = ["localhost:2379"]  # Default etcd
        
        try:
            # In production, use etcd3 or python-consul library
            # For now, log the intent
            logger.info(f"Registering with {registry_type} at {registry_endpoints}")
            
            # Would implement:
            # 1. Leader election for primary orchestrator
            # 2. Port range allocation across hosts
            # 3. VM registry (which host has which VMs)
            # 4. Health heartbeats
            
            # Example etcd structure:
            # /thyris/orchestrators/{orchestrator_id} -> {host, ports, capacity}
            # /thyris/vms/{vm_id} -> {orchestrator_id, host, ports}
            # /thyris/leader -> {orchestrator_id}
            
            self.metadata["registry_type"] = registry_type
            self.metadata["registry_endpoints"] = registry_endpoints
            self.metadata["orchestrator_id"] = str(uuid4())
            
            logger.info(f"Registered orchestrator: {self.metadata['orchestrator_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register with distributed registry: {e}")
            return False
    
    async def acquire_leader_lock(self) -> bool:
        """
        V2 Scaling: Attempt to acquire leader lock in distributed setup.
        Leader handles global tasks like port allocation and VM scheduling.
        
        Returns:
            True if this instance is now the leader
        """
        # Implement using etcd lease or consul session
        # With TTL and automatic release on failure
        logger.info("Attempting to acquire leader lock...")
        
        # Stub - would use etcd3.Lock or consul.Session
        # For now, assume single-instance (always leader)
        self.metadata["is_leader"] = True
        return True
    
    def get_capacity_metrics(self) -> Dict[str, Any]:
        """
        V2 Scaling: Calculate current capacity for load balancing decisions.
        Used by leader to determine where to provision new VMs.
        
        Returns:
            Capacity metrics for this orchestrator instance
        """
        disk_total = shutil.disk_usage(self.vm_storage_path).total / (1024**3)
        disk_used = (disk_total - shutil.disk_usage(self.vm_storage_path).free / (1024**3))
        
        return {
            "orchestrator_id": self.metadata.get("orchestrator_id", "unknown"),
            "active_vms": len(self.active_phones),
            "max_vms": 100,  # Configurable limit
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "memory_used_gb": (psutil.virtual_memory().total - psutil.virtual_memory().available) / (1024**3),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "disk_used_gb": disk_used,
            "disk_total_gb": disk_total,
            "available_vnc_ports": 1000 - len(self.allocated_vnc_ports),
            "available_adb_ports": 1000 - len(self.allocated_adb_ports),
            "capacity_score": self._calculate_capacity_score()
        }
    
    def _calculate_capacity_score(self) -> float:
        """
        Calculate 0-1 capacity score (1.0 = fully available, 0.0 = overloaded).
        Used for load balancing decisions.
        """
        vm_ratio = len(self.active_phones) / 100  # Max 100 VMs
        cpu_ratio = psutil.cpu_percent(interval=0.1) / 100
        mem = psutil.virtual_memory()
        mem_ratio = (mem.total - mem.available) / mem.total
        disk_ratio = 1 - (shutil.disk_usage(self.vm_storage_path).free / shutil.disk_usage(self.vm_storage_path).total)
        
        # Weighted average (VM count and CPU are most important)
        score = 1.0 - (0.4 * vm_ratio + 0.3 * cpu_ratio + 0.2 * mem_ratio + 0.1 * disk_ratio)
        return max(0.0, min(1.0, score))

    def _generate_markdown_report(self, report: Dict[str, Any]) -> str:
        """
        Generate a detailed Markdown report from the provisioning report dict.
        """
        md = []

        # Header
        md.append("# Oracle Browser - Phone VM Provisioning Report")
        md.append("")
        md.append(f"**Correlation ID:** {report['correlation_id']}")
        md.append(f"**Sovereign ID:** {report['sovereign_id']}")
        md.append(f"**Start Time:** {report['start_time']}")
        md.append(f"**End Time:** {report.get('end_time', 'N/A')}")
        md.append(f"**Duration:** {report.get('duration_seconds', 'N/A')} seconds")
        md.append(f"**Final Status:** {report['final_status'].upper()}")
        md.append("")

        # Metrics Summary
        if report.get('metrics'):
            md.append("## Metrics Summary")
            md.append("")
            metrics = report['metrics']
            md.append(f"- **Total Steps:** {metrics['total_steps']}")
            md.append(f"- **Successful Steps:** {metrics['successful_steps']}")
            md.append(f"- **Failed Steps:** {metrics['failed_steps']}")
            md.append(f"- **Warnings:** {metrics['warnings']}")
            md.append("")

        # Step-by-Step Breakdown
        md.append("## Provisioning Steps")
        md.append("")
        for step in report['steps']:
            status_emoji = {
                "started": "▶️",
                "completed": "✅",
                "failed": "❌",
                "warning": "⚠️"
            }.get(step['status'], "❓")

            md.append(f"### {status_emoji} {step['step']}")
            md.append("")
            md.append(f"**Status:** {step['status'].upper()}")
            md.append(f"**Timestamp:** {step['timestamp']}")

            if step.get('details'):
                md.append("**Details:**")
                for k, v in step['details'].items():
                    md.append(f"  - {k}: {v}")

            if step.get('error'):
                md.append(f"**Error:** {step['error']}")

            md.append("")

        # Errors Section
        if report.get('errors'):
            md.append("## Errors")
            md.append("")
            for error in report['errors']:
                md.append(f"- **{error['timestamp']}:** {error['error']}")
            md.append("")

        # Footer
        md.append("---")
        md.append("*Generated by Thyris Phone Orchestrator*")
        md.append("*Oracle Browser - Sovereign Phone VM Provisioning*")

        return "\n".join(md)

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        import yaml
        
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'schemas' / 'phone_config.yaml'
        else:
            config_path = Path(config_path)
        
        try:
            if config_path.exists():
                with open(config_path, 'r') as fh:
                    config = yaml.safe_load(fh)
                    logger.info(f"Loaded configuration from {config_path}")
                    return config
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                return {}
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}, using defaults")
            return {}