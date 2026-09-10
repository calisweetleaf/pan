"""
Enhanced Sovereign AI Infrastructure SDK
=========================================

Production-ready sovereign AI infrastructure with local API server,
API key management, and secure remote connection capabilities. Api server provides the local execution of data from PAN_SDK.
"""

import asyncio
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict, field
from pathlib import Path
import logging
import secrets
import hmac
from enum import Enum
from contextlib import asynccontextmanager
from collections import defaultdict

# Web server and networking
from fastapi import FastAPI, HTTPException, Depends, Security, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Cryptography
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Import core from PAN_SDK directly for full PAN integration (hashchains, ledger) (could load manifest .json to allow config because of the new `somnus-api` we are attaching. This is going to all orbit the PAN_SDK, for short explanation, this should use json style manifests that is served to and from. The local api is what allows my systems to be served and inferenced, but translated into the data-packet network, but in order to recieve calls back we still are going to allow back in. There is a new system that allows daeron to serve full apps over end to end thru https and the PAN)
from PAN_SDK import (
    SovereignIdentity as CoreSovereignIdentity,
    UnifiedDataPacket as CoreUnifiedDataPacket,
    SovereignCommunicator as CoreSovereignCommunicator,
    ModelManifest as CoreModelManifest,
    SovereignInferenceEngine as CoreSovereignInferenceEngine,
    SovereignPipeline,
    utc_now_iso,
    canonical,
    sha256_hex,
    derive_uuid,
    PANPersistenceStore,
    DHTNode,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --------------------------- #
# --------- Core Types --------#
# --------------------------- #

class PacketKind(Enum): # NEEDS MODEL INFERENCE REMOVED, REPLACED/INTEGRATED INTO MY MULTI AGENT COLLABORATION AND COMMUNICATION PROTOCOLS/SYSTEM
    INFERENCE_REQUEST = "INFERENCE_REQUEST"
    INFERENCE_RESPONSE = "INFERENCE_RESPONSE"
    MODEL_MANIFEST = "MODEL_MANIFEST"#OLD. MUST BE REMOVED.
    SYSTEM_STATUS = "SYSTEM_STATUS"
    AUTHENTICATION = "AUTHENTICATION"
    HEARTBEAT = "HEARTBEAT"
    ERROR = "ERROR"

class ConnectionType(Enum):
    LOCAL = "LOCAL"
    REMOTE_AUTHENTICATED = "REMOTE_AUTHENTICATED"
    PIPELINE = "PIPELINE"

class APIKeyScope(Enum):
    INFERENCE = "inference"
    ADMIN = "admin"
    PIPELINE = "pipeline"
    READ_ONLY = "read_only"

# --------------------------- #
# --------- Utilities --------#
# --------------------------- #

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def canonical(obj) -> str:
    """Deterministic JSON for hashing. No whitespace, sorted keys."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)

def sha256_hex(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def derive_uuid(prefix: str = "") -> str:
    """Namespaced deterministic UUID if prefix provided; random otherwise."""
    if prefix:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, prefix))
    return str(uuid.uuid4())

def secure_random_hex(length: int = 32) -> str:
    """Generate cryptographically secure random hex string."""
    return secrets.token_hex(length)

# -----------------------------------  #
# --------- API Key Management --------#
# -----------------------------------  #

@dataclass
class APIKey:
    key_id: str
    key_hash: str
    name: str
    scopes: List[APIKeyScope]
    created_at: str
    expires_at: Optional[str] = None
    last_used: Optional[str] = None
    usage_count: int = 0
    rate_limit_per_hour: int = 1000
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now(timezone.utc)
    
    def has_scope(self, scope: APIKeyScope) -> bool:
        return scope in self.scopes
    
    def can_use(self) -> bool:
        return not self.is_expired()

class APIKeyManager:
    """Manages API keys with rate limiting and scope-based authorization."""
    
    def __init__(self):
        self.keys: Dict[str, APIKey] = {}
        self.usage_tracking: Dict[str, List[datetime]] = defaultdict(list)
        logger.info("APIKeyManager initialized")
    
    def create_key(self, name: str, scopes: List[APIKeyScope], 
                   expires_hours: Optional[int] = None,
                   rate_limit_per_hour: int = 1000) -> tuple[str, APIKey]:
        """Create a new API key and return the raw key and key object."""
        raw_key = f"sk-{secure_random_hex(24)}"
        key_hash = sha256_hex(raw_key)
        key_id = f"key_{secure_random_hex(8)}"
        
        expires_at = None
        if expires_hours:
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            scopes=scopes,
            created_at=utc_now_iso(),
            expires_at=expires_at,
            rate_limit_per_hour=rate_limit_per_hour
        )
        
        self.keys[key_id] = api_key
        logger.info(f"Created API key {key_id} for {name} with scopes: {[s.value for s in scopes]}")
        return raw_key, api_key
    
    def verify_key(self, raw_key: str) -> Optional[APIKey]:
        """Verify a raw API key and return the APIKey object if valid."""
        key_hash = sha256_hex(raw_key)
        
        for api_key in self.keys.values():
            if api_key.key_hash == key_hash and api_key.can_use():
                return api_key
        
        return None
    
    def check_rate_limit(self, api_key: APIKey) -> bool:
        """Check if the API key is within rate limits."""
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        # Clean old usage records
        self.usage_tracking[api_key.key_id] = [
            usage for usage in self.usage_tracking[api_key.key_id] 
            if usage > hour_ago
        ]
        
        current_usage = len(self.usage_tracking[api_key.key_id])
        return current_usage < api_key.rate_limit_per_hour
    
    def record_usage(self, api_key: APIKey):
        """Record usage of an API key."""
        now = datetime.now(timezone.utc)
        self.usage_tracking[api_key.key_id].append(now)
        api_key.usage_count += 1
        api_key.last_used = now.isoformat()
    
    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        if key_id in self.keys:
            del self.keys[key_id]
            if key_id in self.usage_tracking:
                del self.usage_tracking[key_id]
            logger.info(f"Revoked API key {key_id}")
            return True
        return False

# --------------------------- #
# --------- Enhanced Identity (PAN-Aligned) --------#
# --------------------------- #

class SovereignIdentity(CoreSovereignIdentity):
    """Enhanced cryptographic identity with session management and PAN hashchain integration."""
    
    def __init__(self, name: str, private_key_pem: Optional[bytes] = None,
                 connection_type: ConnectionType = ConnectionType.LOCAL,
                 hashchain_parent: Optional[str] = None):
        super().__init__(name, private_key_pem, hashchain_parent=hashchain_parent)
        self.connection_type = connection_type
        self.session_id = derive_uuid()
        self.last_activity = utc_now_iso()

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = utc_now_iso()

    def create_hashchain_entry(self, data: Dict[str, Any]) -> str:
        """Create a new entry in the hashchain with the given data (PAN ledger compatible)."""
        return super().create_hashchain_entry(data)

    def verify_hashchain_entry(self, entry_hash: str, data: Dict[str, Any], 
                              previous_hash: str) -> bool:
        """Verify that an entry is valid in the hashchain (PAN ledger compatible)."""
        return super().verify_hashchain_entry(entry_hash, data, previous_hash)

# --------------------------- #
# --------- Enhanced Data Packet (PAN-Aligned) --------#
# --------------------------- #

@dataclass
class UnifiedDataPacket(CoreUnifiedDataPacket):
    """Enhanced universal data packet with routing, priority, and PAN ledger integration."""
    
    # Existing fields from Core...
    destination_identity_hash: Optional[str] = None
    priority: int = 5  # 1-10, 10 being highest
    ttl: int = 3600  # Time to live in seconds
    
    def __post_init__(self):
        super().__post_init__()
        # Ensure ledger compatibility
        if not self.previous_hash:
            self.previous_hash = self.author_identity_hash  # Default to author for genesis
        if not self.sequence_number:
            self.sequence_number = 1  # Default sequence

    def verify_ledger_link(self, expected_previous_hash: Optional[str] = None) -> bool:
        """Verify PAN ledger chain integrity."""
        return super().verify_ledger_link(expected_previous_hash)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "destination_identity_hash": self.destination_identity_hash,
            "priority": self.priority,
            "ttl": self.ttl,
        })
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedDataPacket':
        data["signature"] = bytes.fromhex(data["signature"]) if data.get("signature") else bytes()
        return cls(**data)

# --------------------------- #
# --------- Enhanced Communicator (PAN-Aligned) --------#
# --------------------------- #

class SovereignCommunicator(CoreSovereignCommunicator):
    """Enhanced secure communication with message queuing, routing, and PAN DHT integration."""
    
    def __init__(self, identity: SovereignIdentity, dht_node: Optional[DHTNode] = None):
        super().__init__(identity)
        self.message_queue: List[UnifiedDataPacket] = []
        self.sent_packets: Dict[str, UnifiedDataPacket] = {}
        self.routing_table: Dict[str, str] = {}  # identity_hash -> endpoint
        self.dht_node = dht_node

    def create_packet(self, kind: PacketKind, content: Dict[str, Any], 
                     parents: List[str] = None, metadata: Dict[str, Any] = None,
                     destination: Optional[str] = None, priority: int = 5) -> UnifiedDataPacket:
        """Create a signed data packet with PAN ledger linking."""
        packet = super().create_packet(kind, content, parents, metadata)
        packet.destination_identity_hash = destination
        packet.priority = priority
        
        # Link to ledger if DHT available
        if self.dht_node:
            ledger_entry = {
                "packet_id": packet.packet_id,
                "kind": kind.value,
                "author": self.identity.identity_hash,
                "timestamp": packet.timestamp,
            }
            packet.previous_hash = self.identity.create_hashchain_entry(ledger_entry)
            self.dht_node.store(f"packet:{packet.packet_id}", packet.to_dict())
        
        self.sent_packets[packet.packet_id] = packet
        self.identity.update_activity()
        self.queue_packet(packet)
        logger.debug(f"Created {kind.value} packet: {packet.packet_id[:12]}")
        return packet

    def verify_packet(self, packet: UnifiedDataPacket, author_public_key_pem: bytes) -> bool:
        """Verify a packet's signature, integrity, and PAN ledger link."""
        if not super().verify_packet(packet, author_public_key_pem):
            return False
        if packet.is_expired():
            logger.warning(f"Packet {packet.packet_id[:12]} has expired")
            return False
        if self.dht_node and not packet.verify_ledger_link():
            logger.warning(f"Packet {packet.packet_id[:12]} failed ledger verification")
            return False
        return True

    def queue_packet(self, packet: UnifiedDataPacket):
        """Queue a packet for processing, sorted by priority."""
        self.message_queue.append(packet)
        self.message_queue.sort(key=lambda p: p.priority, reverse=True)

    def get_next_packet(self) -> Optional[UnifiedDataPacket]:
        """Get the next packet from the queue."""
        return self.message_queue.pop(0) if self.message_queue else None

# --------------------------- #
# --------- Model Manifest (PAN-Aligned) --------#
# --------------------------- #

class ModelManifest(CoreModelManifest):
    """Enhanced model manifest with versioning and capabilities (direct init for PAN compat)."""
    
    def __init__(self, model_name: str, model_hash: str, model_public_key_pem: bytes,
                 creator_identity: SovereignIdentity, model_version: str = "1.0.0",
                 capabilities: List[str] = field(default_factory=list),
                 model_size_bytes: int = 0, quantization_method: str = "proprietary_v2",
                 supported_formats: List[str] = field(default_factory=lambda: ["lacka"]),
                 metadata: Dict[str, Any] = field(default_factory=dict)):
        super().__init__(model_name, model_hash, model_public_key_pem, creator_identity)
        self.model_version = model_version
        self.capabilities = capabilities
        self.model_size_bytes = model_size_bytes
        self.quantization_method = quantization_method
        self.supported_formats = supported_formats
        self.metadata = metadata

    @classmethod
    def create(cls, model_name: str, model_hash: str, model_version: str,
               model_public_key_pem: bytes, creator_identity: SovereignIdentity,
               **kwargs) -> 'ModelManifest':
        """Create a new signed manifest (PAN ledger compatible)."""
        # Ignore unsupported kwargs for PAN compat
        manifest = cls(
            model_name=model_name,
            model_hash=model_hash,
            model_public_key_pem=model_public_key_pem,
            creator_identity=creator_identity,
            model_version=model_version,
            **{k: v for k, v in kwargs.items() if k in ['capabilities', 'model_size_bytes', 'quantization_method', 'supported_formats', 'metadata']}
        )
        # Link to ledger if available (via creator)
        ledger_entry = {"manifest_hash": manifest.content_hash, "model_name": model_name}
        creator_identity.create_hashchain_entry(ledger_entry)
        return manifest

# --------------------------- #
# --------- Enhanced Inference Engine (PAN-Aligned) --------#
# --------------------------- #

class SovereignInferenceEngine(CoreSovereignInferenceEngine):
    """Enhanced inference engine with async processing, monitoring, and PAN ledger signing."""
    
    def __init__(self, model_path: str, model_manifest: ModelManifest,
                 max_concurrent_requests: int = 4, dht_node: Optional[DHTNode] = None):
        super().__init__(model_path, model_manifest)
        self.max_concurrent_requests = max_concurrent_requests
        self.dht_node = dht_node
        self.processing_queue = asyncio.Queue()
        self.active_requests = 0
        self.total_requests = 0
        self.total_tokens_processed = 0

    async def load_model(self):
        """Async model loading with PAN ledger record."""
        if self.loaded:
            return
        logger.info(f"Loading model from {self.model_path}")
        await asyncio.sleep(0.5)  # Simulate
        self.loaded = True
        if self.dht_node:
            load_entry = {"model_name": self.model_manifest.model_name, "status": "loaded"}
            self.dht_node.store("model_load", load_entry)
        logger.info("Model loaded successfully")

    async def process_request_async(self, request_packet: UnifiedDataPacket, 
                                  user_public_key_pem: bytes) -> UnifiedDataPacket:
        """Process an inference request asynchronously with PAN ledger."""
        if not self.loaded:
            await self.load_model()
        if self.active_requests >= self.max_concurrent_requests:
            raise RuntimeError("Too many concurrent requests")
        self.active_requests += 1
        self.total_requests += 1
        
        try:
            prompt = request_packet.content.get("prompt", "")
            temperature = request_packet.content.get("temperature", 0.7)
            max_tokens = request_packet.content.get("max_tokens", 100)
            
            logger.info(f"Processing inference request: {prompt[:50]}...")
            
            start_time = time.time()
            response_text = await self._run_inference_async(prompt, temperature, max_tokens)
            processing_time = int((time.time() - start_time) * 1000)
            
            input_tokens = len(prompt.split())
            output_tokens = len(response_text.split())
            self.total_tokens_processed += input_tokens + output_tokens
            
            response_content = {
                "response": response_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "processing_time_ms": processing_time,
                "model_name": self.model_manifest.model_name,
                "engine_stats": {
                    "total_requests": self.total_requests,
                    "total_tokens_processed": self.total_tokens_processed,
                    "active_requests": self.active_requests
                }
            }
            
            response_packet = UnifiedDataPacket(
                packet_id="",
                kind=PacketKind.INFERENCE_RESPONSE,
                content=response_content,
                author_identity_hash=self.model_manifest.creator_identity_hash,
                timestamp=utc_now_iso(),
                parents=[request_packet.packet_id],
                metadata={"processing_node": "local_engine"},
                previous_hash=request_packet.ledger_hash,  # Link to request ledger
                sequence_number=request_packet.sequence_number + 1 if request_packet.sequence_number else 1
            )
            
            # Sign response (using manifest creator for simplicity)
            response_data = canonical(response_packet.to_dict()).encode('utf-8')
            response_packet.signature = self.model_manifest.creator_identity.sign(response_data)  # Assume access
            
            # Store in PAN ledger if available
            if self.dht_node:
                self.dht_node.store(f"response:{response_packet.packet_id}", response_packet.to_dict())
            
            logger.info(f"Inference completed in {processing_time}ms")
            return response_packet
            
        finally:
            self.active_requests -= 1

    def process_request(self, request_packet: UnifiedDataPacket, 
                       user_public_key_pem: bytes) -> UnifiedDataPacket:
        """Sync fallback with async delegation."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.process_request_async(request_packet, user_public_key_pem))

    async def _run_inference_async(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Simulate async model inference."""
        await asyncio.sleep(0.1)
        return f"Enhanced response to: {prompt[:50]}... (processed with proprietary quantization v2.0)"

# Override with PAN-aligned implementations (no fallback needed as they extend core)
SovereignIdentity = SovereignIdentity
UnifiedDataPacket = UnifiedDataPacket
SovereignCommunicator = SovereignCommunicator
ModelManifest = ModelManifest
SovereignInferenceEngine = SovereignInferenceEngine

# --------------------------- #
# --------- Local API Server (PAN-Integrated) --------#
# --------------------------- #

class SovereignAPIServer:
    """Local API server for sovereign AI infrastructure with optional PAN DHT integration."""
    
    def __init__(self, port: int = 8000, host: str = "127.0.0.1", dht_node: Optional[DHTNode] = None):
        self.port = port
        self.host = host
        self.dht_node = dht_node
        self.app = FastAPI(
            title="Sovereign AI Infrastructure API",
            description="Local API for sovereign AI systems with PAN integration",
            version="2.0.0"
        )
        
        self.api_key_manager = APIKeyManager()
        self.security = HTTPBearer()
        self.identities: Dict[str, SovereignIdentity] = {}
        self.communicators: Dict[str, SovereignCommunicator] = {}
        self.inference_engine: Optional[SovereignInferenceEngine] = None
        
        self._setup_middleware()
        self._setup_routes()
        logger.info(f"SovereignAPIServer initialized on {host}:{port} with PAN DHT: {bool(dht_node)}")

    def _setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Adjust as needed
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    async def get_api_key(self, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Dependency to verify API key."""
        api_key = self.api_key_manager.verify_key(credentials.credentials)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        if not self.api_key_manager.check_rate_limit(api_key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        self.api_key_manager.record_usage(api_key)
        return api_key

    def require_scope(self, required_scope: APIKeyScope):
        """Dependency factory for scope-based authorization."""
        async def check_scope(api_key: APIKey = Depends(self.get_api_key)):
            if not api_key.has_scope(required_scope):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required scope: {required_scope.value}"
                )
            return api_key
        return check_scope

    def _setup_routes(self):
        """Setup API routes with PAN ledger support."""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": utc_now_iso(),
                "version": "2.0.0"
            }

        @self.app.post("/admin/api-keys")
        async def create_api_key(
            request: Dict[str, Any],
            api_key: APIKey = Depends(self.require_scope(APIKeyScope.ADMIN))
        ):
            """Create a new API key."""
            name = request.get("name", "unnamed")
            scopes = [APIKeyScope(s) for s in request.get("scopes", ["inference"])]
            expires_hours = request.get("expires_hours")
            rate_limit = request.get("rate_limit_per_hour", 1000)
            
            raw_key, key_obj = self.api_key_manager.create_key(
                name, scopes, expires_hours, rate_limit
            )
            
            return {
                "key": raw_key,
                "key_id": key_obj.key_id,
                "name": key_obj.name,
                "scopes": [s.value for s in key_obj.scopes],
                "created_at": key_obj.created_at,
                "expires_at": key_obj.expires_at
            }

        @self.app.delete("/admin/api-keys/{key_id}")
        async def revoke_api_key(
            key_id: str,
            api_key: APIKey = Depends(self.require_scope(APIKeyScope.ADMIN))
        ):
            """Revoke an API key."""
            success = self.api_key_manager.revoke_key(key_id)
            if not success:
                raise HTTPException(status_code=404, detail="API key not found")
            return {"message": f"API key {key_id} revoked"}

        @self.app.post("/inference")
        async def inference_request(
            request: Dict[str, Any],
            api_key: APIKey = Depends(self.require_scope(APIKeyScope.INFERENCE))
        ):
            """Process an inference request with PAN ledger recording."""
            if not self.inference_engine:
                raise HTTPException(status_code=503, detail="Inference engine not available")
            
            # Create identity for this request if needed
            user_identity = self.identities.get(api_key.key_id)
            if not user_identity:
                user_identity = SovereignIdentity(
                    f"api_user_{api_key.key_id}",
                    connection_type=ConnectionType.REMOTE_AUTHENTICATED
                )
                self.identities[api_key.key_id] = user_identity
                communicator = SovereignCommunicator(user_identity, dht_node=self.dht_node)
                self.communicators[api_key.key_id] = communicator
            else:
                communicator = self.communicators[api_key.key_id]
            
            # Create request packet with ledger
            request_packet = communicator.create_packet(
                kind=PacketKind.INFERENCE_REQUEST,
                content={
                    "prompt": request.get("prompt", ""),
                    "temperature": request.get("temperature", 0.7),
                    "max_tokens": request.get("max_tokens", 100),
                    "stream": request.get("stream", False)
                },
                metadata={
                    "api_key_id": api_key.key_id,
                    "client_info": request.get("client_info", {})
                }
            )
            
            # Process request
            try:
                response_packet = await self.inference_engine.process_request_async(
                    request_packet, user_identity.get_public_key_pem()
                )
                
                return {
                    "response": response_packet.content["response"],
                    "usage": {
                        "input_tokens": response_packet.content.get("input_tokens", 0),
                        "output_tokens": response_packet.content.get("output_tokens", 0),
                        "processing_time_ms": response_packet.content.get("processing_time_ms", 0)
                    },
                    "model": response_packet.content.get("model_name", "unknown"),
                    "packet_id": response_packet.packet_id,
                    "ledger_hash": response_packet.ledger_hash  # Expose PAN ledger info
                }
            except Exception as e:
                logger.error(f"Inference request failed: {e}")
                raise HTTPException(status_code=500, detail="Inference request failed")

        @self.app.get("/status")
        async def system_status(
            api_key: APIKey = Depends(self.require_scope(APIKeyScope.READ_ONLY))
        ):
            """Get system status."""
            return {
                "system": "sovereign_ai_infrastructure",
                "version": "2.0.0",
                "status": "operational",
                "timestamp": utc_now_iso(),
                "active_identities": len(self.identities),
                "inference_engine": "available" if self.inference_engine else "unavailable",
                "api_keys": len(self.api_key_manager.keys)
            }

    def set_inference_engine(self, engine: SovereignInferenceEngine):
        """Set the inference engine with optional DHT."""
        if self.dht_node:
            engine.dht_node = self.dht_node
        self.inference_engine = engine
        logger.info("Inference engine attached to API server")

    async def start(self):
        """Start the API server."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    def create_admin_key(self) -> tuple[str, APIKey]:
        """Create an admin API key for initial setup."""
        return self.api_key_manager.create_key(
            "admin",
            [APIKeyScope.ADMIN, APIKeyScope.INFERENCE, APIKeyScope.READ_ONLY],
            expires_hours=None,
            rate_limit_per_hour=10000
        )

# --------------------------- #
# --------- Demo Runner --------#
# --------------------------- #

async def demo_enhanced_infrastructure():
    """Comprehensive demo of the enhanced infrastructure."""
    print("=== Enhanced Sovereign AI Infrastructure Demo ===\n")
    
    # 1. Create identities
    print("1. Creating sovereign identities...")
    user_identity = SovereignIdentity("UserApp", connection_type=ConnectionType.LOCAL)
    model_identity = SovereignIdentity("AI_Model_Enhanced")
    
    # 2. Initialize API server
    print("2. Initializing API server...")
    api_server = SovereignAPIServer(port=8001)
    
    # Create initial admin key
    admin_key, admin_key_obj = api_server.create_admin_key()
    print(f"   Admin API Key: {admin_key}")
    
    # 3. Create model manifest
    print("3. Creating enhanced model manifest...")
    manifest = ModelManifest.create(
        model_name="gemma3-enhanced-4b",
        model_hash=sha256_hex("enhanced_model_data"),
        model_version="2.1.0",
        model_public_key_pem=model_identity.get_public_key_pem(),
        creator_identity=user_identity,
        capabilities=["text_generation", "reasoning", "code"],
        model_size_bytes=4_000_000_000,
        quantization_method="proprietary_v2.1"
    )
    
    # 4. Initialize inference engine
    print("4. Initializing enhanced inference engine...")
    engine = SovereignInferenceEngine("/path/to/enhanced-model.lacka", manifest)
    api_server.set_inference_engine(engine)
    
    # 5. Test local inference
    print("5. Testing direct inference...")
    communicator = SovereignCommunicator(user_identity)
    request_packet = communicator.create_packet(
        kind=PacketKind.INFERENCE_REQUEST,
        content={
            "prompt": "Explain the advantages of enhanced sovereign AI systems",
            "temperature": 0.8,
            "max_tokens": 200
        }
    )
    
    response_packet = await engine.process_request_async(
        request_packet, user_identity.get_public_key_pem()
    )
    
    print(f"   Response: {response_packet.content['response']}")
    print(f"   Processing time: {response_packet.content['processing_time_ms']}ms\n")
    
    print("6. Enhanced infrastructure ready!")
    print(f"   API Server: http://127.0.0.1:8001")
    print(f"   Admin Key: {admin_key}")
    print("   Endpoints: /health, /status, /inference, /admin/api-keys")
    print("\n=== Demo completed successfully ===")

if __name__ == "__main__":
    asyncio.run(demo_enhanced_infrastructure())
