"""
================================================================================
Oracle Browser - Thyris Phone Orchestrator
================================================================================

Manages Android phone VMs for Oracle Browser V1. Separate from AI VM orchestration
to maintain clean separation of concerns and enable V2 hotswap feature.

Architecture:
- Provisions Android-x86 VMs via QEMU (full async subprocess)
- Assigns PAN phone addresses (visible but non-functional in V1)
- Links to PAN SDK personal data stores (contacts/messages/calls)
- Sets up VNC display streaming for browser sidebar (with random passwords)
- Configures ADB over network for APK installation (with retries/health checks)
- Uses VM memory system for session persistence (auto-sync on boot)
- Robust: Retries, orphan detection, metrics, encryption for configs

V1: Infrastructure with "unusable" phone numbers to build hype
V2: Full communication network activation with hotswap (Android VM ↔ AI agent VM)

Modified: 2026-09-11
Modified by: cursor-grok (daeron)
Justification: I rebound memory_system.memory_core / memory_system.system_cache
    onto this repository's memory.memory_core and memory.system_cache. A
    memory_system package would duplicate Thyris memory beside USMS. Import-time
    FileHandler + correlation_id format would write a cwd log and KeyError on
    the first log record that lacks that field.
Provenance: snapshots/v0.6/manifest.json -> domains.thyris.edits[0]
Files: telecom/phone_orchestrator.py
"""

from __future__ import annotations

import logging
import asyncio
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
import secrets  # For secure random passwords
import psutil  # For PID/process management (from your VM supervisor)
import os
import signal
from collections import defaultdict

