"""
PAN SDK - Personal Data Layer
Manages contacts, messages, call logs, and user data for sovereign phone identities.

ARCHITECTURE NOTE:
- This is STANDALONE storage for phone/contact data (SQLite)
- VM Memory System (memory_core.py) is SEPARATE - used for VM session persistence
- V1: Simple infrastructure with "unusable" PAN addresses to build hype
- V2: Full featured communication network integration

This layer stores:
- Contact books (per sovereign identity)
- Message/SMS history
- Call logs (voice/video)
- User preferences
- PAN phone address registry
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict, fields
import logging

from .PAN_SDK import (
    SovereignIdentity,
    PANPersistenceStore,
    utc_now_iso,
    canonical,
    sha256_hex,
    derive_uuid,
)

logger = logging.getLogger(__name__)


# ==================== Contact Book System ====================

@dataclass
class PANContact:
    """Represents a contact entry in a user's phone book."""
    contact_id: str
    owner_sovereign_id: str  # Who owns this contact entry
    display_name: str
    pan_phone_address: Optional[str] = None  # pan:[network]:[motif]:voice
    phone_numbers: List[str] = field(default_factory=list)  # Traditional numbers
    email_addresses: List[str] = field(default_factory=list)
    profile_picture_uri: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    favorite: bool = False
    blocked: bool = False
    created_at: str = field(default_factory=utc_now_iso)
    last_modified: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PANContact':
        return cls(**data)


@dataclass
class PANMessage:
    """Represents a message (SMS/chat) in conversation history."""
    message_id: str
    conversation_id: str  # Groups messages together
    sender_sovereign_id: str
    recipient_sovereign_id: str
    message_type: str  # "sms", "chat", "voice_transcript", "media"
    content: str
    media_attachments: List[str] = field(default_factory=list)  # URIs to media
    timestamp: str = field(default_factory=utc_now_iso)
    read: bool = False
    delivered: bool = False
    encrypted: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PANMessage':
        return cls(**data)


@dataclass
class PANCallLog:
    """Represents a voice/video call record."""
    call_id: str
    caller_sovereign_id: str
    recipient_sovereign_id: str
    call_type: str  # "voice", "video", "conference"
    direction: str  # "outgoing", "incoming", "missed"
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: int = 0
    call_quality: Optional[str] = None  # "excellent", "good", "poor"
    recording_uri: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PANCallLog':
        return cls(**data)


@dataclass
class UserPreferences:
    """Per-user settings and preferences."""
    user_sovereign_id: str
    theme: str = "dark"
    notification_enabled: bool = True
    default_message_encryption: bool = True
    auto_sync: bool = True
    backup_enabled: bool = True
    language: str = "en"
    vm_preferences: Dict[str, Any] = field(default_factory=dict)
    app_settings: Dict[str, Any] = field(default_factory=dict)
    privacy_settings: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserPreferences':
        return cls(**data)


# ==================== Personal Data Store ====================

