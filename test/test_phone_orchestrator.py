import sys
import tempfile
import shutil
from pathlib import Path
import pytest

from types import SimpleNamespace
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

class DummyVMManager:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path


class DummyNetworkManager:
    def __init__(self):
        pass


class DummyPANRegistry:
    def __init__(self):
        pass


class DummyMemoryManager:
    def __init__(self, cfg=None):
        self._initialized = False

    async def initialize(self):
        self._initialized = True


class DummyCache:
    def __init__(self, config=None, memory_manager=None):
        self.config = config
        self.memory_manager = memory_manager

    def start_background_cleanup(self):
        pass


@pytest.fixture()
def patch_phone_orchestrator(monkeypatch, tmp_path):
    """Patch external dependencies in the phone_orchestrator module."""
    import thyris.virtual_machine.phone_orchestrator as po

    monkeypatch.setattr(po, 'CustomVMManager', DummyVMManager)
    monkeypatch.setattr(po, 'CustomNetworkManager', DummyNetworkManager)
    monkeypatch.setattr(po, 'PANPhoneAddressRegistry', DummyPANRegistry)
    monkeypatch.setattr(po, 'MemoryManager', DummyMemoryManager)
    monkeypatch.setattr(po, 'SomnusCache', DummyCache)

    return po


def test_orchestrator_initializes_and_creates_dirs(patch_phone_orchestrator, tmp_path):
    po = patch_phone_orchestrator

    vm_storage = tmp_path / "vm_storage"
    android_images = tmp_path / "android_images"

    orchestrator = po.ThyrisPhoneOrchestrator(
        vm_storage_path=str(vm_storage),
        android_images_path=str(android_images),
        vnc_base_port=6000,
        adb_base_port=6600,
        memory_config=None,
        max_retries=1,
        retry_delay=0.1
    )

    # Basic state checks
    assert orchestrator.vm_storage_path.exists()
    assert orchestrator.android_images_path.exists()
    assert isinstance(orchestrator.vm_manager, DummyVMManager)
    assert isinstance(orchestrator.network_manager, DummyNetworkManager)
    assert isinstance(orchestrator.pan_registry, DummyPANRegistry)


def test_port_allocation_and_release(patch_phone_orchestrator, tmp_path):
    po = patch_phone_orchestrator

    orchestrator = po.ThyrisPhoneOrchestrator(
        vm_storage_path=str(tmp_path / "vms2"),
        android_images_path=str(tmp_path / "images2"),
        vnc_base_port=7000,
        adb_base_port=7500,
    )

    p1 = orchestrator._allocate_vnc_port()
    p2 = orchestrator._allocate_vnc_port()
    assert p1 != p2
    assert p1 in orchestrator.allocated_vnc_ports
    assert p2 in orchestrator.allocated_vnc_ports

    a1 = orchestrator._allocate_adb_port()
    a2 = orchestrator._allocate_adb_port()
    assert a1 != a2
    assert a1 in orchestrator.allocated_adb_ports

    # Create a fake phone entry to release
    fake_id = po.uuid4()
    fake_phone = po.AndroidPhoneVM(
        vm_id=fake_id,
        sovereign_id='sid',
        instance_name='i',
        pan_phone_address='pan:0'
    )
    fake_phone.vnc_port = p1
    fake_phone.adb_port = a1
    orchestrator._release_ports(fake_phone)

    assert p1 not in orchestrator.allocated_vnc_ports
    assert a1 not in orchestrator.allocated_adb_ports
