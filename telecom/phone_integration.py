"""
Oracle Browser - Phone VM Integration
Handles APK import, phone display, and interaction between browser and Android VMs.

Features:
- APK import from browser downloads
- Phone display in sidebar (VNC streaming)
- Touch event forwarding
- App management
- PAN phone address display
"""

import logging
import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass

# Import phone orchestrator
import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from thyris.virtual_machine.phone_orchestrator import (
    ThyrisPhoneOrchestrator,
    AndroidPhoneVM,
    AndroidVersion,
    PhoneVMState
)
from PAN_SDK.personal_data import PANPersonalDataStore

logger = logging.getLogger(__name__)


# ==================== Browser-Phone Bridge ====================

@dataclass
class APKImportRequest:
    """Represents an APK import request from browser"""
    apk_path: str
    filename: str
    user_sovereign_id: str
    vm_id: Optional[UUID] = None
    auto_install: bool = True
    grant_permissions: bool = True
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class PhoneDisplayConfig:
    """Configuration for phone display in browser sidebar"""
    vm_id: UUID
    vnc_port: int
    width: int
    height: int
    scaling_factor: float = 1.0
    show_status_bar: bool = True
    show_navigation_bar: bool = True


class OracleBrowserPhoneManager:
    """
    Manages the integration between Oracle Browser and Android phone VMs.
    
    This is the bridge layer that:
    - Handles APK imports from browser downloads
    - Manages phone display in sidebar
    - Routes touch events from browser to phone VM
    - Displays PAN phone addresses
    - Manages multiple phones per user
    """
    
    def __init__(
        self,
        phone_orchestrator: ThyrisPhoneOrchestrator,
        download_dir: Path,
        apk_staging_dir: Optional[Path] = None
    ):
        """
        Initialize the browser-phone manager.
        
        Args:
            phone_orchestrator: Phone VM orchestrator instance
            download_dir: Browser downloads directory to monitor
            apk_staging_dir: Temporary staging area for APK imports
        """
        self.orchestrator = phone_orchestrator
        self.download_dir = Path(download_dir)
        self.apk_staging_dir = apk_staging_dir or Path("/tmp/oracle_apk_imports")
        self.apk_staging_dir.mkdir(parents=True, exist_ok=True)
        
        # Track APK import queue
        self.import_queue: List[APKImportRequest] = []
        self.import_history: List[Dict[str, Any]] = []
        
        # Track active phone displays (user -> vm_id mapping)
        self.active_displays: Dict[str, UUID] = {}
        
        # Download monitoring
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("OracleBrowserPhoneManager initialized")
    
    async def start_download_monitoring(self):
        """Start monitoring the downloads directory for APK files"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_downloads())
        logger.info(f"Started monitoring {self.download_dir} for APK downloads")
    
    async def stop_download_monitoring(self):
        """Stop monitoring downloads"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped download monitoring")
    
    async def _monitor_downloads(self):
        """Background task to monitor downloads directory"""
        seen_files = set()
        
        while self._running:
            try:
                # Scan for new APK files
                for apk_file in self.download_dir.glob("*.apk"):
                    if apk_file not in seen_files:
                        seen_files.add(apk_file)
                        logger.info(f"Detected new APK download: {apk_file.name}")
                        # Trigger UI notification (callback to browser)
                        await self._notify_apk_available(apk_file)
                
                await asyncio.sleep(2)  # Check every 2 seconds
            except Exception as e:
                logger.error(f"Error in download monitor: {e}")
                await asyncio.sleep(5)
    
    async def _notify_apk_available(self, apk_path: Path):
        """
        Notify browser UI that an APK is available for import.
        In production, this would trigger a browser notification/popup.
        """
        # This would be implemented as a callback to the browser UI
        # For now, just log it
        logger.info(f"📱 APK ready for import: {apk_path.name}")
        logger.info(f"   Call import_apk_to_phone() to install")
    
    async def import_apk_to_phone(
        self,
        apk_path: str,
        user_sovereign_id: str,
        vm_id: Optional[UUID] = None,
        auto_install: bool = True,
        delete_after_import: bool = True
    ) -> Dict[str, Any]:
        """
        Import an APK from browser downloads into a phone VM.
        
        This is the main entry point called from browser UI when user clicks
        "Import to Phone" on a downloaded APK.
        
        Args:
            apk_path: Path to downloaded APK file
            user_sovereign_id: User's sovereign identity
            vm_id: Target phone VM (None = use active phone)
            auto_install: Automatically install the APK
            delete_after_import: Delete APK from downloads after import
        
        Returns:
            Import result dictionary with status and details
        """
        logger.info(f"Importing APK {apk_path} for user {user_sovereign_id[:12]}")
        
        try:
            apk_file = Path(apk_path)
            if not apk_file.exists():
                return {
                    "status": "error",
                    "message": f"APK file not found: {apk_path}"
                }
            
            # 1. Determine target phone VM
            if vm_id is None:
                # Use active phone for this user
                vm_id = self.active_displays.get(user_sovereign_id)
                
                if vm_id is None:
                    # No active phone - get first phone for user or create one
                    user_phones = self.orchestrator.list_phones(user_sovereign_id)
                    
                    if not user_phones:
                        return {
                            "status": "error",
                            "message": "No phone VM found. Please create a phone first.",
                            "action_required": "create_phone"
                        }
                    
                    vm_id = UUID(user_phones[0]["vm_id"])
            
            # 2. Verify phone VM exists and is ready
            phone_status = self.orchestrator.get_phone_status(vm_id)
            if not phone_status:
                return {
                    "status": "error",
                    "message": f"Phone VM {vm_id} not found"
                }
            
            if phone_status["vm_state"] != PhoneVMState.READY.value:
                return {
                    "status": "error",
                    "message": f"Phone is not ready (state: {phone_status['vm_state']})"
                }
            
            # 3. Stage the APK (copy to staging area)
            staged_apk = self.apk_staging_dir / f"{vm_id}_{apk_file.name}"
            shutil.copy2(apk_file, staged_apk)
            logger.info(f"Staged APK to {staged_apk}")
            
            # 4. Install via orchestrator
            if auto_install:
                install_result = await self.orchestrator.install_apk(
                    vm_id=vm_id,
                    apk_path=str(staged_apk),
                    grant_permissions=True
                )
                
                if install_result["status"] != "success":
                    return {
                        "status": "error",
                        "message": f"APK installation failed: {install_result.get('message', 'Unknown error')}"
                    }
                
                package_name = install_result.get("package_name", apk_file.stem)
            else:
                # Just copy to phone storage, don't install yet
                package_name = apk_file.stem
                install_result = {"status": "staged"}
            
            # 5. Clean up
            if delete_after_import:
                try:
                    apk_file.unlink()
                    logger.info(f"Deleted original APK from downloads")
                except Exception as e:
                    logger.warning(f"Could not delete APK: {e}")
            
            # Clean up staging
            try:
                staged_apk.unlink()
            except:
                pass
            
            # 6. Record import history
            self.import_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "user_sovereign_id": user_sovereign_id,
                "vm_id": str(vm_id),
                "apk_filename": apk_file.name,
                "package_name": package_name,
                "auto_installed": auto_install,
                "status": "success"
            })
            
            logger.info(f"Successfully imported {apk_file.name} to phone {vm_id}")
            
            return {
                "status": "success",
                "message": f"APK imported and installed successfully",
                "vm_id": str(vm_id),
                "package_name": package_name,
                "phone_name": phone_status["instance_name"],
                "pan_address": phone_status["pan_phone_address"]
            }
            
        except Exception as e:
            logger.error(f"APK import failed: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Import failed: {str(e)}"
            }
    
    async def get_or_create_user_phone(
        self,
        user_sovereign_id: str,
        instance_name: Optional[str] = None,
        profile_name: str = "standard"
    ) -> Dict[str, Any]:
        """
        Get existing phone for user or create a new one.
        Called when user first opens phone sidebar.
        
        Args:
            user_sovereign_id: User's sovereign identity
            instance_name: Optional custom phone name
            profile_name: Resource profile (light/standard/premium)
        
        Returns:
            Phone VM details
        """
        # Check if user already has a phone
        user_phones = self.orchestrator.list_phones(user_sovereign_id)
        
        if user_phones:
            # Return first phone
            phone = user_phones[0]
            vm_id = UUID(phone["vm_id"])
            self.active_displays[user_sovereign_id] = vm_id
            
            logger.info(f"Using existing phone {vm_id} for user {user_sovereign_id[:12]}")
            return phone
        
        # Create new phone
        logger.info(f"Creating new phone for user {user_sovereign_id[:12]}")
        
        result = await self.orchestrator.provision_sovereign_phone(
            sovereign_id=user_sovereign_id,
            instance_name=instance_name or f"Phone-{user_sovereign_id[:8]}",
            android_version=AndroidVersion.ANDROID_13,
            profile_name=profile_name
        )
        
        if result["status"] == "success":
            vm_id = UUID(result["vm_id"])
            self.active_displays[user_sovereign_id] = vm_id
            
            # Return phone details
            return self.orchestrator.get_phone_status(vm_id)
        else:
            return result
    
    def get_phone_display_config(
        self,
        user_sovereign_id: str,
        sidebar_width: int = 360
    ) -> Optional[PhoneDisplayConfig]:
        """
        Get display configuration for phone in browser sidebar.
        
        Args:
            user_sovereign_id: User's sovereign identity
            sidebar_width: Width of browser sidebar in pixels
        
        Returns:
            Display configuration or None if no active phone
        """
        vm_id = self.active_displays.get(user_sovereign_id)
        if not vm_id:
            return None
        
        phone_status = self.orchestrator.get_phone_status(vm_id)
        if not phone_status:
            return None
        
        # Get phone from orchestrator to access profile
        phone_vm = self.orchestrator.active_phones.get(vm_id)
        if not phone_vm:
            return None
        
        profile = phone_vm.profile
        
        # Calculate scaling to fit in sidebar
        scaling_factor = sidebar_width / profile.display_width
        
        return PhoneDisplayConfig(
            vm_id=vm_id,
            vnc_port=phone_status["vnc_port"],
            width=profile.display_width,
            height=profile.display_height,
            scaling_factor=scaling_factor
        )
    
    def get_vnc_stream_url(
        self,
        user_sovereign_id: str,
        use_websocket: bool = True
    ) -> Optional[str]:
        """
        Get VNC stream URL for embedding in browser.
        
        Args:
            user_sovereign_id: User's sovereign identity
            use_websocket: Use WebSocket proxy for browser compatibility
        
        Returns:
            VNC stream URL or None
        """
        display_config = self.get_phone_display_config(user_sovereign_id)
        if not display_config:
            return None
        
        if use_websocket:
            # In production, you'd have a WebSocket-to-VNC proxy
            # For now, return the WebSocket URL that would be served
            ws_port = 6080  # noVNC default WebSocket port
            return f"ws://localhost:{ws_port}/?port={display_config.vnc_port}"
        else:
            # Direct VNC URL (not browser-compatible)
            return f"vnc://localhost:{display_config.vnc_port}"
    
    async def send_touch_event(
        self,
        user_sovereign_id: str,
        x: int,
        y: int,
        event_type: str = "tap"
    ) -> bool:
        """
        Send touch event from browser to phone VM.
        
        Args:
            user_sovereign_id: User's sovereign identity
            x: Touch X coordinate
            y: Touch Y coordinate
            event_type: Type of touch event (tap/swipe/long_press)
        
        Returns:
            True if event sent successfully
        """
        vm_id = self.active_displays.get(user_sovereign_id)
        if not vm_id:
            return False
        
        phone_status = self.orchestrator.get_phone_status(vm_id)
        if not phone_status:
            return False
        
        try:
            # Send touch via ADB input command
            adb_connect = f"localhost:{phone_status['adb_port']}"
            
            if event_type == "tap":
                cmd = ["adb", "-s", adb_connect, "shell", "input", "tap", str(x), str(y)]
            elif event_type == "swipe":
                # For swipe, you'd need start and end coordinates
                # This is simplified
                cmd = ["adb", "-s", adb_connect, "shell", "input", "swipe", str(x), str(y), str(x+100), str(y+100)]
            else:
                return False
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Failed to send touch event: {e}")
            return False
    
    def get_user_contacts(self, user_sovereign_id: str) -> List[Dict[str, Any]]:
        """
        Get contacts for user's phone.
        
        Args:
            user_sovereign_id: User's sovereign identity
        
        Returns:
            List of contacts
        """
        data_store = self.orchestrator.get_personal_data_store(user_sovereign_id)
        if not data_store:
            return []
        
        contacts = data_store.list_contacts()
        return [
            {
                "contact_id": c.contact_id,
                "display_name": c.display_name,
                "pan_phone_address": c.pan_phone_address,
                "phone_numbers": c.phone_numbers,
                "favorite": c.favorite
            }
            for c in contacts
        ]
    
    def get_pan_phone_address(self, user_sovereign_id: str) -> Optional[str]:
        """
        Get PAN phone address for user's phone.
        This is what's displayed in the phone UI (V1: non-functional).
        
        Args:
            user_sovereign_id: User's sovereign identity
        
        Returns:
            PAN phone address or None
        """
        vm_id = self.active_displays.get(user_sovereign_id)
        if not vm_id:
            return None
        
        phone_status = self.orchestrator.get_phone_status(vm_id)
        if phone_status:
            return phone_status["pan_phone_address"]
        
        return None
    
    def get_import_history(
        self,
        user_sovereign_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get APK import history.
        
        Args:
            user_sovereign_id: Filter by user (None = all users)
            limit: Maximum number of records to return
        
        Returns:
            List of import history records
        """
        history = self.import_history
        
        if user_sovereign_id:
            history = [h for h in history if h["user_sovereign_id"] == user_sovereign_id]
        
        return history[-limit:]


# ==================== Browser UI Integration Helpers ====================

class BrowserPhoneUI:
    """
    Helper class for browser UI integration.
    Provides simplified API for common UI operations.
    """
    
    def __init__(self, phone_manager: OracleBrowserPhoneManager):
        self.manager = phone_manager
    
    async def handle_apk_download(self, apk_path: str, user_id: str) -> Dict[str, Any]:
        """
        Handle APK download from browser.
        Called automatically when user downloads an APK.
        
        Returns UI notification data.
        """
        return {
            "type": "apk_ready",
            "title": "APK Downloaded",
            "message": f"Import {Path(apk_path).name} to your phone?",
            "actions": [
                {
                    "label": "Import to Phone",
                    "callback": "import_apk",
                    "data": {"apk_path": apk_path, "user_id": user_id}
                },
                {
                    "label": "Dismiss",
                    "callback": "dismiss"
                }
            ]
        }
    
    async def handle_import_action(self, apk_path: str, user_id: str) -> Dict[str, Any]:
        """
        Handle user clicking "Import to Phone" button.
        """
        result = await self.manager.import_apk_to_phone(
            apk_path=apk_path,
            user_sovereign_id=user_id,
            auto_install=True,
            delete_after_import=True
        )
        
        if result["status"] == "success":
            return {
                "type": "success_notification",
                "title": "App Installed",
                "message": f"{result['package_name']} installed on {result['phone_name']}",
                "icon": "✅"
            }
        else:
            return {
                "type": "error_notification",
                "title": "Import Failed",
                "message": result["message"],
                "icon": "❌"
            }
    
    async def open_phone_sidebar(self, user_id: str) -> Dict[str, Any]:
        """
        Open phone in browser sidebar.
        Returns configuration for sidebar component.
        """
        # Get or create phone
        phone = await self.manager.get_or_create_user_phone(user_id)
        
        if phone.get("status") == "error":
            return {
                "type": "error",
                "message": phone.get("message", "Failed to open phone")
            }
        
        # Get display config
        display_config = self.manager.get_phone_display_config(user_id, sidebar_width=360)
        vnc_url = self.manager.get_vnc_stream_url(user_id, use_websocket=True)
        pan_address = self.manager.get_pan_phone_address(user_id)
        
        return {
            "type": "phone_sidebar",
            "phone": {
                "name": phone["instance_name"],
                "pan_address": pan_address,
                "state": phone["vm_state"],
                "android_version": phone["android_version"]
            },
            "display": {
                "vnc_url": vnc_url,
                "width": display_config.width,
                "height": display_config.height,
                "scaling": display_config.scaling_factor
            },
            "installed_apps": phone.get("installed_apps", [])
        }


# ==================== Example Usage ====================

async def example_browser_integration():
    """Example of how Oracle Browser would use this system"""
    
    # 1. Initialize components
    from thyris.virtual_machine.phone_orchestrator import create_phone_orchestrator
    
    orchestrator = await create_phone_orchestrator()
    
    phone_manager = OracleBrowserPhoneManager(
        phone_orchestrator=orchestrator,
        download_dir=Path.home() / "Downloads"
    )
    
    browser_ui = BrowserPhoneUI(phone_manager)
    
    # 2. Start monitoring downloads
    await phone_manager.start_download_monitoring()
    
    # 3. User opens phone sidebar
    user_id = "user-sovereign-id-12345"
    sidebar_config = await browser_ui.open_phone_sidebar(user_id)
    print("Sidebar config:", sidebar_config)
    
    # 4. User downloads an APK
    apk_path = str(Path.home() / "Downloads" / "SomeApp.apk")
    notification = await browser_ui.handle_apk_download(apk_path, user_id)
    print("Show notification:", notification)
    
    # 5. User clicks "Import to Phone"
    result = await browser_ui.handle_import_action(apk_path, user_id)
    print("Import result:", result)
    
    # 6. Check import history
    history = phone_manager.get_import_history(user_id)
    print(f"Import history: {len(history)} items")
    
    # Cleanup
    await phone_manager.stop_download_monitoring()
    await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(example_browser_integration())