class PANPersonalDataStore:
    """
    Manages personal data storage for sovereign identities.
    Each user gets their own encrypted contact book, message history, and preferences.
    """
    
    def __init__(
        self,
        sovereign_id: str,
        base_path: Optional[Path] = None,
        persistence: Optional[PANPersistenceStore] = None,
    ):
        self.sovereign_id = sovereign_id
        self.base_path = base_path or Path("pan_data") / "users" / sovereign_id[:12]
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.persistence = persistence or PANPersistenceStore(
            base_path=self.base_path,
            db_filename="personal_data.db"
        )
        
        self._lock = threading.RLock()
        self._init_schema()
        
        # In-memory caches
        self.contacts: Dict[str, PANContact] = {}
        self.messages: Dict[str, PANMessage] = {}
        self.call_logs: Dict[str, PANCallLog] = {}
        self.preferences: Optional[UserPreferences] = None
        
        self._load_from_persistence()
        
        logger.info(f"PANPersonalDataStore initialized for sovereign {sovereign_id[:12]}")
    
    def _init_schema(self) -> None:
        """Initialize database schema for personal data."""
        conn = sqlite3.connect(self.base_path / "personal_data.db")
        with conn:
            # Contacts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    contact_id TEXT PRIMARY KEY,
                    owner_sovereign_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    pan_phone_address TEXT,
                    phone_numbers TEXT,
                    email_addresses TEXT,
                    profile_picture_uri TEXT,
                    notes TEXT,
                    tags TEXT,
                    favorite INTEGER DEFAULT 0,
                    blocked INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_modified TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    sender_sovereign_id TEXT NOT NULL,
                    recipient_sovereign_id TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    media_attachments TEXT,
                    timestamp TEXT NOT NULL,
                    read INTEGER DEFAULT 0,
                    delivered INTEGER DEFAULT 0,
                    encrypted INTEGER DEFAULT 1,
                    metadata TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation ON messages(conversation_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)")
            
            # Call logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS call_logs (
                    call_id TEXT PRIMARY KEY,
                    caller_sovereign_id TEXT NOT NULL,
                    recipient_sovereign_id TEXT NOT NULL,
                    call_type TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds INTEGER DEFAULT 0,
                    call_quality TEXT,
                    recording_uri TEXT,
                    notes TEXT,
                    metadata TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_call_time ON call_logs(start_time)")
            
            # User preferences table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_sovereign_id TEXT PRIMARY KEY,
                    theme TEXT DEFAULT 'dark',
                    notification_enabled INTEGER DEFAULT 1,
                    default_message_encryption INTEGER DEFAULT 1,
                    auto_sync INTEGER DEFAULT 1,
                    backup_enabled INTEGER DEFAULT 1,
                    language TEXT DEFAULT 'en',
                    vm_preferences TEXT,
                    app_settings TEXT,
                    privacy_settings TEXT
                )
            """)
        conn.close()
    
    def _load_from_persistence(self) -> None:
        """Load cached data from persistence layer."""
        conn = sqlite3.connect(self.base_path / "personal_data.db")
        conn.row_factory = sqlite3.Row
        
        # Load contacts
        cursor = conn.execute("SELECT * FROM contacts WHERE owner_sovereign_id = ?", (self.sovereign_id,))
        for row in cursor:
            contact_data = dict(row)
            # Deserialize JSON fields
            contact_data['phone_numbers'] = json.loads(contact_data.get('phone_numbers') or '[]')
            contact_data['email_addresses'] = json.loads(contact_data.get('email_addresses') or '[]')
            contact_data['tags'] = json.loads(contact_data.get('tags') or '[]')
            contact_data['metadata'] = json.loads(contact_data.get('metadata') or '{}')
            contact_data['favorite'] = bool(contact_data['favorite'])
            contact_data['blocked'] = bool(contact_data['blocked'])
            
            contact = PANContact.from_dict(contact_data)
            self.contacts[contact.contact_id] = contact
        
        # Load preferences
        cursor = conn.execute("SELECT * FROM user_preferences WHERE user_sovereign_id = ?", (self.sovereign_id,))
        row = cursor.fetchone()
        if row:
            pref_data = dict(row)
            pref_data['notification_enabled'] = bool(pref_data['notification_enabled'])
            pref_data['default_message_encryption'] = bool(pref_data['default_message_encryption'])
            pref_data['auto_sync'] = bool(pref_data['auto_sync'])
            pref_data['backup_enabled'] = bool(pref_data['backup_enabled'])
            pref_data['vm_preferences'] = json.loads(pref_data.get('vm_preferences') or '{}')
            pref_data['app_settings'] = json.loads(pref_data.get('app_settings') or '{}')
            pref_data['privacy_settings'] = json.loads(pref_data.get('privacy_settings') or '{}')
            self.preferences = UserPreferences.from_dict(pref_data)
        else:
            self.preferences = UserPreferences(user_sovereign_id=self.sovereign_id)
            self.save_preferences(self.preferences)
        
        logger.debug(f"Loaded {len(self.contacts)} contacts for {self.sovereign_id[:12]}")

        cursor = conn.execute("SELECT * FROM messages")
        for row in cursor:
            msg_data = dict(row)
            msg_data['media_attachments'] = json.loads(msg_data.get('media_attachments') or '[]')
            msg_data['metadata'] = json.loads(msg_data.get('metadata') or '{}')
            msg_data['read'] = bool(msg_data['read'])
            msg_data['delivered'] = bool(msg_data['delivered'])
            msg_data['encrypted'] = bool(msg_data['encrypted'])
            allowed = {item.name for item in fields(PANMessage)}
            message = PANMessage.from_dict({k: v for k, v in msg_data.items() if k in allowed})
            self.messages[message.message_id] = message

        cursor = conn.execute("SELECT * FROM call_logs")
        for row in cursor:
            call_data = dict(row)
            call_data['metadata'] = json.loads(call_data.get('metadata') or '{}')
            allowed = {item.name for item in fields(PANCallLog)}
            call_log = PANCallLog.from_dict({k: v for k, v in call_data.items() if k in allowed})
            self.call_logs[call_log.call_id] = call_log

        conn.close()
        logger.debug(
            "Loaded %s contacts, %s messages, %s call logs for %s",
            len(self.contacts),
            len(self.messages),
            len(self.call_logs),
            self.sovereign_id[:12],
        )
    
    # ==================== Contact Management ====================
    
    def add_contact(
        self,
        display_name: str,
        pan_phone_address: Optional[str] = None,
        phone_numbers: Optional[List[str]] = None,
        email_addresses: Optional[List[str]] = None,
        **kwargs
    ) -> PANContact:
        """Add a new contact to the phone book."""
        with self._lock:
            contact_id = derive_uuid(f"contact:{self.sovereign_id}:{display_name}")
            
            contact = PANContact(
                contact_id=contact_id,
                owner_sovereign_id=self.sovereign_id,
                display_name=display_name,
                pan_phone_address=pan_phone_address,
                phone_numbers=phone_numbers or [],
                email_addresses=email_addresses or [],
                **kwargs
            )
            
            self.contacts[contact_id] = contact
            self._persist_contact(contact)
            
            logger.info(f"Added contact {display_name} ({contact_id[:12]}) for {self.sovereign_id[:12]}")
            return contact
    
    def update_contact(self, contact_id: str, **updates) -> bool:
        """Update an existing contact."""
        with self._lock:
            contact = self.contacts.get(contact_id)
            if not contact:
                logger.warning(f"Contact {contact_id[:12]} not found")
                return False
            
            for key, value in updates.items():
                if hasattr(contact, key):
                    setattr(contact, key, value)
            
            contact.last_modified = utc_now_iso()
            self._persist_contact(contact)
            
            logger.info(f"Updated contact {contact_id[:12]}")
            return True
    
    def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact from the phone book."""
        with self._lock:
            if contact_id not in self.contacts:
                return False
            
            del self.contacts[contact_id]
            
            conn = sqlite3.connect(self.base_path / "personal_data.db")
            with conn:
                conn.execute("DELETE FROM contacts WHERE contact_id = ?", (contact_id,))
            conn.close()
            
            logger.info(f"Deleted contact {contact_id[:12]}")
            return True
    
    def get_contact(self, contact_id: str) -> Optional[PANContact]:
        """Retrieve a contact by ID."""
        return self.contacts.get(contact_id)
    
    def search_contacts(self, query: str) -> List[PANContact]:
        """Search contacts by name, phone, or email."""
        query_lower = query.lower()
        results = []
        
        for contact in self.contacts.values():
            if (query_lower in contact.display_name.lower() or
                any(query_lower in phone for phone in contact.phone_numbers) or
                any(query_lower in email for email in contact.email_addresses) or
                (contact.pan_phone_address and query_lower in contact.pan_phone_address.lower())):
                results.append(contact)
        
        return results
    
    def list_contacts(self, favorites_only: bool = False) -> List[PANContact]:
        """List all contacts, optionally filtered by favorites."""
        contacts = list(self.contacts.values())
        if favorites_only:
            contacts = [c for c in contacts if c.favorite]
        return sorted(contacts, key=lambda c: c.display_name)
    
    def _persist_contact(self, contact: PANContact) -> None:
        """Persist a contact to database."""
        conn = sqlite3.connect(self.base_path / "personal_data.db")
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO contacts (
                    contact_id, owner_sovereign_id, display_name, pan_phone_address,
                    phone_numbers, email_addresses, profile_picture_uri, notes, tags,
                    favorite, blocked, created_at, last_modified, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                contact.contact_id,
                contact.owner_sovereign_id,
                contact.display_name,
                contact.pan_phone_address,
                json.dumps(contact.phone_numbers),
                json.dumps(contact.email_addresses),
                contact.profile_picture_uri,
                contact.notes,
                json.dumps(contact.tags),
                int(contact.favorite),
                int(contact.blocked),
                contact.created_at,
                contact.last_modified,
                json.dumps(contact.metadata)
            ))
        conn.close()
    
    # ==================== Message Management ====================
    
    def send_message(
        self,
        recipient_sovereign_id: str,
        content: str,
        message_type: str = "chat",
        media_attachments: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
    ) -> PANMessage:
        """Send a message and record it in history."""
        with self._lock:
            message_id = derive_uuid(f"msg:{self.sovereign_id}:{utc_now_iso()}")
            
            # Generate conversation ID if not provided
            if not conversation_id:
                participants = sorted([self.sovereign_id, recipient_sovereign_id])
                conversation_id = sha256_hex(":".join(participants))[:16]
            
            message = PANMessage(
                message_id=message_id,
                conversation_id=conversation_id,
                sender_sovereign_id=self.sovereign_id,
                recipient_sovereign_id=recipient_sovereign_id,
                message_type=message_type,
                content=content,
                media_attachments=media_attachments or [],
                delivered=True,  # Assume delivery for now
            )
            
            self.messages[message_id] = message
            self._persist_message(message)
            
            logger.info(f"Sent message {message_id[:12]} to {recipient_sovereign_id[:12]}")
            return message
    
    def receive_message(self, message: PANMessage) -> None:
        """Receive and store an incoming message."""
        with self._lock:
            self.messages[message.message_id] = message
            self._persist_message(message)
            logger.info(f"Received message {message.message_id[:12]} from {message.sender_sovereign_id[:12]}")
    
    def get_conversation(self, conversation_id: str, limit: int = 100) -> List[PANMessage]:
        """Get messages from a conversation."""
        conn = sqlite3.connect(self.base_path / "personal_data.db")
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT * FROM messages 
            WHERE conversation_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (conversation_id, limit))
        
        messages = []
        for row in cursor:
            msg_data = dict(row)
            msg_data['media_attachments'] = json.loads(msg_data.get('media_attachments') or '[]')
            msg_data['metadata'] = json.loads(msg_data.get('metadata') or '{}')
            msg_data['read'] = bool(msg_data['read'])
            msg_data['delivered'] = bool(msg_data['delivered'])
            msg_data['encrypted'] = bool(msg_data['encrypted'])
            messages.append(PANMessage.from_dict(msg_data))
        
        conn.close()
        return list(reversed(messages))  # Chronological order
    
    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        with self._lock:
            message = self.messages.get(message_id)
            if not message:
                return False
            
            message.read = True
            conn = sqlite3.connect(self.base_path / "personal_data.db")
            with conn:
                conn.execute("UPDATE messages SET read = 1 WHERE message_id = ?", (message_id,))
            conn.close()
            return True
    
    def _persist_message(self, message: PANMessage) -> None:
        """Persist a message to database."""
        conn = sqlite3.connect(self.base_path / "personal_data.db")
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO messages (
                    message_id, conversation_id, sender_sovereign_id, recipient_sovereign_id,
                    message_type, content, media_attachments, timestamp, read, delivered,
                    encrypted, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.message_id,
                message.conversation_id,
                message.sender_sovereign_id,
                message.recipient_sovereign_id,
                message.message_type,
                message.content,
                json.dumps(message.media_attachments),
                message.timestamp,
                int(message.read),
                int(message.delivered),
                int(message.encrypted),
                json.dumps(message.metadata)
            ))
        conn.close()
    
    # ==================== Call Log Management ====================
    
    def log_call(
        self,
        caller_sovereign_id: str,
        recipient_sovereign_id: str,
        call_type: str,
        direction: str,
        duration_seconds: int = 0,
        **kwargs
    ) -> PANCallLog:
        """Log a call record."""
        with self._lock:
            call_id = derive_uuid(f"call:{caller_sovereign_id}:{utc_now_iso()}")
            
            call_log = PANCallLog(
                call_id=call_id,
                caller_sovereign_id=caller_sovereign_id,
                recipient_sovereign_id=recipient_sovereign_id,
                call_type=call_type,
                direction=direction,
                start_time=utc_now_iso(),
                duration_seconds=duration_seconds,
                **kwargs
            )
            
            self.call_logs[call_id] = call_log
            self._persist_call_log(call_log)
            
            logger.info(f"Logged {direction} {call_type} call {call_id[:12]}")
            return call_log
    
    def get_call_history(self, limit: int = 50) -> List[PANCallLog]:
        """Get recent call history."""
        conn = sqlite3.connect(self.base_path / "personal_data.db")
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT * FROM call_logs 
            WHERE caller_sovereign_id = ? OR recipient_sovereign_id = ?
            ORDER BY start_time DESC 
            LIMIT ?
        """, (self.sovereign_id, self.sovereign_id, limit))
        
        calls = []
        for row in cursor:
            call_data = dict(row)
            call_data['metadata'] = json.loads(call_data.get('metadata') or '{}')
            calls.append(PANCallLog.from_dict(call_data))
        
        conn.close()
        return calls
    
    def _persist_call_log(self, call_log: PANCallLog) -> None:
        """Persist a call log to database."""
        conn = sqlite3.connect(self.base_path / "personal_data.db")
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO call_logs (
                    call_id, caller_sovereign_id, recipient_sovereign_id, call_type,
                    direction, start_time, end_time, duration_seconds, call_quality,
                    recording_uri, notes, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                call_log.call_id,
                call_log.caller_sovereign_id,
                call_log.recipient_sovereign_id,
                call_log.call_type,
                call_log.direction,
                call_log.start_time,
                call_log.end_time,
                call_log.duration_seconds,
                call_log.call_quality,
                call_log.recording_uri,
                call_log.notes,
                json.dumps(call_log.metadata)
            ))
        conn.close()
    
    # ==================== User Preferences ====================
    
    def save_preferences(self, preferences: UserPreferences) -> None:
        """Save user preferences."""
        with self._lock:
            self.preferences = preferences
            
            conn = sqlite3.connect(self.base_path / "personal_data.db")
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO user_preferences (
                        user_sovereign_id, theme, notification_enabled, default_message_encryption,
                        auto_sync, backup_enabled, language, vm_preferences, app_settings,
                        privacy_settings
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    preferences.user_sovereign_id,
                    preferences.theme,
                    int(preferences.notification_enabled),
                    int(preferences.default_message_encryption),
                    int(preferences.auto_sync),
                    int(preferences.backup_enabled),
                    preferences.language,
                    json.dumps(preferences.vm_preferences),
                    json.dumps(preferences.app_settings),
                    json.dumps(preferences.privacy_settings)
                ))
            conn.close()
            
            logger.info(f"Saved preferences for {self.sovereign_id[:12]}")
    
    def get_preferences(self) -> UserPreferences:
        """Get user preferences."""
        return self.preferences or UserPreferences(user_sovereign_id=self.sovereign_id)
    
    # ==================== Data Export / Backup ====================
    
    def export_data(self, output_path: Optional[Path] = None) -> Path:
        """Export all personal data to JSON for backup."""
        output_path = output_path or self.base_path / f"backup_{utc_now_iso().replace(':', '-')}.json"
        
        export_data = {
            "sovereign_id": self.sovereign_id,
            "export_timestamp": utc_now_iso(),
            "contacts": [c.to_dict() for c in self.contacts.values()],
            "preferences": self.preferences.to_dict() if self.preferences else None,
            "metadata": {
                "total_contacts": len(self.contacts),
                "total_messages": len(self.messages),
                "total_calls": len(self.call_logs),
            }
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Exported personal data to {output_path}")
        return output_path
    
    def close(self) -> None:
        """Close all database connections and clean up resources."""
        with self._lock:
            # Clear in-memory caches to free memory
            self.contacts.clear()
            self.messages.clear()
            self.call_logs.clear()
            self.preferences = None
            
            logger.info(f"Closed PANPersonalDataStore for sovereign {self.sovereign_id[:12]}")


# ==================== Phone Address Registry ====================

class PANPhoneAddressRegistry:
    """
    Maps PAN phone addresses to sovereign identities and VM instances.
    Phone address format: pan:[network-hash]:[identity-motif]:voice
    """
    
    def __init__(self, persistence: Optional[PANPersistenceStore] = None):
        self.persistence = persistence or PANPersistenceStore()
        self._lock = threading.RLock()
        self.address_map: Dict[str, Dict[str, Any]] = {}
        self._load_from_persistence()
        
        logger.info("PANPhoneAddressRegistry initialized")
    
    def _load_from_persistence(self) -> None:
        """Load phone addresses from persistence."""
        persisted = self.persistence.load_component('phone_addresses')
        if persisted:
            self.address_map.update(persisted)
            logger.debug(f"Loaded {len(self.address_map)} phone addresses from persistence")
    
    def assign_phone_address(
        self,
        sovereign_id: str,
        vm_id: str,
        network_hash: Optional[str] = None,
        identity_motif: Optional[str] = None,
    ) -> str:
        """
        Assign a PAN phone address to a sovereign identity + VM.
        Returns address in format: pan:[network-hash]:[identity-motif]:voice
        """
        with self._lock:
            # Generate network hash (simplified - in production use .lacka network ID)
            if not network_hash:
                network_hash = sha256_hex(f"pan_network:{sovereign_id}")[:8]
            
            # Generate identity motif (simplified - in production use compressed motif)
            if not identity_motif:
                identity_motif = sha256_hex(f"identity:{sovereign_id}")[:16]
            
            phone_address = f"pan:{network_hash}:{identity_motif}:voice"
            
            # Check if address already exists
            if phone_address in self.address_map:
                logger.warning(f"Phone address {phone_address} already assigned")
                return phone_address
            
            # Register the address
            address_record = {
                "phone_address": phone_address,
                "sovereign_id": sovereign_id,
                "vm_id": vm_id,
                "network_hash": network_hash,
                "identity_motif": identity_motif,
                "assigned_at": utc_now_iso(),
                "active": True,
            }
            
            self.address_map[phone_address] = address_record
            self.persistence.write_state('phone_addresses', phone_address, address_record)
            
            logger.info(f"Assigned phone address {phone_address} to sovereign {sovereign_id[:12]}")
            return phone_address
    
    def resolve_address(self, phone_address: str) -> Optional[Dict[str, Any]]:
        """Resolve a phone address to sovereign identity and VM info."""
        return self.address_map.get(phone_address)
    
    def get_address_for_sovereign(self, sovereign_id: str) -> Optional[str]:
        """Get the phone address for a sovereign identity."""
        for address, record in self.address_map.items():
            if record["sovereign_id"] == sovereign_id and record["active"]:
                return address
        return None
    
    def deactivate_address(self, phone_address: str) -> bool:
        """Deactivate a phone address."""
        with self._lock:
            record = self.address_map.get(phone_address)
            if not record:
                return False
            
            record["active"] = False
            record["deactivated_at"] = utc_now_iso()
            self.persistence.write_state('phone_addresses', phone_address, record)
            
            logger.info(f"Deactivated phone address {phone_address}")
            return True
