"""Thin adapter/shim layer to expose a stable SDK API for the repo.

This module re-exports core classes and provides small compatibility shims
so callers can depend on a single import path: tools.sdk_dev.sdk_adapter
"""
from typing import Any, Dict, Optional, Tuple, Union
import personal_data
import logging
import sovereign_firewall

from .PAN_SDK import (
    SovereignIdentity as CoreSovereignIdentity,
    SovereignCommunicator,
    UnifiedDataPacket,
    ModelManifest,
    SovereignInferenceEngine,
    SovereignPipeline,
    utc_now_iso,
)

# Compatibility wrapper for SovereignIdentity: accept optional connection_type and other kwargs
class SovereignIdentity:
    """Wrapper around core.SovereignIdentity to accept legacy keyword args.

    Accepts (name, private_key_pem=None, connection_type=..., **kwargs) and forwards
    to the core implementation which only requires (name, private_key_pem).
    """
    def __init__(self, name: str, private_key_pem: Optional[bytes] = None, **kwargs):
        # Ignore extra compatibility kwargs like connection_type
        # Default hashchain_parent=None for new constructor compatibility
        self._core = CoreSovereignIdentity(name, private_key_pem, hashchain_parent=None)

    def __getattr__(self, item):
        return getattr(self._core, item)

    def __repr__(self):
        return f"SovereignIdentityShim({getattr(self._core, 'identity_hash', 'unknown')})"

# Re-export common classes (keep our SovereignIdentity wrapper defined above)
SovereignCommunicator = SovereignCommunicator
UnifiedDataPacket = UnifiedDataPacket
ModelManifest = ModelManifest
SovereignInferenceEngine = SovereignInferenceEngine
SovereignPipeline = SovereignPipeline

# Some environments may not include a full SovereignAPIServer in the core module.
# Provide a tiny fallback server that exposes create_admin_key() for smoke tests.
class SmallServer:
    def __init__(self, port: int = 8001, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        # Minimal local fallback (no external core dependency)
        class _LocalKM:
            def __init__(self):
                self.keys = {}
            def create_key(self, name, scopes, expires_hours=None, rate_limit_per_hour=10000):
                raw = f"sk-local-{name[:8]}"
                api = type('APIKeyObj', (), {'key_id': 'local', 'key_hash': raw, 'name': name, 'scopes': scopes, 'created_at': utc_now_iso()})
                return raw, api
        self.api_key_manager = _LocalKM()

    def create_admin_key(self):
        return self.api_key_manager.create_key(
            "admin",
            ["inference"],  # Fallback string since PAN_SDK lacks APIKeyScope
            expires_hours=None,
            rate_limit_per_hour=10000
        )


# Compatibility shim: async wrapper for sync inference engine (if needed)
class AsyncInferenceEngineShim:
    """Wrap a synchronous SovereignInferenceEngine to provide async process_request_async."""
    def __init__(self, sync_engine: AsyncSovereignInferenceEngine):
        self._engine = sync_engine

    async def load_model(self):
        # call sync load_model in thread to avoid blocking event loop
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._engine.load_model)

    async def process_request_async(self, request_packet: UnifiedDataPacket, user_public_key_pem: bytes) -> UnifiedDataPacket:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._engine.process_request, request_packet, user_public_key_pem)


def create_admin_server(port: int = 8001, host: str = "127.0.0.1") -> SmallServer:
    """Convenience factory to create a minimal server instance for testing."""
    return SmallServer(port=port, host=host)


# Small helper to create a signed manifest from creator identity (keeps API stable)
def make_manifest(model_name: str, model_hash: str, model_public_key_pem: bytes, creator_identity: SovereignIdentity, model_version: str = "1.0.0", **kwargs) -> ModelManifest:
    # Ignore model_version and kwargs for new ModelManifest compatibility (no .create method or version param)
    return ModelManifest(
        model_name=model_name,
        model_hash=model_hash,
        model_public_key_pem=model_public_key_pem,
        creator_identity=creator_identity
    )

__all__ = [
    "SovereignIdentity",
    "SovereignCommunicator",
    "UnifiedDataPacket",
    "ModelManifest",
    "SovereignInferenceEngine",
    "SovereignPipeline",
    "AsyncInferenceEngineShim",
    "create_admin_server",
    "make_manifest",
]