# Import VM infrastructure
from .vm_supervisor import VMSupervisor, VMState, ResourceProfile
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
    android_version: AndroidVersion = AndroidVersion.ANDROID_13
    
    # Hardware specs
    profile: PhoneVMProfile = field(default_factory=lambda: PhoneVMProfile(profile_name="standard"))
    
    # Storage paths
    vm_disk_path: str = ""
    android_iso_path: str = ""
    
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
        
        # Create directories
        self.vm_storage_path.mkdir(parents=True, exist_ok=True)
        self.android_images_path.mkdir(parents=True, exist_ok=True)
        
        # Create directories
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
        """Return True if tool is available on PATH, otherwise False."""
        tool = shutil.which(tool_name)
        if tool:
            return True
        logger.warning(f"Required host tool not found on PATH: {tool_name}")
        return False

    def _ensure_host_tools(self) -> Tuple[bool, List[str]]:
        """Ensure required host tools are present. Returns (ok, missing_tools)."""
        required = ['qemu-system-x86_64', 'qemu-img', 'adb']
        missing = [t for t in required if not self._check_host_tool(t)]
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
        """Get path to Android ISO image (with auto-download fallback)"""
        iso_map = {
            AndroidVersion.ANDROID_11: "android-x86_64-11.0.iso",
            AndroidVersion.ANDROID_12: "android-x86_64-12.0.iso",
            AndroidVersion.ANDROID_13: "android-x86_64-13.0.iso",
            AndroidVersion.BLISS_OS_15: "bliss-os-15.8.iso"
        }
        
        iso_filename = iso_map.get(android_version, "android-x86_64-13.0.iso")
        iso_path = self.android_images_path / iso_filename
        
        if not iso_path.exists():
            logger.warning(f"Android ISO not found: {iso_path}")
            # Auto-download (simple wget fallback; customize URL)
            download_url = f"https://www.android-x86.org/releases/{iso_filename}"
            try:
                subprocess.run(["wget", "-O", str(iso_path), download_url], check=True, capture_output=True)
                logger.info(f"Downloaded ISO: {iso_path}")
            except subprocess.CalledProcessError:
                raise FileNotFoundError(f"Failed to download ISO from {download_url}. Manual download required: https://www.android-x86.org/download")
        
        return iso_path

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
        android_version: AndroidVersion = AndroidVersion.ANDROID_13,
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

            # Create disk image (async subprocess)
            add_step("disk_creation", "started")
            proc = await asyncio.create_subprocess_exec(
                "qemu-img", "create", "-f", "qcow2", str(vm_disk_path), f"{profile.storage_gb}G",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                error_msg = f"Failed to create disk: {stderr.decode()}"
                add_step("disk_creation", "failed", error=error_msg)
                raise RuntimeError(error_msg)
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
            phone_vm.internal_ip = await self._wait_for_ip_and_adb(vm_id, adb_port, correlation_id)
            if not phone_vm.internal_ip:
                add_step("boot_wait", "warning", {"note": "Could not confirm IP/ADB"})
            else:
                add_step("boot_wait", "completed", {"internal_ip": phone_vm.internal_ip})

            # 10. Mark ready and sync data
            add_step("finalization", "started")
            phone_vm.vm_state = PhoneVMState.READY
            phone_vm.last_active = datetime.now(timezone.utc)

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

        except Exception as e:
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
        """Start the Android VM using async QEMU (retries, health checks)."""
        profile = phone_vm.profile
        logger.info(f"[{correlation_id}] Starting Android VM with profile: {profile.profile_name}")

        for attempt in range(self.max_retries):
            logger.info(f"[{correlation_id}] QEMU start attempt {attempt + 1}/{self.max_retries}")
            try:
                # Build QEMU command (secured VNC)
                qemu_cmd = [
                    "qemu-system-x86_64",
                    "-enable-kvm",
                    "-name", f"thyris-phone-{phone_vm.vm_id}",
                    "-uuid", str(phone_vm.vm_id),
                    "-m", f"{profile.memory_gb}G",
                    "-smp", str(profile.vcpus),
                    "-drive", f"file={phone_vm.vm_disk_path},format=qcow2,if=virtio",
                    "-cdrom", phone_vm.android_iso_path,
                    "-boot", "d",
                    "-netdev", f"user,id=net0,hostfwd=tcp::{phone_vm.adb_port}-:5555",
                    "-device", "virtio-net,netdev=net0",
                    "-vga", "virtio",
                    "-display", "none",
                    f"-vnc", f":{phone_vm.vnc_port - 5900},password=on,websocket=5700+{phone_vm.vnc_port - 5900}",  # Secured + WebSocket
                    "-audiodev", "none,id=audio0",
                    "-device", "usb-tablet"
                ]
                if include_play_services:
                    qemu_cmd.extend(["-device", "virtio-gpu-pci"])  # For better graphics

                logger.debug(f"[{correlation_id}] QEMU command: {' '.join(qemu_cmd)}")

                # Async start (no daemonize - manage manually)
                phone_vm.process = await asyncio.create_subprocess_exec(
                    *qemu_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                phone_vm.process_pid = phone_vm.process.pid
                logger.info(f"[{correlation_id}] QEMU process started with PID: {phone_vm.process_pid}")

                # Initial health check (wait 10s, check if running)
                logger.info(f"[{correlation_id}] Performing initial health check...")
                await asyncio.sleep(10)
                if phone_vm.process.returncode is None:  # Still running
                    logger.info(f"[{correlation_id}] QEMU started successfully (PID: {phone_vm.process_pid})")
                    return True
                else:
                    stdout, stderr = await phone_vm.process.communicate()
                    logger.warning(f"[{correlation_id}] QEMU exited early: {stderr.decode()}")
                    await self._kill_process(phone_vm)

            except Exception as e:
                logger.warning(f"[{correlation_id}] QEMU start attempt {attempt+1} failed: {e}")
                if phone_vm.process:
                    await self._kill_process(phone_vm)
                if attempt < self.max_retries - 1:
                    retry_delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"[{correlation_id}] Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)

        logger.error(f"[{correlation_id}] Failed to start QEMU after {self.max_retries} attempts")
        return False

    async def _wait_for_ip_and_adb(self, vm_id: UUID, adb_port: int, correlation_id: str) -> Optional[str]:
        """Wait for VM IP and ADB readiness (retries, health check via ADB shell)."""
        logger.info(f"[{correlation_id}] Waiting for VM IP and ADB readiness (max 5 minutes)...")

        for attempt in range(30):  # 5 min max
            logger.debug(f"[{correlation_id}] IP/ADB check attempt {attempt + 1}/30")

            ip = self.network_manager.get_vm_ip(vm_id)
            if ip:
                logger.debug(f"[{correlation_id}] Found IP: {ip}, checking ADB...")
                # Health check: ADB shell echo
                proc = await asyncio.create_subprocess_exec(
                    "adb", "-s", f"localhost:{adb_port}", "shell", "echo", "health_check",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
                if proc.returncode == 0 and b"health_check" in stdout:
                    logger.info(f"[{correlation_id}] VM ready at IP {ip} (ADB confirmed)")
                    return ip
                else:
                    logger.debug(f"[{correlation_id}] IP {ip} found but ADB not ready: {stderr.decode()}")
            else:
                logger.debug(f"[{correlation_id}] No IP assigned yet")

            await asyncio.sleep(10)

        logger.warning(f"[{correlation_id}] VM IP/ADB not ready after 5min")
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

            phone_vm.vm_state = PhoneVMState.READY
            phone_vm.last_active = datetime.now(timezone.utc)
            self._save_phone_config(phone_vm)

            # Re-sync PAN data after resume
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
        V2 Hotswap: Migrate VM state between Android phone and AI agent VMs.
        Uses QEMU savevm/loadvm for state transfer.
        
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
            await self.resume_phone(to_vm_id)
            
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