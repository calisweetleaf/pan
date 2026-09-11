"""
PAN Citizen Registry - The "SSN Office" of PAN
A sovereign, persistent registry for managing citizens, applications, and economic activities.
Integrates with DHT for decentralized storage and consensus.
Pulls storage logic from personal_data.py for persistent citizen profiles.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from .PAN_SDK import (
    SovereignIdentity, DHTNode, PANCitizenRegistry as BaseRegistry,
    PANEconomicEngine, PANConsensus, utc_now_iso, derive_uuid, PANPersistenceStore
)
from .personal_data import PANPersonalDataStore, UserPreferences, PANContact

logger = logging.getLogger("PANCitizenRegistry")
logger.setLevel(logging.INFO)


@dataclass
class CitizenProfile:
    """Enhanced citizen profile with personal data integration."""
    citizen_id: str
    identity_hash: str
    citizen_type: str = "standard"
    registration_time: str = field(default_factory=utc_now_iso)
    tokens: int = 0
    reputation_score: int = 100
    active_status: bool = True
    permissions: List[str] = field(default_factory=list)
    preferences: Optional[UserPreferences] = None
    contacts: List[PANContact] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "citizen_id": self.citizen_id,
            "identity_hash": self.identity_hash,
            "citizen_type": self.citizen_type,
            "registration_time": self.registration_time,
            "tokens": self.tokens,
            "reputation_score": self.reputation_score,
            "active_status": self.active_status,
            "permissions": self.permissions,
            "preferences": self.preferences.to_dict() if self.preferences else None,
            "contacts": [c.to_dict() for c in self.contacts],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CitizenProfile':
        preferences = UserPreferences.from_dict(data["preferences"]) if data.get("preferences") else None
        contacts = [PANContact.from_dict(c) for c in data.get("contacts", [])]
        return cls(
            citizen_id=data["citizen_id"],
            identity_hash=data["identity_hash"],
            citizen_type=data.get("citizen_type", "standard"),
            registration_time=data.get("registration_time", utc_now_iso()),
            tokens=data.get("tokens", 0),
            reputation_score=data.get("reputation_score", 100),
            active_status=data.get("active_status", True),
            permissions=data.get("permissions", []),
            preferences=preferences,
            contacts=contacts,
            metadata=data.get("metadata", {}),
        )


class PANCitizenRegistry(BaseRegistry):
    """Real PAN Citizen Registry - Sovereign management of citizens and apps."""
    
    def __init__(self, identity: SovereignIdentity, dht_node: DHTNode,
                 persistence: Optional[PANPersistenceStore] = None):
        super().__init__(identity, dht_node, persistence)
        self.personal_store = PANPersonalDataStore(self.identity.identity_hash, persistence=self.persistence)
        self.citizen_profiles: Dict[str, CitizenProfile] = {}
        self.citizens = self.citizen_profiles  # Alias for compatibility
        self._load_profiles()
        logger.info("PANCitizenRegistry initialized as real registry")
    
    def _load_profiles(self) -> None:
        """Load citizen profiles from persistent storage."""
        stored = self.persistence.load_component('citizen_profiles')
        for citizen_id, data in stored.items():
            self.citizen_profiles[citizen_id] = CitizenProfile.from_dict(data)
    
    def register_citizen(self, identity: SovereignIdentity, citizen_type: str = "standard",
                        registration_data: Dict[str, Any] = None) -> Optional[CitizenProfile]:
        """Register a new citizen with full profile persistence."""
        if identity.identity_hash in [p.identity_hash for p in self.citizen_profiles.values()]:
            logger.warning(f"Identity {identity.identity_hash[:12]} already registered")
            return None
        
        citizen_id = derive_uuid(f"citizen:{identity.identity_hash}")
        profile = CitizenProfile(
            citizen_id=citizen_id,
            identity_hash=identity.identity_hash,
            citizen_type=citizen_type,
            metadata=registration_data or {},
        )
        profile.preferences = self.personal_store.get_preferences()
        
        # Store in DHT with consensus
        success = self.dht_node.store(f"citizen:{citizen_id}", profile.to_dict(), require_consensus=True)
        if success:
            self.citizen_profiles[citizen_id] = profile
            self.persistence.write_state('citizen_profiles', citizen_id, profile.to_dict())
            logger.info(f"Registered citizen {citizen_id[:12]}")
            return profile
        logger.error(f"Failed to register citizen {citizen_id[:12]}")
        return None
    
    def get_citizen_profile(self, citizen_id: str) -> Optional[CitizenProfile]:
        """Retrieve a citizen profile."""
        return self.citizen_profiles.get(citizen_id)
    
    def update_citizen_profile(self, citizen_id: str, updates: Dict[str, Any]) -> bool:
        """Update a citizen profile."""
        profile = self.citizen_profiles.get(citizen_id)
        if not profile:
            return False
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        self.persistence.write_state('citizen_profiles', citizen_id, profile.to_dict())
        self.dht_node.store(f"citizen:{citizen_id}", profile.to_dict(), require_consensus=False)
        logger.info(f"Updated profile for citizen {citizen_id[:12]}")
        return True
    
    def transfer_tokens(self, sender_id: str, recipient_id: str, amount: int) -> Dict[str, Any]:
        """Handle token transfers between citizens."""
        sender = self.get_citizen_profile(sender_id)
        recipient = self.get_citizen_profile(recipient_id)
        if not sender or not recipient or sender.tokens < amount:
            return {"success": False, "error": "Invalid transfer"}
        
        sender.tokens -= amount
        recipient.tokens += amount
        self.update_citizen_profile(sender_id, {"tokens": sender.tokens})
        self.update_citizen_profile(recipient_id, {"tokens": recipient.tokens})
        
        # Use economic engine if available
        if hasattr(self.dht_node, 'economic_engine') and self.dht_node.economic_engine:
            return self.dht_node.economic_engine.transfer_tokens(sender_id, recipient_id, amount, "registry_transfer")
        return {"success": True, "amount": amount}
    
    def list_citizens(self, active_only: bool = True) -> List[CitizenProfile]:
        """List all citizens."""
        citizens = list(self.citizen_profiles.values())
        if active_only:
            citizens = [c for c in citizens if c.active_status]
        return citizens
    
    def deactivate_citizen(self, citizen_id: str) -> bool:
        """Deactivate a citizen."""
        return self.update_citizen_profile(citizen_id, {"active_status": False})


# Optional: Add a simple demo or CLI for the registry
if __name__ == "__main__":
    print("=== PAN Citizen Registry Demo ===")
    identity = SovereignIdentity("RegistryAdmin")
    dht = DHTNode(identity)
    registry = PANCitizenRegistry(identity, dht)
    
    # Example: Register a citizen
    user_identity = SovereignIdentity("TestCitizen")
    citizen = registry.register_citizen(user_identity, citizen_type="developer")
    if citizen:
        print(f"Registered citizen: {citizen.citizen_id[:12]}")
    else:
        print("Registration failed")
    
    print("=== Registry operations completed ===")