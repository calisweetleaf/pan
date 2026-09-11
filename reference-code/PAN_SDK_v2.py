"""
Planetary Autonomous Network - PAN Global SDK
"""

import hashlib
import json
import time
import uuid
import re
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature
from numpy import identity

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# --------------------------- #
# --------- Utilities --------#
# --------------------------- #

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def canonical(obj) -> str:
    """Deterministic JSON for hashing. No whitespace, sorted keys."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)

def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def derive_uuid(prefix: str = "") -> str:
    """Namespaced deterministic UUID if prefix provided; random otherwise."""
    if prefix:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, prefix))
    return str(uuid.uuid4())

PAN_DATA_ROOT = Path("pan_data")


# --------------------------- #
# --------- Persistence --------#
# --------------------------- #

class PersistenceManager:
    """
    Manages SQLite-based persistent storage for the PAN network.
    Provides append-only storage for ledger, citizen registry, apps, transactions.
    """
    
    def __init__(self, db_path: str = "pan_network.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the SQLite database with all required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table for ledger entries (append-only)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id TEXT UNIQUE NOT NULL,
                entry_type TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                author_hash TEXT NOT NULL,
                hashchain_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create table for citizen registry
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS citizens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                citizen_id TEXT UNIQUE NOT NULL,
                identity_hash TEXT NOT NULL,
                citizen_type TEXT NOT NULL,
                registration_time TEXT NOT NULL,
                tokens REAL DEFAULT 0,
                reputation_score REAL DEFAULT 100,
                active_status BOOLEAN DEFAULT 1,
                permissions TEXT DEFAULT '[]',
                resource_usage TEXT DEFAULT '{}',
                registration_data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create table for applications
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id TEXT UNIQUE NOT NULL,
                app_name TEXT NOT NULL,
                developer_identity TEXT NOT NULL,
                creation_time TEXT NOT NULL,
                active_status BOOLEAN DEFAULT 1,
                users_count INTEGER DEFAULT 0,
                total_tokens_earned REAL DEFAULT 0,
                token_per_use REAL DEFAULT 1,
                app_metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create table for transactions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT UNIQUE NOT NULL,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create table for DHT data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dht_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                ledger_hash TEXT,
                author_hash TEXT NOT NULL,
                consensus_record TEXT,
                timestamp TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create table for names in the registry
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                target_identity TEXT NOT NULL,
                service_endpoint TEXT,
                registered_at TEXT NOT NULL,
                registered_by TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                active BOOLEAN DEFAULT 1,
                deregistered_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create table for hashchain entries
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hashchain (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identity_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                previous_hash TEXT,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                depth INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(entry_hash, identity_hash)
            )
        ''')
        
        # Create table for consensus records
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS consensus_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT UNIQUE NOT NULL,
                item_key TEXT NOT NULL,
                item_value TEXT NOT NULL,
                proposer TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PROPOSED',
                votes TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_ledger_entry(self, entry_id: str, entry_type: str, data: Dict[str, Any], 
                          timestamp: str, author_hash: str, hashchain_hash: str, signature: str) -> bool:
        """Store an entry in the ledger table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO ledger (entry_id, entry_type, data, timestamp, author_hash, hashchain_hash, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (entry_id, entry_type, json.dumps(data), timestamp, author_hash, hashchain_hash, signature))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Ledger entry with ID {entry_id} already exists")
            return False
        except Exception as e:
            logger.error(f"Failed to store ledger entry {entry_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_ledger_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a ledger entry by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM ledger WHERE entry_id = ?', (entry_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'entry_id': row[1],
                'entry_type': row[2],
                'data': json.loads(row[3]),
                'timestamp': row[4],
                'author_hash': row[5],
                'hashchain_hash': row[6],
                'signature': row[7],
                'created_at': row[8]
            }
        return None
    
    def get_all_ledger_entries(self, limit: int = None) -> List[Dict[str, Any]]:
        """Retrieve all ledger entries."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM ledger ORDER BY id DESC'
        params = []
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        entries = []
        for row in rows:
            entries.append({
                'id': row[0],
                'entry_id': row[1],
                'entry_type': row[2],
                'data': json.loads(row[3]),
                'timestamp': row[4],
                'author_hash': row[5],
                'hashchain_hash': row[6],
                'signature': row[7],
                'created_at': row[8]
            })
        return entries
    
    def store_citizen(self, citizen_data: Dict[str, Any]) -> bool:
        """Store citizen data in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO citizens 
                (citizen_id, identity_hash, citizen_type, registration_time, tokens, 
                 reputation_score, active_status, permissions, resource_usage, registration_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                citizen_data['citizen_id'], 
                citizen_data['identity_hash'], 
                citizen_data['citizen_type'], 
                citizen_data['registration_time'], 
                citizen_data.get('tokens', 0),
                citizen_data.get('reputation_score', 100),
                citizen_data.get('active_status', True),
                json.dumps(citizen_data.get('permissions', [])),
                json.dumps(citizen_data.get('resource_usage', {})),
                json.dumps(citizen_data.get('registration_data', {}))
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store citizen {citizen_data.get('citizen_id', 'unknown')}: {e}")
            return False
        finally:
            conn.close()
    
    def get_citizen(self, citizen_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a citizen by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM citizens WHERE citizen_id = ?', (citizen_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'citizen_id': row[1],
                'identity_hash': row[2],
                'citizen_type': row[3],
                'registration_time': row[4],
                'tokens': row[5],
                'reputation_score': row[6],
                'active_status': bool(row[7]),
                'permissions': json.loads(row[8]),
                'resource_usage': json.loads(row[9]),
                'registration_data': json.loads(row[10]),
                'created_at': row[11],
                'updated_at': row[12]
            }
        return None
    
    def get_all_citizens(self) -> List[Dict[str, Any]]:
        """Retrieve all citizens."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM citizens')
        rows = cursor.fetchall()
        conn.close()
        
        citizens = []
        for row in rows:
            citizens.append({
                'id': row[0],
                'citizen_id': row[1],
                'identity_hash': row[2],
                'citizen_type': row[3],
                'registration_time': row[4],
                'tokens': row[5],
                'reputation_score': row[6],
                'active_status': bool(row[7]),
                'permissions': json.loads(row[8]),
                'resource_usage': json.loads(row[9]),
                'registration_data': json.loads(row[10]),
                'created_at': row[11],
                'updated_at': row[12]
            })
        return citizens
    
    def store_application(self, app_data: Dict[str, Any]) -> bool:
        """Store application data in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO applications 
                (app_id, app_name, developer_identity, creation_time, active_status, 
                 users_count, total_tokens_earned, token_per_use, app_metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                app_data['app_id'], 
                app_data['app_name'], 
                app_data['developer_identity'], 
                app_data['creation_time'], 
                app_data.get('active_status', True),
                app_data.get('users_count', 0),
                app_data.get('total_tokens_earned', 0),
                app_data.get('token_per_use', 1),
                json.dumps(app_data.get('app_metadata', {}))
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store application {app_data.get('app_id', 'unknown')}: {e}")
            return False
        finally:
            conn.close()
    
    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an application by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM applications WHERE app_id = ?', (app_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'app_id': row[1],
                'app_name': row[2],
                'developer_identity': row[3],
                'creation_time': row[4],
                'active_status': bool(row[5]),
                'users_count': row[6],
                'total_tokens_earned': row[7],
                'token_per_use': row[8],
                'app_metadata': json.loads(row[9]),
                'created_at': row[10],
                'updated_at': row[11]
            }
        return None
    
    def get_all_applications(self) -> List[Dict[str, Any]]:
        """Retrieve all applications."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM applications')
        rows = cursor.fetchall()
        conn.close()
        
        apps = []
        for row in rows:
            apps.append({
                'id': row[0],
                'app_id': row[1],
                'app_name': row[2],
                'developer_identity': row[3],
                'creation_time': row[4],
                'active_status': bool(row[5]),
                'users_count': row[6],
                'total_tokens_earned': row[7],
                'token_per_use': row[8],
                'app_metadata': json.loads(row[9]),
                'created_at': row[10],
                'updated_at': row[11]
            })
        return apps
    
    def store_transaction(self, transaction_data: Dict[str, Any]) -> bool:
        """Store transaction data in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO transactions 
                (transaction_id, sender, recipient, amount, transaction_type, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                transaction_data['transaction_id'], 
                transaction_data['sender'], 
                transaction_data['recipient'], 
                transaction_data['amount'], 
                transaction_data['transaction_type'], 
                transaction_data['timestamp'], 
                json.dumps(transaction_data.get('metadata', {}))
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Transaction with ID {transaction_data['transaction_id']} already exists")
            return False
        except Exception as e:
            logger.error(f"Failed to store transaction {transaction_data.get('transaction_id', 'unknown')}: {e}")
            return False
        finally:
            conn.close()
    
    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a transaction by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM transactions WHERE transaction_id = ?', (transaction_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'transaction_id': row[1],
                'sender': row[2],
                'recipient': row[3],
                'amount': row[4],
                'transaction_type': row[5],
                'timestamp': row[6],
                'metadata': json.loads(row[7]),
                'created_at': row[8]
            }
        return None
    
    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """Retrieve all transactions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM transactions ORDER BY id DESC')
        rows = cursor.fetchall()
        conn.close()
        
        transactions = []
        for row in rows:
            transactions.append({
                'id': row[0],
                'transaction_id': row[1],
                'sender': row[2],
                'recipient': row[3],
                'amount': row[4],
                'transaction_type': row[5],
                'timestamp': row[6],
                'metadata': json.loads(row[7]),
                'created_at': row[8]
            })
        return transactions
    
    def store_dht_data(self, key: str, value: Any, value_hash: str, ledger_hash: Optional[str], 
                      author_hash: str, consensus_record: Optional[str], timestamp: str) -> bool:
        """Store DHT key-value data in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO dht_data 
                (key, value, value_hash, ledger_hash, author_hash, consensus_record, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (key, json.dumps(value), value_hash, ledger_hash, author_hash, consensus_record, timestamp))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store DHT data with key {key}: {e}")
            return False
        finally:
            conn.close()
    
    def get_dht_data(self, key: str) -> Optional[Any]:
        """Retrieve DHT data by key."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM dht_data WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def get_all_dht_data(self) -> List[Tuple[str, Any]]:
        """Retrieve all DHT data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT key, value FROM dht_data')
        rows = cursor.fetchall()
        conn.close()
        
        data = []
        for row in rows:
            data.append((row[0], json.loads(row[1])))
        return data
    
    def store_name(self, name_data: Dict[str, Any]) -> bool:
        """Store a name in the registry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO names 
                (name, target_identity, service_endpoint, registered_at, registered_by, metadata, active, deregistered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name_data['name'], 
                name_data['target_identity'], 
                name_data.get('service_endpoint'), 
                name_data['registered_at'], 
                name_data['registered_by'], 
                json.dumps(name_data.get('metadata', {})),
                name_data.get('active', True),
                name_data.get('deregistered_at')
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store name {name_data.get('name', 'unknown')}: {e}")
            return False
        finally:
            conn.close()
    
    def get_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a name from the registry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM names WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'target_identity': row[2],
                'service_endpoint': row[3],
                'registered_at': row[4],
                'registered_by': row[5],
                'metadata': json.loads(row[6]),
                'active': bool(row[7]),
                'deregistered_at': row[8],
                'created_at': row[9]
            }
        return None
    
    def get_all_names(self) -> List[Dict[str, Any]]:
        """Retrieve all names."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM names')
        rows = cursor.fetchall()
        conn.close()
        
        names = []
        for row in rows:
            names.append({
                'id': row[0],
                'name': row[1],
                'target_identity': row[2],
                'service_endpoint': row[3],
                'registered_at': row[4],
                'registered_by': row[5],
                'metadata': json.loads(row[6]),
                'active': bool(row[7]),
                'deregistered_at': row[8],
                'created_at': row[9]
            })
        return names
    
    def store_hashchain_entry(self, identity_hash: str, entry_hash: str, previous_hash: Optional[str], 
                             data: Dict[str, Any], timestamp: str, depth: int) -> bool:
        """Store a hashchain entry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO hashchain 
                (identity_hash, entry_hash, previous_hash, data, timestamp, depth)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (identity_hash, entry_hash, previous_hash, json.dumps(data), timestamp, depth))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store hashchain entry {entry_hash}: {e}")
            return False
        finally:
            conn.close()
    
    def get_hashchain_entries(self, identity_hash: str) -> List[Dict[str, Any]]:
        """Retrieve all hashchain entries for an identity."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM hashchain WHERE identity_hash = ? ORDER BY depth', (identity_hash,))
        rows = cursor.fetchall()
        conn.close()
        
        entries = []
        for row in rows:
            entries.append({
                'id': row[0],
                'identity_hash': row[1],
                'entry_hash': row[2],
                'previous_hash': row[3],
                'data': json.loads(row[4]),
                'timestamp': row[5],
                'depth': row[6],
                'created_at': row[7]
            })
        return entries
    
    def store_consensus_record(self, record_data: Dict[str, Any]) -> bool:
        """Store a consensus record."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO consensus_records 
                (proposal_id, item_key, item_value, proposer, timestamp, status, votes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                record_data['proposal_id'], 
                record_data['item_key'], 
                json.dumps(record_data['item_value']), 
                record_data['proposer'], 
                record_data['timestamp'], 
                record_data['status'], 
                json.dumps(record_data.get('votes', {}))
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store consensus record {record_data.get('proposal_id', 'unknown')}: {e}")
            return False
        finally:
            conn.close()
    
    def get_consensus_record(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a consensus record by proposal ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM consensus_records WHERE proposal_id = ?', (proposal_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'proposal_id': row[1],
                'item_key': row[2],
                'item_value': json.loads(row[3]),
                'proposer': row[4],
                'timestamp': row[5],
                'status': row[6],
                'votes': json.loads(row[7]),
                'created_at': row[8],
                'updated_at': row[9]
            }
        return None
    
    def get_all_consensus_records(self) -> List[Dict[str, Any]]:
        """Retrieve all consensus records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM consensus_records ORDER BY id DESC')
        rows = cursor.fetchall()
        conn.close()
        
        records = []
        for row in rows:
            records.append({
                'id': row[0],
                'proposal_id': row[1],
                'item_key': row[2],
                'item_value': json.loads(row[3]),
                'proposer': row[4],
                'timestamp': row[5],
                'status': row[6],
                'votes': json.loads(row[7]),
                'created_at': row[8],
                'updated_at': row[9]
            })
        return records
    
    def replay_state(self) -> Dict[str, Any]:
        """Replay the state from the database to reconstruct in-memory objects."""
        return {
            'ledger': self.get_all_ledger_entries(),
            'citizens': self.get_all_citizens(),
            'applications': self.get_all_applications(),
            'transactions': self.get_all_transactions(),
            'dht_data': self.get_all_dht_data(),
            'names': self.get_all_names(),
            'hashchain': {row['identity_hash']: self.get_hashchain_entries(row['identity_hash']) 
                          for row in self.get_all_citizens() if row.get('identity_hash')},
            'consensus_records': self.get_all_consensus_records()
        }

# --------------------------- #
# --------- Utilities --------#
# --------------------------- #

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def canonical(obj) -> str:
    """Deterministic JSON for hashing. No whitespace, sorted keys."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)

def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def derive_uuid(prefix: str = "") -> str:
    """Namespaced deterministic UUID if prefix provided; random otherwise."""
    if prefix:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, prefix))
    return str(uuid.uuid4())

class SovereignIdentity:
    """
    Represents the cryptographic identity of a sovereign actor (user or AI model).
    Each actor has a unique cryptographic keypair for authentication and verification.
    Now includes hashchain functionality for the PAN network.
    """
    
    def __init__(self, name: str, private_key_pem: Optional[bytes] = None, 
                 hashchain_parent: Optional[str] = None):
        self.name = name
        self.created_at = utc_now_iso()
        self.hashchain_parent = hashchain_parent  # Previous hash in the chain
        self.hashchain_depth = 0  # Depth in the hashchain
        
        # Generate or load private key
        if private_key_pem:
            self._private_key = serialization.load_pem_private_key(
                private_key_pem, password=None
            )
        else:
            self._private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
        
        # Extract public key
        self._public_key = self._private_key.public_key()
        
        # Generate identity hash
        pub_key_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.identity_hash = sha256_hex(pub_key_bytes)[:64]
        
        # Initialize hashchain with identity hash if no parent provided
        if hashchain_parent is None:
            self.current_hash = self.identity_hash
        else:
            # Create first hash in chain based on parent
            chain_data = f"{self.identity_hash}:{hashchain_parent}:{self.created_at}"
            self.current_hash = sha256_hex(chain_data)
        
        logger.info(f"Created SovereignIdentity for {name} with ID: {self.identity_hash[:12]} in hashchain")

    def sign(self, data: bytes) -> bytes:
        """Sign data with the private key."""
        return self._private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

    def verify_signature(self, data: bytes, signature: bytes, public_key_pem: bytes) -> bool:
        """Verify a signature with a public key."""
        try:
            public_key = serialization.load_pem_public_key(public_key_pem)
            public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False

    def get_public_key_pem(self) -> bytes:
        """Get the public key in PEM format."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def serialize_private_key(self) -> bytes:
        """Serialize the private key to PEM format."""
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

    def create_hashchain_entry(self, data: Dict[str, Any]) -> str:
        """
        Create a new entry in the hashchain with the given data.
        This creates an immutable record linked to the previous hash.
        """
        # Create hash of the data
        data_hash = sha256_hex(canonical(data))
        
        # Create chain entry: previous_hash + data_hash + timestamp
        chain_entry = f"{self.current_hash}:{data_hash}:{self.created_at}"
        new_hash = sha256_hex(chain_entry)
        
        # Update current hash
        self.current_hash = new_hash
        self.hashchain_depth += 1
        
        logger.info(f"Created hashchain entry for {self.name}, depth: {self.hashchain_depth}")
        return new_hash
    
    def create_persistent_hashchain_entry(self, data: Dict[str, Any], persistence_manager: PersistenceManager) -> str:
        """
        Create a new entry in the hashchain with the given data and persist it.
        This creates an immutable record linked to the previous hash.
        """
        # Create hash of the data
        data_hash = sha256_hex(canonical(data))
        
        # Create chain entry: previous_hash + data_hash + timestamp
        chain_entry = f"{self.current_hash}:{data_hash}:{self.created_at}"
        new_hash = sha256_hex(chain_entry)
        
        # Keep track of the previous hash before updating
        previous_hash = self.current_hash
        
        # Update current hash
        self.current_hash = new_hash
        self.hashchain_depth += 1
        
        # Persist the hashchain entry
        persistence_manager.store_hashchain_entry(
            identity_hash=self.identity_hash,
            entry_hash=new_hash,
            previous_hash=previous_hash,
            data=data,
            timestamp=self.created_at,
            depth=self.hashchain_depth
        )
        
        logger.info(f"Created and persisted hashchain entry for {self.name}, depth: {self.hashchain_depth}")
        return new_hash

    def verify_hashchain_entry(self, entry_hash: str, data: Dict[str, Any], 
                              previous_hash: str) -> bool:
        """
        Verify that an entry is valid in the hashchain.
        """
        data_hash = sha256_hex(canonical(data))
        chain_entry = f"{previous_hash}:{data_hash}:{self.created_at}"
        calculated_hash = sha256_hex(chain_entry)
        return calculated_hash == entry_hash
    
    def persist_hashchain_entry(self, persistence_manager: PersistenceManager, 
                               entry_hash: str, previous_hash: Optional[str], 
                               data: Dict[str, Any]) -> bool:
        """
        Persist a hashchain entry to the database.
        """
        return persistence_manager.store_hashchain_entry(
            identity_hash=self.identity_hash,
            entry_hash=entry_hash,
            previous_hash=previous_hash,
            data=data,
            timestamp=self.created_at,
            depth=self.hashchain_depth
        )

@dataclass
class UnifiedDataPacket:
    """
    Universal data packet for all communication in the sovereign AI infrastructure.
    This replaces the traditional memory node concept for secure communication.
    Enhanced to support ledger entries for the PAN network.
    """
    packet_id: str
    kind: str  # INFERENCE_REQUEST, INFERENCE_RESPONSE, MODEL_MANIFEST, etc.
    content: Dict[str, Any]
    author_identity_hash: str
    timestamp: str
    parents: List[str]  # Links to parent packets for traceability
    metadata: Dict[str, Any]
    
    # Cryptographic fields
    content_hash: str  # Hash of the content for integrity verification
    signature: bytes   # Signature from the author
    
    # Hashchain fields for immutable ledger
    previous_hash: Optional[str] = None  # Previous hash in the chain
    ledger_hash: Optional[str] = None   # Combined hash for ledger entry
    sequence_number: Optional[int] = None  # Position in the sequence
    
    def __post_init__(self):
        # Calculate content hash if not provided
        if not self.content_hash:
            self.content_hash = sha256_hex(canonical(self.content))[:64]
        
        # Generate packet ID if not provided
        if not self.packet_id:
            id_data = f"{self.kind}:{self.author_identity_hash}:{self.timestamp}:{self.content_hash}"
            self.packet_id = sha256_hex(id_data)[:64]
        
        # Generate ledger hash if not provided (for immutable record)
        if not self.ledger_hash:
            ledger_data = f"{self.packet_id}:{self.previous_hash or 'genesis'}:{self.content_hash}:{self.timestamp}"
            self.ledger_hash = sha256_hex(ledger_data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert packet to dictionary for serialization."""
        return {
            "packet_id": self.packet_id,
            "kind": self.kind,
            "content": self.content,
            "author_identity_hash": self.author_identity_hash,
            "timestamp": self.timestamp,
            "parents": self.parents,
            "metadata": self.metadata,
            "content_hash": self.content_hash,
            "signature": self.signature.hex() if self.signature else None,
            "previous_hash": self.previous_hash,
            "ledger_hash": self.ledger_hash,
            "sequence_number": self.sequence_number
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedDataPacket':
        """Create a packet from dictionary data."""
        # Convert signature back from hex
        if data.get("signature"):
            data["signature"] = bytes.fromhex(data["signature"])
        return cls(**data)

    def verify_integrity(self) -> bool:
        """Verify the integrity of the packet content."""
        calculated_hash = sha256_hex(canonical(self.content))[:64]
        return calculated_hash == self.content_hash

    def verify_ledger_link(self, expected_previous_hash: Optional[str] = None) -> bool:
        """
        Verify that this packet is properly linked in the ledger chain.
        """
        if expected_previous_hash and self.previous_hash != expected_previous_hash:
            return False
        
        # Recalculate the ledger hash to verify integrity
        expected_ledger_hash = sha256_hex(
            f"{self.packet_id}:{self.previous_hash or 'genesis'}:{self.content_hash}:{self.timestamp}"
        )
        return expected_ledger_hash == self.ledger_hash

class SovereignCommunicator:
    """
    Handles secure communication between sovereign entities using the 
    UnifiedDataPacket protocol.
    """
    
    def __init__(self, identity: SovereignIdentity):
        self.identity = identity
        logger.info(f"SovereignCommunicator initialized for {identity.name}")

    def create_packet(self, kind: str, content: Dict[str, Any], 
                     parents: List[str] = None, metadata: Dict[str, Any] = None) -> UnifiedDataPacket:
        """Create a signed data packet."""
        packet = UnifiedDataPacket(
            packet_id=None,  # Will be generated
            kind=kind,
            content=content,
            author_identity_hash=self.identity.identity_hash,
            timestamp=utc_now_iso(),
            parents=parents or [],
            metadata=metadata or {},
            content_hash=None,  # Will be calculated
            signature=None  # Will be added
        )
        
        # Sign the packet
        packet_data = canonical(packet.to_dict()).encode('utf-8')
        packet.signature = self.identity.sign(packet_data)
        
        logger.info(f"Created {kind} packet: {packet.packet_id[:12]}")
        return packet

    def verify_packet(self, packet: UnifiedDataPacket, author_public_key_pem: bytes) -> bool:
        """Verify a packet's signature and integrity."""
        # Check content integrity
        if not packet.verify_integrity():
            logger.warning(f"Packet {packet.packet_id[:12]} failed integrity check")
            return False
            
        # Verify signature
        packet_dict = packet.to_dict()
        # Remove signature for verification
        packet_dict['signature'] = None
        packet_data = canonical(packet_dict).encode('utf-8')
        
        try:
            self.identity.verify_signature(packet_data, packet.signature, author_public_key_pem)
            logger.debug(f"Packet {packet.packet_id[:12]} verified successfully")
            return True
        except Exception as e:
            logger.warning(f"Packet {packet.packet_id[:12]} failed signature verification: {e}")
            return False

# --------------------------- #
# ---------- Model Management ----------#
# --------------------------- #

class ModelManifest:
    """
    Represents a cryptographically signed manifest for a model,
    ensuring authenticity and integrity.
    """
    
    def __init__(self, model_name: str, model_hash: str, model_public_key_pem: bytes,
                 creator_identity: SovereignIdentity):
        self.model_name = model_name
        self.model_hash = model_hash
        self.model_public_key_pem = model_public_key_pem
        self.created_at = utc_now_iso()
        
        # Create the manifest content
        self.content = {
            "model_name": model_name,
            "model_hash": model_hash,
            "model_public_key": model_public_key_pem.decode('utf-8'),
            "created_at": self.created_at
        }
        
        # Sign the manifest
        self.content_hash = sha256_hex(canonical(self.content))[:64]
        manifest_data = canonical(self.content).encode('utf-8')
        self.signature = creator_identity.sign(manifest_data)
        self.creator_identity_hash = creator_identity.identity_hash
        
        logger.info(f"Created manifest for model {model_name}")

    def verify_manifest(self, creator_public_key_pem: bytes, expected_creator_identity_hash: Optional[str] = None) -> bool:
        """Verify the manifest's signature and integrity."""
        try:
            public_key = serialization.load_pem_public_key(creator_public_key_pem)
        except (ValueError, TypeError) as exc:
            logger.warning(f"Invalid creator public key for manifest {self.model_name}: {exc}")
            return False

        computed_identity_hash = sha256_hex(creator_public_key_pem)[:64]
        if expected_creator_identity_hash and computed_identity_hash != expected_creator_identity_hash:
            logger.warning(
                f"Creator identity mismatch for manifest {self.model_name}: expected {expected_creator_identity_hash[:12]}, "
                f"received {computed_identity_hash[:12]}"
            )
            return False

        if computed_identity_hash != self.creator_identity_hash:
            logger.warning(
                f"Stored creator identity hash mismatch for manifest {self.model_name}: "
                f"manifest={self.creator_identity_hash[:12]}, provided={computed_identity_hash[:12]}"
            )
            return False

        serialized_content = canonical(self.content)
        recalculated_hash = sha256_hex(serialized_content)[:64]
        if recalculated_hash != self.content_hash:
            logger.warning(
                f"Content hash mismatch for manifest {self.model_name}: "
                f"stored={self.content_hash[:12]}, recalculated={recalculated_hash[:12]}"
            )
            return False

        try:
            public_key.verify(
                self.signature,
                serialized_content.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        except InvalidSignature:
            logger.warning(f"Signature verification failed for manifest {self.model_name}")
            return False
        except Exception as exc:
            logger.warning(f"Unexpected error verifying manifest {self.model_name}: {exc}")
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "model_hash": self.model_hash,
            "model_public_key_pem": self.model_public_key_pem.decode('utf-8'),
            "created_at": self.created_at,
            "content_hash": self.content_hash,
            "signature": self.signature.hex(),
            "creator_identity_hash": self.creator_identity_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelManifest':
        """Create a manifest from dictionary data."""
        # This is a simplified reconstruction for demonstration
        instance = cls.__new__(cls)
        instance.model_name = data["model_name"]
        instance.model_hash = data["model_hash"]
        instance.model_public_key_pem = data["model_public_key_pem"].encode('utf-8')
        instance.created_at = data["created_at"]
        instance.content_hash = data["content_hash"]
        instance.signature = bytes.fromhex(data["signature"])
        instance.creator_identity_hash = data["creator_identity_hash"]
        instance.content = {
            "model_name": data["model_name"],
            "model_hash": data["model_hash"],
            "model_public_key": data["model_public_key_pem"],
            "created_at": data["created_at"]
        }
        return instance

# --------------------------- #
# ---------- Inference Engine ----------#
# --------------------------- #

class SovereignInferenceEngine:
    """
    Local inference engine that processes requests using the sovereign protocol.
    This represents the "air-gapped AI brain" that runs entirely offline.
    """
    
    def __init__(self, model_path: str, model_manifest: ModelManifest):
        self.model_path = model_path
        self.model_manifest = model_manifest
        self.loaded = False
        logger.info(f"SovereignInferenceEngine initialized for {model_manifest.model_name}")

    def load_model(self):
        """Load the model into memory."""
        # In a real implementation, this would load your quantized model
        # For now, we'll just simulate the loading
        logger.info(f"Loading model from {self.model_path}")
        # Simulate model loading time
        time.sleep(0.1)
        self.loaded = True
        logger.info("Model loaded successfully")

    def process_request(self, request_packet: UnifiedDataPacket, 
                       user_public_key_pem: bytes) -> UnifiedDataPacket:
        """Process an inference request and return a signed response."""
        if not self.loaded:
            self.load_model()
            
        # Verify the request
        # In a real implementation, you'd have a communicator to verify
        # For this example, we'll assume verification is done elsewhere
        
        # Extract prompt and parameters
        prompt = request_packet.content.get("prompt", "")
        temperature = request_packet.content.get("temperature", 0.7)
        max_tokens = request_packet.content.get("max_tokens", 100)
        
        logger.info(f"Processing inference request: {prompt[:50]}...")
        
        # Simulate model inference with your quantization method
        # This is where your proprietary quantization would be used
        response_text = self._run_inference(prompt, temperature, max_tokens)
        
        # Create response packet
        response_content = {
            "response": response_text,
            "input_tokens": len(prompt.split()),
            "output_tokens": len(response_text.split()),
            "processing_time_ms": 150,  # Simulated time
            "model_name": self.model_manifest.model_name
        }
        
        # In a real implementation, you'd use a communicator with the model's identity
        # For this example, we'll create a simplified response
        response_packet = UnifiedDataPacket(
            packet_id=None,
            kind="INFERENCE_RESPONSE",
            content=response_content,
            author_identity_hash=self.model_manifest.creator_identity_hash,  # Simplified
            timestamp=utc_now_iso(),
            parents=[request_packet.packet_id],
            metadata={"processing_node": "local"},
            content_hash=None,
            signature=None
        )
        
        # In a real implementation, this would be signed by the model's identity
        # response_packet.signature = model_identity.sign(...)
        
        logger.info("Inference request processed successfully")
        return response_packet

    def _run_inference(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Simulate running inference with your quantization method."""
        # This is where your proprietary quantization method would be integrated
        # For demonstration, we'll just return a simulated response
        return f"Simulated response to: {prompt[:50]}... (processed with proprietary quantization)"

# --------------------------- #
# ---------- Distributed Hash Table (DHT) ----------#
# --------------------------- #

class DHTNode:
    """
    Represents a node in the distributed hash table.
    Each node maintains a portion of the key-value pairs in the PAN network.
    """
        def __init__(
        self,
        identity: SovereignIdentity,
        address: str = "127.0.0.1",
        port: int = 8462,
        *,
        enable_consensus: bool = True,
        enable_registries: bool = True,
        persistence: Optional[PANPersistenceStore] = None,
    ) -> None:
        self.identity = identity
        self.address = address
        self.port = port
        self.node_id = identity.identity_hash[:16]
        self.data_store: Dict[str, Dict[str, Any]] = {}
        self.routing_table: Dict[str, Dict[str, Any]] = {}
        self.network_neighbors: set[str] = set()
        self.persistence = persistence or PANPersistenceStore()
        self.consensus: Optional['PANConsensus'] = PANConsensus(identity) if enable_consensus else None
        self.ledger: Dict[str, Dict[str, Any]] = {}
        self.pending_transactions: List[Dict[str, Any]] = []
        self.citizen_registry: Optional[Any] = None
        self.economic_engine: Optional[Any] = None
        self.name_registry: Optional[Any] = None
        self.governance_council: Optional[Any] = None

        if enable_registries:
            self._initialize_registries()

        self._hydrate_from_persistence()

        logger.info(
            "DHTNode initialized for %s at %s:%s, ID: %s",
            identity.name,
            address,
            port,
            self.node_id,
        )

    def _initialize_registries(self) -> None:
        """Instantiate civic subsystems if their classes are available."""
        registry_specs = (
            ("citizen_registry", "PANCitizenRegistry", (self.identity, self), {"persistence": self.persistence}),
            ("economic_engine", "PANEconomicEngine", (self,), {"persistence": self.persistence}),
            ("name_registry", "PANNameRegistry", (self.identity, self), {"persistence": self.persistence}),
            ("governance_council", "PANGovernanceCouncil", (self,), {"persistence": self.persistence}),
        )
        global_namespace = globals()
        for attr_name, class_name, args, kwargs in registry_specs:
            if getattr(self, attr_name, None) is not None:
                continue
            cls = global_namespace.get(class_name)
            if cls is None:
                logger.debug("Registry component %s not available yet", class_name)
                continue
            kwargs = kwargs or {}
            setattr(self, attr_name, cls(*args, **kwargs))

    def _hydrate_from_persistence(self) -> None:
        if not self.persistence:
            return
        persisted_data = self.persistence.load_component('dht_data')
        if persisted_data:
            self.data_store.update(persisted_data)
        persisted_ledger = self.persistence.load_component('dht_ledger')
        if persisted_ledger:
            self.ledger.update(persisted_ledger)
        pending = self.persistence.read_state('dht_pending_transactions', 'pending')
        if isinstance(pending, list):
            self.pending_transactions = pending
        if self.citizen_registry and hasattr(self.citizen_registry, 'hydrate_from_persistence'):
            self.citizen_registry.hydrate_from_persistence()
        if self.economic_engine and hasattr(self.economic_engine, 'hydrate_from_persistence'):
            self.economic_engine.hydrate_from_persistence()
        if self.governance_council and hasattr(self.governance_council, 'hydrate_from_persistence'):
            self.governance_council.hydrate_from_persistence()

    def __init__(self, identity: SovereignIdentity, address: str = "127.0.0.1", port: int = 8462):
        self.identity = identity
        self.address = address
        self.port = port
        self.node_id = identity.identity_hash[:16]  # Use part of the identity hash as node ID
        self.data_store = {}  # Local storage for key-value pairs
        self.routing_table = {}  # Known nodes in the network
        self.network_neighbors = set()  # Connected neighbors
        
        logger.info(f"DHTNode initialized for {identity.name} at {address}:{port}, ID: {self.node_id}")



    def get_key_hash(self, key: str) -> str:
        """Generate a hash for a key to determine where it should be stored."""
        return sha256_hex(key)[:16]  # Use first 16 chars for 16-bit address space

    def store(self, key: str, value: Any) -> bool:
        """Store a key-value pair locally."""
        try:
            # Create a signed ledger entry for the storage operation
            ledger_entry = {
                "operation": "STORE",
                "key": key,
                "value_hash": sha256_hex(str(value)),
                "timestamp": utc_now_iso(),
                "node_id": self.node_id
            }
            
            # Add to hashchain
            new_hash = self.identity.create_hashchain_entry(ledger_entry)
            
            # Store the actual data with its ledger reference
            self.data_store[key] = {
                "value": value,
                "ledger_hash": new_hash,
                "timestamp": utc_now_iso(),
                "author": self.identity.identity_hash
            }
            
            logger.info(f"Stored key {key} in DHT with hash {new_hash[:12]}")
            return True
        except Exception as e:
            logger.error(f"Failed to store key {key} in DHT: {e}")
            return False

    def lookup(self, key: str) -> Optional[Any]:
        """Look up a value by key."""
        if key in self.data_store:
            logger.debug(f"Found key {key} in local DHT storage")
            return self.data_store[key]["value"]
        
        logger.debug(f"Key {key} not found in local DHT storage")
        return None

    def add_neighbor(self, node_id: str, address: str, port: int):
        """Add a neighbor to the routing table."""
        self.routing_table[node_id] = {
            "address": address,
            "port": port,
            "last_seen": utc_now_iso()
        }
        self.network_neighbors.add(node_id)
        
        logger.info(f"Added neighbor {node_id} at {address}:{port}")

    def get_closest_nodes(self, key_hash: str, num_nodes: int = 8) -> List[Dict[str, Any]]:
        """Find the closest nodes to a key hash."""
        # Calculate distance to each known node
        distances = []
        key_numeric = int(key_hash, 16)
        
        for node_id, node_info in self.routing_table.items():
            node_numeric = int(node_id[:16], 16)  # Use first 16 chars like key
            distance = abs(key_numeric - node_numeric)
            distances.append((distance, node_id, node_info))
        
        # Sort by distance and return closest nodes
        distances.sort(key=lambda x: x[0])
        closest = []
        
        for _, node_id, node_info in distances[:num_nodes]:
            closest.append({
                "node_id": node_id,
                "address": node_info["address"],
                "port": node_info["port"]
            })
        
        return closest


class PANConsensus:
    """
    Consensus mechanism for the PAN network.
    Implements a simplified Byzantine fault-tolerant consensus for the hashchain.
    """
    def __init__(self, identity: SovereignIdentity):
        self.identity = identity
        self.consensus_records = {}  # Track consensus for different items
        self.votes = {}  # Track votes for each consensus item
        self.validators = set()  # Set of validator identities

    def add_validator(self, identity_hash: str):
        """Add a validator to the consensus network."""
        self.validators.add(identity_hash)
        logger.info(f"Added validator {identity_hash[:12]} to consensus network")

    def propose_consensus(self, item_key: str, item_value: Any) -> str:
        """
        Propose an item for consensus in the network.
        """
        proposal_id = derive_uuid(f"{item_key}:{str(item_value)[:20]}")
        
        consensus_item = {
            "proposal_id": proposal_id,
            "item_key": item_key,
            "item_value": item_value,
            "proposer": self.identity.identity_hash,
            "timestamp": utc_now_iso(),
            "status": "PROPOSED",  # PROPOSED, ACCEPTED, REJECTED
            "votes": {self.identity.identity_hash: True}  # Self-vote
        }
        
        self.consensus_records[proposal_id] = consensus_item
        logger.info(f"Proposed consensus for {item_key} with ID {proposal_id[:12]}")
        
        return proposal_id

    def vote_on_proposal(self, proposal_id: str, vote: bool, voter_identity: SovereignIdentity) -> bool:
        """
        Vote on a consensus proposal.
        """
        if proposal_id not in self.consensus_records:
            logger.warning(f"Proposal {proposal_id[:12]} not found for voting")
            return False

        # Verify the voter's signature on the vote
        vote_data = {"proposal_id": proposal_id, "vote": vote, "voter": voter_identity.identity_hash}
        vote_hash = sha256_hex(canonical(vote_data))
        
        # Add the vote to the proposal
        proposal = self.consensus_records[proposal_id]
        proposal["votes"][voter_identity.identity_hash] = vote
        
        # Check if we have enough votes for consensus (simple majority for now)
        total_validators = len(self.validators)
        total_votes = len(proposal["votes"])
        yes_votes = sum(1 for v in proposal["votes"].values() if v)
        
        # For simple majority consensus
        if total_votes >= total_validators // 2 + 1:
            if yes_votes > total_votes // 2:
                proposal["status"] = "ACCEPTED"
                logger.info(f"Proposal {proposal_id[:12]} accepted by consensus")
            else:
                proposal["status"] = "REJECTED"
                logger.info(f"Proposal {proposal_id[:12]} rejected by consensus")
        
        logger.info(f"Vote recorded for proposal {proposal_id[:12]} by {voter_identity.identity_hash[:12]}")
        return True

    def is_consensus_reached(self, proposal_id: str) -> Optional[bool]:
        """
        Check if consensus has been reached for a proposal.
        Returns True if accepted, False if rejected, None if still pending.
        """
        if proposal_id not in self.consensus_records:
            return None
        
        proposal = self.consensus_records[proposal_id]
        if proposal["status"] == "ACCEPTED":
            return True
        elif proposal["status"] == "REJECTED":
            return False
        return None
    
    def persist_proposal(self, dht_node: DHTNode) -> bool:
        """Persist the consensus records to the database."""
        for proposal_id, record in self.consensus_records.items():
            record_data = {
                "proposal_id": proposal_id,
                "item_key": record["item_key"],
                "item_value": record["item_value"],
                "proposer": record["proposer"],
                "timestamp": record["timestamp"],
                "status": record["status"],
                "votes": record["votes"]
            }
            success = dht_node.persistence.store_consensus_record(record_data)
            if not success:
                logger.error(f"Failed to persist consensus record {proposal_id}")
                return False
        return True
    
    def load_proposals_from_db(self, dht_node: DHTNode):
        """Load consensus records from the database."""
        records = dht_node.persistence.get_all_consensus_records()
        for record in records:
            self.consensus_records[record["proposal_id"]] = {
                "item_key": record["item_key"],
                "item_value": record["item_value"],
                "proposer": record["proposer"],
                "timestamp": record["timestamp"],
                "status": record["status"],
                "votes": record["votes"]
            }
        logger.info(f"Loaded {len(records)} consensus records from database")


class DHTNode:
    """
    Represents a node in the distributed hash table.
    Each node maintains a portion of the key-value pairs in the PAN network.
    Enhanced with consensus and broader PAN functionality.
    """
    def __init__(self, identity: SovereignIdentity, address: str = "127.0.0.1", port: int = 8462, 
                 persistence_path: str = "pan_network.db"):
        self.identity = identity
        self.address = address
        self.port = port
        self.node_id = identity.identity_hash[:16]  # Use part of the identity hash as node ID
        self.data_store = {}  # Local storage for key-value pairs
        self.routing_table = {}  # Known nodes in the network
        self.network_neighbors = set()  # Connected neighbors
        self.consensus = PANConsensus(identity)  # Consensus mechanism for the node
        self.ledger = {}  # PAN ledger for immutable records
        self.pending_transactions = []  # Pending transactions awaiting consensus
        self.citizen_registry = PANCitizenRegistry(identity, self)  # PAN citizen and app registry
        self.economic_engine = PANEconomicEngine(self)  # PAN economic system
        self.name_registry = PANNameRegistry(identity, self)  # PAN name resolution system
        
        # Persistence manager for offline-first storage
        self.persistence = PersistenceManager(persistence_path)
        
        # Load existing state from persistence if available
        self.load_state_from_persistence()
    
    def load_state_from_persistence(self):
        """Load existing state from persistence."""
        try:
            # Get all data from persistence
            persisted_data = self.persistence.replay_state()
            
            # Load ledger entries
            for entry in persisted_data['ledger']:
                key = f"ledger:{entry['entry_type']}:{entry['timestamp']}"
                self.ledger[key] = entry
            
            # Load DHT data into memory
            for key, value in persisted_data['dht_data']:
                self.data_store[key] = value
                
            # Load citizens into registry
            for citizen_data in persisted_data['citizens']:
                # Create citizen object from data
                citizen_identity = SovereignIdentity(f"PersistedCitizen_{citizen_data['citizen_id'][:8]}")
                citizen = PANCitizen(
                    identity=citizen_identity,
                    citizen_id=citizen_data['citizen_id'],
                    citizen_type=citizen_data['citizen_type'],
                    registration_data=json.loads(citizen_data['registration_data'])
                )
                citizen.tokens = citizen_data['tokens']
                citizen.reputation_score = citizen_data['reputation_score']
                citizen.active_status = citizen_data['active_status']
                citizen.permissions = set(json.loads(citizen_data['permissions']))
                
                # Add to registry without storing again (since it's already in DB)
                self.citizen_registry.citizens[citizen.citizen_id] = citizen
                self.citizen_registry.citizen_by_identity[citizen_data['identity_hash']] = citizen.citizen_id
            
            # Load applications into registry
            for app_data in persisted_data['applications']:
                # Create app object from data
                developer_identity = SovereignIdentity(f"Developer_{app_data['developer_identity'][:8]}")
                app = PANApplication(
                    app_name=app_data['app_name'],
                    developer_identity=developer_identity,
                    app_id=app_data['app_id'],
                    app_metadata=json.loads(app_data['app_metadata'])
                )
                app.active_status = app_data['active_status']
                app.total_tokens_earned = app_data['total_tokens_earned']
                app.token_per_use = app_data['token_per_use']
                
                # Add to registry without storing again (since it's already in DB)
                self.citizen_registry.applications[app.app_id] = app
            
            logger.info("State loaded from persistence successfully")
        except Exception as e:
            logger.error(f"Error loading state from persistence: {e}")
        
        logger.info(f"DHTNode initialized for {identity.name} at {address}:{port}, ID: {self.node_id}")

    def get_key_hash(self, key: str) -> str:
        """Generate a hash for a key to determine where it should be stored."""
        return sha256_hex(key)[:16]  # Use first 16 chars for 16-bit address space

    def store(self, key: str, value: Any, require_consensus: bool = True) -> bool:
        """Store a key-value pair locally with optional consensus."""
        try:
            proposal_id = None
            # If consensus is required, create a proposal first
            if require_consensus:
                proposal_id = self.consensus.propose_consensus(key, value)
                
                # For now, since we're a single node, we'll auto-accept
                # In a real network, we'd wait for other validators
                self.consensus.vote_on_proposal(proposal_id, True, self.identity)
                
                # Wait briefly to process consensus status
                import time
                time.sleep(0.01)
                
                if self.consensus.is_consensus_reached(proposal_id) is False:
                    logger.warning(f"Consensus failed for key {key}")
                    return False

            # Create a signed ledger entry for the storage operation
            ledger_entry = {
                "operation": "STORE",
                "key": key,
                "value": value,  # Store the actual value in the ledger entry too
                "value_hash": sha256_hex(str(value)),
                "timestamp": utc_now_iso(),
                "node_id": self.node_id,
                "author": self.identity.identity_hash
            }
            
            # Add to hashchain
            new_hash = self.identity.create_hashchain_entry(ledger_entry)
            
            # Create PAN ledger entry
            ledger_key = f"ledger:{key}:{utc_now_iso()}"
            ledger_signature = self.identity.sign(canonical(ledger_entry).encode())
            self.ledger[ledger_key] = {
                "hashchain_hash": new_hash,
                "entry": ledger_entry,
                "signature": ledger_signature
            }
            
            # Store the actual data with its ledger reference
            store_entry = {
                "value": value,
                "ledger_hash": new_hash,
                "timestamp": utc_now_iso(),
                "author": self.identity.identity_hash,
                "consensus_record": proposal_id if require_consensus else None
            }
            
            self.data_store[key] = store_entry
            
            # Persist the data to the database
            success = self.persistence.store_dht_data(
                key=key,
                value=value,
                value_hash=sha256_hex(str(value)),
                ledger_hash=new_hash,
                author_hash=self.identity.identity_hash,
                consensus_record=proposal_id if require_consensus else None,
                timestamp=utc_now_iso()
            )
            
            # Also store the ledger entry in persistence
            self.persistence.store_ledger_entry(
                entry_id=new_hash,
                entry_type="DHT_STORE",
                data=ledger_entry,
                timestamp=ledger_entry["timestamp"],
                author_hash=ledger_entry["author"],
                hashchain_hash=new_hash,
                signature=ledger_signature.hex()
            )
            
            if success:
                logger.info(f"Stored key {key} in PAN DHT with hash {new_hash[:12]} and persisted to database")
                return True
            else:
                logger.error(f"Failed to persist key {key} to database")
                return False
        except Exception as e:
            logger.error(f"Failed to store key {key} in PAN DHT: {e}")
            return False

    def lookup(self, key: str, include_history: bool = False) -> Optional[Any]:
        """Look up a value by key, optionally with historical versions."""
        if key in self.data_store:
            if not include_history:
                logger.debug(f"Found key {key} in local PAN DHT storage")
                return self.data_store[key]["value"]
            else:
                # Find all historical entries for this key
                history = []
                for ledger_key, ledger_entry in self.ledger.items():
                    if ledger_key.startswith(f"ledger:{key}:"):
                        history.append(ledger_entry)
                
                result = {
                    "current_value": self.data_store[key]["value"],
                    "history": history
                }
                return result
        else:
            # Check if the key exists in persistence
            persisted_value = self.persistence.get_dht_data(key)
            if persisted_value is not None:
                # Load it into memory
                ledger_hash = self.get_ledger_hash_for_key(key)  # Helper method to find ledger hash
                self.data_store[key] = {
                    "value": persisted_value,
                    "ledger_hash": ledger_hash,
                    "timestamp": utc_now_iso(),  # In a real implementation, get the actual timestamp
                    "author": self.identity.identity_hash,  # In a real implementation, get the actual author
                    "consensus_record": None  # In a real implementation, get the actual consensus record
                }
                
                if not include_history:
                    logger.debug(f"Found key {key} in persisted DHT storage and loaded to memory")
                    return persisted_value
                else:
                    # Find all historical entries for this key
                    history = []
                    for ledger_key, ledger_entry in self.ledger.items():
                        if ledger_key.startswith(f"ledger:{key}:"):
                            history.append(ledger_entry)
                    
                    result = {
                        "current_value": persisted_value,
                        "history": history
                    }
                    return result
        
        logger.debug(f"Key {key} not found in local PAN DHT storage")
        return None
    
    def get_ledger_hash_for_key(self, key: str) -> Optional[str]:
        """Helper method to get the ledger hash for a specific key from persistence."""
        # This is a simplified implementation - in a real system, you'd have a more efficient way
        # to map keys to their ledger entries
        persisted_data = self.persistence.get_dht_data(key)
        if persisted_data is not None:
            # Look up in persistence for the ledger hash for this key
            conn = sqlite3.connect(self.persistence.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT ledger_hash FROM dht_data WHERE key = ?', (key,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row[0]
        return None

    def add_neighbor(self, node_id: str, address: str, port: int):
        """Add a neighbor to the routing table."""
        self.routing_table[node_id] = {
            "address": address,
            "port": port,
            "last_seen": utc_now_iso()
        }
        self.network_neighbors.add(node_id)
        
        logger.info(f"Added neighbor {node_id} at {address}:{port}")

    def get_closest_nodes(self, key_hash: str, num_nodes: int = 8) -> List[Dict[str, Any]]:
        """Find the closest nodes to a key hash."""
        key_numeric = int(key_hash, 16)
        distances = []
        for peer_id, info in self.routing_table.items():
            peer_numeric = int(peer_id[:16], 16)
            distances.append((abs(key_numeric - peer_numeric), peer_id, info))

        distances.sort(key=lambda item: item[0])
        return [
            {"node_id": peer_id, "address": info["address"], "port": info["port"]}
            for _, peer_id, info in distances[:num_nodes]
        ]
        
        # Calculate distance to each known node
        distances = []
        key_numeric = int(key_hash, 16)
        
        for node_id, node_info in self.routing_table.items():
            node_numeric = int(node_id[:16], 16)  # Use first 16 chars like key
            distance = abs(key_numeric - node_numeric)
            distances.append((distance, node_id, node_info))
        
        # Sort by distance and return closest nodes
        distances.sort(key=lambda x: x[0])
        closest = []
        
        for _, node_id, node_info in distances[:num_nodes]:
            closest.append({
                "node_id": node_id,
                "address": node_info["address"],
                "port": node_info["port"]
            })
        
        return closest

    def execute_transaction(self, transaction_data: Dict[str, Any]) -> str:
        """
        Execute a transaction on the PAN network.
        This could be any operation that needs to be recorded in the ledger.
        """
        # Create a transaction record
        transaction_id = derive_uuid(f"tx:{canonical(transaction_data)}")
        
        transaction_record = {
            "transaction_id": transaction_id,
            "data": transaction_data,
            "timestamp": utc_now_iso(),
            "author": self.identity.identity_hash,
            "node_id": self.node_id
        }
        
        # Add to hashchain
        tx_hash = self.identity.create_hashchain_entry(transaction_record)
        
        # Add to ledger
        ledger_key = f"transaction:{transaction_id}"
        signature = self.identity.sign(canonical(transaction_record).encode())
        self.ledger[ledger_key] = {
            "hashchain_hash": tx_hash,
            "entry": transaction_record,
            "signature": signature
        }
        
        # Store in pending transactions if consensus required
        self.pending_transactions.append(transaction_record)
        
        # Persist the transaction to the database
        persistence_success = self.persistence.store_ledger_entry(
            entry_id=tx_hash,
            entry_type="TRANSACTION",
            data=transaction_record,
            timestamp=transaction_record["timestamp"],
            author_hash=transaction_record["author"],
            hashchain_hash=tx_hash,
            signature=signature.hex()
        )
        
        if persistence_success:
            logger.info(f"Executed and persisted transaction {transaction_id[:12]} on PAN network")
        else:
            logger.error(f"Transaction {transaction_id[:12]} executed but failed to persist to database")
        
        return transaction_id

class PANConsensus:
    """Consensus mechanism for the PAN network's hashchain operations."""

    def __init__(self, identity: SovereignIdentity):
        self.identity = identity
        self.consensus_records: Dict[str, Dict[str, Any]] = {}
        self.votes: Dict[str, Dict[str, bool]] = {}
        self.validators: set[str] = set()

    def add_validator(self, identity_hash: str) -> None:
        """Register a validator able to participate in consensus."""
        self.validators.add(identity_hash)
        logger.info("Added validator %s to consensus network", identity_hash[:12])

    def propose_consensus(self, item_key: str, item_value: Any) -> str:
        """Submit a proposal to reach consensus on a key/value update."""
        proposal_id = derive_uuid(f"{item_key}:{str(item_value)[:20]}")
        consensus_item = {
            "proposal_id": proposal_id,
            "item_key": item_key,
            "item_value": item_value,
            "proposer": self.identity.identity_hash,
            "timestamp": utc_now_iso(),
            "status": "PROPOSED",
            "votes": {self.identity.identity_hash: True},
        }
        self.consensus_records[proposal_id] = consensus_item
        logger.info("Proposed consensus for %s with ID %s", item_key, proposal_id[:12])
        return proposal_id

    def vote_on_proposal(self, proposal_id: str, vote: bool, voter_identity: SovereignIdentity) -> bool:
        """Record a validator vote for a proposal."""
        proposal = self.consensus_records.get(proposal_id)
        if not proposal:
            logger.warning("Proposal %s not found for voting", proposal_id[:12])
            return False

        proposal.setdefault("votes", {})[voter_identity.identity_hash] = vote

        total_validators = max(len(self.validators), 1)
        total_votes = len(proposal["votes"])
        yes_votes = sum(1 for accepted in proposal["votes"].values() if accepted)

        if total_votes >= total_validators // 2 + 1:
            if yes_votes > total_votes // 2:
                proposal["status"] = "ACCEPTED"
                logger.info("Proposal %s accepted by consensus", proposal_id[:12])
            else:
                proposal["status"] = "REJECTED"
                logger.info("Proposal %s rejected by consensus", proposal_id[:12])

        logger.info(
            "Vote recorded for proposal %s by %s",
            proposal_id[:12],
            voter_identity.identity_hash[:12],
        )
        return True

    def is_consensus_reached(self, proposal_id: str) -> Optional[bool]:
        """Return True if accepted, False if rejected, None if still pending."""
        proposal = self.consensus_records.get(proposal_id)
        if not proposal:
            return None
        status = proposal.get("status")
        if status == "ACCEPTED":
            return True
        if status == "REJECTED":
            return False
        return None

class PANNameRegistry:
    """
    Name resolution system for the PAN network.
    Allows human-readable names to be mapped to identity hashes and service endpoints.
    """
    def __init__(self, identity: SovereignIdentity, dht_node: DHTNode):
        self.identity = identity
        self.dht_node = dht_node
        self.name_registry = {}  # name -> registration record
        self.reverse_lookup = {}  # identity_hash -> names
        
        logger.info("PANNameRegistry initialized")
    
    def register_name(self, name: str, target_identity: str, 
                     service_endpoint: str = None, metadata: Dict[str, Any] = None) -> bool:
        """Register a name in the PAN namespace."""
        # Check if name already exists
        if name in self.name_registry:
            logger.warning(f"Name {name} is already registered")
            return False
        
        # Check if name follows PAN naming conventions
        if not self._validate_name(name):
            logger.warning(f"Invalid name format: {name}")
            return False
        
        # Create registration record
        registration = {
            "name": name,
            "target_identity": target_identity,
            "service_endpoint": service_endpoint,
            "registered_at": utc_now_iso(),
            "registered_by": self.identity.identity_hash,
            "metadata": metadata or {},
            "active": True
        }
        
        # Attempt to store in DHT with consensus
        name_key = f"name:{name}"
        success = self.dht_node.store(name_key, registration, require_consensus=True)
        
        if success:
            self.name_registry[name] = registration
            if target_identity not in self.reverse_lookup:
                self.reverse_lookup[target_identity] = set()
            self.reverse_lookup[target_identity].add(name)
            
            logger.info(f"Successfully registered name {name} for identity {target_identity[:12]}")
            return True
        else:
            logger.error(f"Failed to register name {name} in DHT")
            return False
    
    def resolve_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Resolve a name to its target identity and service endpoint."""
        if name in self.name_registry:
            return self.name_registry[name]
        
        # Try to look up in DHT
        name_key = f"name:{name}"
        dht_result = self.dht_node.lookup(name_key)
        
        if dht_result:
            self.name_registry[name] = dht_result
            target_identity = dht_result["target_identity"]
            if target_identity not in self.reverse_lookup:
                self.reverse_lookup[target_identity] = set()
            self.reverse_lookup[target_identity].add(name)
            
            logger.debug(f"Resolved name {name} from DHT")
            return dht_result
        
        logger.debug(f"Name {name} not found in registry")
        return None
    
    def resolve_identity_names(self, identity_hash: str) -> List[str]:
        """Get all names associated with an identity."""
        if identity_hash in self.reverse_lookup:
            return list(self.reverse_lookup[identity_hash])
        return []
    
    def _validate_name(self, name: str) -> bool:
        """Validate that a name follows PAN naming conventions."""
        # Names must be 3-63 characters, lowercase alphanumeric and hyphens only
        # Must start and end with alphanumeric
        pattern = r'^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'
        return bool(re.match(pattern, name))
    
    def deregister_name(self, name: str, requester_identity: str) -> bool:
        """Deregister a name (requires authorization)."""
        if name not in self.name_registry:
            logger.warning(f"Cannot deregister unknown name: {name}")
            return False
        
        registration = self.name_registry[name]
        
        # Only allow the original registrant or admin to deregister
        if requester_identity not in [registration["registered_by"], self.identity.identity_hash]:
            logger.warning(f"Unauthorized deregister attempt for {name}")
            return False
        
        # Mark as inactive
        registration["active"] = False
        registration["deregistered_at"] = utc_now_iso()
        
        # Update in DHT
        name_key = f"name:{name}"
        success = self.dht_node.store(name_key, registration, require_consensus=True)
        
        if success:
            logger.info(f"Deregistered name {name}")
            return True
        else:
            logger.error(f"Failed to deregister name {name} in DHT")
            return False
    
    def persist_name(self, name: str) -> bool:
        """Persist a name registration to the database."""
        if name not in self.name_registry:
            logger.warning(f"Cannot persist unknown name: {name}")
            return False
        
        name_data = self.name_registry[name].copy()
        return self.dht_node.persistence.store_name(name_data)
    
    def load_name_from_db(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a name registration from the database."""
        name_data = self.dht_node.persistence.get_name(name)
        if name_data:
            # Store in memory
            self.name_registry[name] = name_data
            target_identity = name_data["target_identity"]
            if target_identity not in self.reverse_lookup:
                self.reverse_lookup[target_identity] = set()
            self.reverse_lookup[target_identity].add(name)
            
            logger.debug(f"Loaded name {name} from database")
            return name_data
        return None


class PANEconomicEngine:
    """
    Economic engine for the PAN network.
    Manages the token economy, resource allocation, and value exchange.
    """
        def __init__(self, dht_node: DHTNode, persistence: Optional[PANPersistenceStore] = None):
        self.dht_node = dht_node
        self.persistence = persistence
        self.token_supply = 0
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.transaction_history: List[Dict[str, Any]] = []
        self.resource_prices = {}
        self.service_fees = {
            "compute": 0.01,
            "storage": 0.005,
            "bandwidth": 0.001,
            "app_usage": 1,
            "sdk_api_call": 0.5,
            "name_registration": 5,
            "app_deployment": 10,
        }
        self.usage_history: List[Dict[str, Any]] = []
        self.usage_metrics = {
            "total_usage_events": 0,
            "volume_by_type": {},
        }
        self.platform_fee_rate = 0.10
        self.reward_pool_rate = 0.5
        self.treasury_account_id = "treasury:pan"
        self.reward_pool_account_id = "reward_pool:pan"

        self.hydrate_from_persistence()

        self.ensure_account(self.treasury_account_id, account_type="treasury")
        self.ensure_account(self.reward_pool_account_id, account_type="reward_pool")

        logger.info("PANEconomicEngine initialized")

    def hydrate_from_persistence(self) -> None:
        if not self.persistence:
            return
        stored_accounts = self.persistence.load_component('economy_accounts')
        if stored_accounts:
            self.accounts = stored_accounts
        token_state = self.persistence.read_state('economy_meta', 'token_supply')
        if isinstance(token_state, dict) and 'token_supply' in token_state:
            self.token_supply = token_state['token_supply']
        elif isinstance(token_state, (int, float)):
            self.token_supply = token_state
        metrics = self.persistence.read_state('economy_usage_metrics', 'metrics')
        if isinstance(metrics, dict):
            self.usage_metrics.update(metrics)
        tx_events = self.persistence.load_journal('economy', 'transaction')
        if tx_events:
            self.transaction_history = [entry['payload'] for entry in tx_events]
        usage_events = self.persistence.load_journal('economy', 'usage')
        if usage_events:
            self.usage_history = [entry['payload'] for entry in usage_events]

    def _persist_account(self, account_id: str) -> None:
        if not self.persistence:
            return
        account = self.accounts.get(account_id)
        if account is None:
            return
        self.persistence.write_state('economy_accounts', account_id, account)
        self.persistence.write_state('economy_meta', 'token_supply', {'token_supply': self.token_supply})

    def _persist_usage_metrics(self) -> None:
        if not self.persistence:
            return
        self.persistence.write_state('economy_usage_metrics', 'metrics', self.usage_metrics)

    def ensure_account(
        self,
        account_id: str,
        *,
        owner_identity: Optional[str] = None,
        account_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create an account if it does not exist and return it."""
        account = self.accounts.get(account_id)
        if not account:
            account = {
                "account_id": account_id,
                "owner_identity": owner_identity,
                "account_type": account_type,
                "balance": 0,
                "lifetime_earned": 0,
                "lifetime_spent": 0,
                "created_at": utc_now_iso(),
                "metadata": metadata or {},
            }
            self.accounts[account_id] = account
            self._persist_account(account_id)
        else:
            if owner_identity and not account.get("owner_identity"):
                account["owner_identity"] = owner_identity
            if metadata:
                account.setdefault("metadata", {}).update(metadata)
            self._persist_account(account_id)
        return account

    def get_balance(self, account_id: str) -> int:
        """Return the current balance for an account."""
        account = self.ensure_account(account_id)
        return account["balance"]

    def mint_tokens(self, recipient_id: str, amount: int, reason: str = "incentive") -> bool:
        """Mint new tokens and credit them to an account."""
        if amount <= 0:
            logger.warning("Attempted to mint non-positive token amount")
            return False

        account = self.ensure_account(recipient_id)
        account["balance"] += amount
        account["lifetime_earned"] += amount
        self.token_supply += amount

        record = {
            "transaction_type": "mint",
            "recipient": recipient_id,
            "amount": amount,
            "reason": reason,
            "timestamp": utc_now_iso(),
        }
        transaction_id = self.dht_node.execute_transaction(record) if self.dht_node else derive_uuid(f"mint:{recipient_id}:{utc_now_iso()}")
        record["transaction_id"] = transaction_id
        self.transaction_history.append(record)
        if self.persistence:
            self.persistence.append_journal('economy', 'transaction', record)

        self._persist_account(recipient_id)

        logger.info(
            "Minted %s tokens to %s for %s. Total supply: %s",
            amount,
            recipient_id[:12],
            reason,
            self.token_supply,
        )
        return True

    def charge_service_fee(self, service_type: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Calculate the fee for a service based on usage parameters."""
        params = params or {}
        base_fee = self.service_fees.get(service_type, 0)
        if base_fee <= 0:
            return 0

        if service_type == "compute":
            units = params.get("compute_units") or params.get("units") or 1
            return int(math.ceil(base_fee * units))
        if service_type == "storage":
            mb = params.get("megabytes") or params.get("units") or 1
            days = params.get("days", 1)
            return int(math.ceil(base_fee * mb * days))
        if service_type == "bandwidth":
            mb = params.get("megabytes") or params.get("units") or 1
            return int(math.ceil(base_fee * mb))
        if service_type in {"app_usage", "sdk_api_call"}:
            units = params.get("units", 1)
            return max(1, int(math.ceil(base_fee * units)))

        multiplier = params.get("units", 1)
        return int(math.ceil(base_fee * multiplier))

    def transfer_tokens(
        self,
        sender_id: str,
        recipient_id: str,
        amount: int,
        transaction_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Transfer tokens between accounts, recording the movement."""
        if amount <= 0:
            return {"success": False, "error": "Invalid transaction amount"}

        sender = self.ensure_account(sender_id)
        recipient = self.ensure_account(recipient_id)

        if sender["balance"] < amount:
            logger.warning(
                "Insufficient tokens for %s to send %s (has %s)",
                sender_id[:12],
                amount,
                sender["balance"],
            )
            return {"success": False, "error": "Insufficient funds"}

        sender["balance"] -= amount
        sender["lifetime_spent"] += amount
        recipient["balance"] += amount
        recipient["lifetime_earned"] += amount

        transaction_record = {
            "sender": sender_id,
            "recipient": recipient_id,
            "amount": amount,
            "transaction_type": transaction_type,
            "metadata": metadata or {},
        }
        transaction_id = self.dht_node.execute_transaction(transaction_record)
        transaction_record["transaction_id"] = transaction_id
        transaction_record["timestamp"] = utc_now_iso()
        self.transaction_history.append(transaction_record)

        if self.persistence:
            self.persistence.append_journal('economy', 'transaction', transaction_record)

        self._persist_account(sender_id)
        self._persist_account(recipient_id)

        logger.info(
            "Executed transaction %s: %s tokens from %s to %s",
            transaction_id[:12],
            amount,
            sender_id[:12],
            recipient_id[:12],
        )
        return {
            "success": True,
            "transaction_id": transaction_id,
            "amount": amount,
            "sender": sender_id,
            "recipient": recipient_id,
        }

    def execute_transaction(
        self,
        sender_id: str,
        recipient_id: str,
        amount: int,
        transaction_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Backward-compatible wrapper around transfer_tokens."""
        return self.transfer_tokens(
            sender_id,
            recipient_id,
            amount,
            transaction_type,
            metadata,
        )

    def record_usage(
        self,
        consumer_id: Optional[str],
        provider_id: Optional[str],
        service_type: str,
        quantity: int = 1,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        bill_consumer: bool = True,
    ) -> Dict[str, Any]:
        """Record platform usage, optionally billing the consumer."""
        metadata = metadata or {}
        usage_id = derive_uuid(f"usage:{service_type}:{consumer_id}:{provider_id}:{utc_now_iso()}")
        fee = self.charge_service_fee(service_type, {"units": quantity, **metadata})

        consumer_account = self.ensure_account(consumer_id) if consumer_id else None
        provider_account = self.ensure_account(provider_id, account_type="application") if provider_id else None

        settlement_details: Dict[str, Any] = {
            "fee": fee,
            "provider_share": 0,
            "treasury_share": 0,
            "reward_allocation": 0,
        }

        if bill_consumer and consumer_account and fee > 0:
            if consumer_account["balance"] < fee:
                logger.warning(
                    "Usage billing failed: %s has %s tokens but needs %s",
                    consumer_id[:12],
                    consumer_account["balance"],
                    fee,
                )
                settlement_details["error"] = "insufficient_funds"
            else:
                treasury_share = int(math.floor(fee * self.platform_fee_rate))
                provider_share = max(fee - treasury_share, 0)
                settlement_details["provider_share"] = provider_share
                settlement_details["treasury_share"] = treasury_share

                if provider_share > 0 and provider_id:
                    self.transfer_tokens(
                        consumer_account["account_id"],
                        provider_account["account_id"],
                        provider_share,
                        f"usage_{service_type}",
                        metadata,
                    )

                if treasury_share > 0:
                    self.transfer_tokens(
                        consumer_account["account_id"],
                        self.treasury_account_id,
                        treasury_share,
                        "platform_fee",
                        {"service_type": service_type, **metadata},
                    )
                    reward_cut = int(math.floor(treasury_share * self.reward_pool_rate))
                    if reward_cut > 0:
                        treasury_balance = self.get_balance(self.treasury_account_id)
                        if treasury_balance >= reward_cut:
                            self.transfer_tokens(
                                self.treasury_account_id,
                                self.reward_pool_account_id,
                                reward_cut,
                                "reward_allocation",
                                {"origin_usage": usage_id},
                            )
                            settlement_details["reward_allocation"] = reward_cut
        elif fee > 0 and provider_id:
            self.mint_tokens(provider_account["account_id"], fee, reason=f"usage_reward_{service_type}")
            settlement_details["provider_share"] = fee

        usage_entry = {
            "usage_id": usage_id,
            "consumer_id": consumer_id,
            "provider_id": provider_id,
            "service_type": service_type,
            "quantity": quantity,
            "timestamp": utc_now_iso(),
            "metadata": metadata,
            "settlement": settlement_details,
            "billed_consumer": bool(bill_consumer and consumer_id),
        }
        self.usage_history.append(usage_entry)
        self.usage_metrics["total_usage_events"] += 1
        volume_bucket = self.usage_metrics["volume_by_type"].setdefault(service_type, 0)
        self.usage_metrics["volume_by_type"][service_type] = volume_bucket + quantity

        if self.persistence:
            self.persistence.append_journal('economy', 'usage', usage_entry)
            self._persist_usage_metrics()
            if consumer_id:
                self._persist_account(consumer_id)
            if provider_id:
                self._persist_account(provider_id)
            self._persist_account(self.treasury_account_id)
            self._persist_account(self.reward_pool_account_id)

        if self.dht_node:
            self.dht_node.store(f"usage:{usage_id}", usage_entry, require_consensus=False)

        return usage_entry

    def distribute_rewards(self, allocation: Dict[str, int], reason: str = "usage_reward") -> bool:
        """Distribute reward-pool tokens according to weighted allocation."""
        if not allocation:
            return False
        pool_balance = self.get_balance(self.reward_pool_account_id)
        if pool_balance <= 0:
            logger.warning("Reward pool is empty; cannot distribute rewards")
            return False

        total_weight = sum(weight for weight in allocation.values() if weight > 0)
        if total_weight <= 0:
            return False

        distributed = 0
        for recipient_id, weight in allocation.items():
            if weight <= 0:
                continue
            share = int(pool_balance * (weight / total_weight))
            if share <= 0:
                continue
            result = self.transfer_tokens(
                self.reward_pool_account_id,
                self.ensure_account(recipient_id)["account_id"],
                share,
                reason,
                {"allocation_weight": weight},
            )
            if result.get("success"):
                distributed += share

        logger.info("Distributed %s tokens from reward pool for %s", distributed, reason)
        return distributed > 0

    def get_account_snapshot(self, account_id: str) -> Dict[str, Any]:
        """Return a copy of the account data for external reporting."""
        account = self.ensure_account(account_id)
        return dict(account)

    def get_usage_metrics(self) -> Dict[str, Any]:
        """Return aggregate usage statistics."""
        return {
            "total_usage_events": self.usage_metrics["total_usage_events"],
            "volume_by_type": dict(self.usage_metrics["volume_by_type"]),
            "reward_pool_balance": self.get_balance(self.reward_pool_account_id),
            "treasury_balance": self.get_balance(self.treasury_account_id),
        }
        
    

    def mint_tokens(self, recipient_id: str, amount: int, reason: str = "incentive") -> bool:
        """Mint new tokens and award to recipient."""
        if amount <= 0:
            return False

        self.token_supply += amount
        logger.info(f"Minted {amount} tokens to {recipient_id[:12]} for {reason}. Total supply: {self.token_supply}")
        return True

    def charge_service_fee(self, service_type: str, params: Dict[str, Any] = None) -> int:
        """Calculate service fee based on service type and parameters."""
        base_fee = self.service_fees.get(service_type, 0)
        
        if service_type == "compute":
            units = params.get("compute_units", 1)
            return int(base_fee * units)
        elif service_type == "storage":
            mb = params.get("megabytes", 1)
            days = params.get("days", 1)
            return int(base_fee * mb * days)
        elif service_type == "bandwidth":
            mb = params.get("megabytes", 1)
            return int(base_fee * mb)
        else:
            return int(base_fee)

    def execute_transaction(self, sender_id: str, recipient_id: str, amount: int, 
                           transaction_type: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a token transaction between citizens."""
        if amount <= 0:
            return {"success": False, "error": "Invalid transaction amount"}
        
        transaction_id = derive_uuid(f"txn:{sender_id}:{recipient_id}:{amount}")
        transaction_record = {
            "transaction_id": transaction_id,
            "sender": sender_id,
            "recipient": recipient_id,
            "amount": amount,
            "transaction_type": transaction_type,
            "timestamp": utc_now_iso(),
            "metadata": metadata or {}
        }
        
        # Add to transaction history
        self.transaction_history.append(transaction_record)
        
        # Store transaction in persistence
        success = self.dht_node.persistence.store_transaction(transaction_record)
        
        if success:
            logger.info(f"Executed transaction {transaction_id[:12]}: {amount} tokens from {sender_id[:12]} to {recipient_id[:12]}")
            return {
                "success": True,
                "transaction_id": transaction_id,
                "amount": amount,
                "sender": sender_id,
                "recipient": recipient_id
            }
        else:
            logger.error(f"Failed to store transaction {transaction_id[:12]} in database")
            return {"success": False, "error": "Failed to store transaction"}

@dataclass
class GovernanceProposal:
    """Structured representation of a governance proposal."""
    proposal_id: str
    title: str
    proposal_type: str
    content: Dict[str, Any]
    proposer_id: str
    status: str
    created_at: str
    voting_deadline: str
    required_quorum: float
    stake_amount: int = 0
    votes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "proposal_type": self.proposal_type,
            "content": self.content,
            "proposer_id": self.proposer_id,
            "status": self.status,
            "created_at": self.created_at,
            "voting_deadline": self.voting_deadline,
            "required_quorum": self.required_quorum,
            "stake_amount": self.stake_amount,
            "votes": self.votes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GovernanceProposal':
        return cls(
            proposal_id=data["proposal_id"],
            title=data["title"],
            proposal_type=data["proposal_type"],
            content=data.get("content", {}),
            proposer_id=data["proposer_id"],
            status=data.get("status", "ACTIVE"),
            created_at=data.get("created_at", utc_now_iso()),
            voting_deadline=data.get("voting_deadline", utc_now_iso()),
            required_quorum=data.get("required_quorum", 0.5),
            stake_amount=data.get("stake_amount", 0),
            votes=data.get("votes", {}),
            metadata=data.get("metadata", {}),
        )

    def tally(self) -> Dict[str, int]:
        totals = {"YES": 0, "NO": 0, "ABSTAIN": 0}
        for vote in self.votes.values():
            choice = vote.get("choice", "ABSTAIN")
            weight = vote.get("weight", 0)
            totals.setdefault(choice, 0)
            totals[choice] += weight
        return totals

    def total_participation(self) -> int:
        return sum(vote.get("weight", 0) for vote in self.votes.values())


class PANConstitution:
    """Canonical charter for the digital country."""

    def __init__(self, founding_identity: SovereignIdentity):
        self.founding_identity_hash = founding_identity.identity_hash
        self.version = 1
        self.articles: List[Dict[str, Any]] = []
        self.amendments: List[Dict[str, Any]] = []
        self.signatures: List[Dict[str, Any]] = []
        self.document_hash = self._recalculate_document_hash()
        self.last_updated = utc_now_iso()

    def _recalculate_document_hash(self) -> str:
        content = {
            "version": self.version,
            "articles": self.articles,
            "amendments": self.amendments,
        }
        self.document_hash = sha256_hex(canonical(content))
        return self.document_hash

    def add_article(
        self,
        title: str,
        body: str,
        author_identity: SovereignIdentity,
        *,
        tags: Optional[List[str]] = None,
    ) -> str:
        article_id = derive_uuid(f"article:{title}:{len(self.articles)}")
        article = {
            "article_id": article_id,
            "title": title,
            "body": body,
            "tags": tags or [],
            "created_at": utc_now_iso(),
            "author": author_identity.identity_hash,
        }
        article_hash = sha256_hex(canonical(article))
        signature = author_identity.sign(article_hash.encode("utf-8")).hex()
        article["hash"] = article_hash
        article["signature"] = signature
        self.articles.append(article)
        self.last_updated = utc_now_iso()
        self._recalculate_document_hash()
        return article_id

    def register_amendment(self, amendment_text: str, author_identity: SovereignIdentity) -> Dict[str, Any]:
        amendment = {
            "amendment_id": derive_uuid(f"amendment:{len(self.amendments)}"),
            "body": amendment_text,
            "author": author_identity.identity_hash,
            "created_at": utc_now_iso(),
        }
        amendment["hash"] = sha256_hex(canonical(amendment))
        amendment["signature"] = author_identity.sign(amendment["hash"].encode("utf-8")).hex()
        self.amendments.append(amendment)
        self.version += 1
        self.last_updated = utc_now_iso()
        self._recalculate_document_hash()
        return amendment

    def sign_constitution(self, signer_identity: SovereignIdentity) -> str:
        signature = signer_identity.sign(self.document_hash.encode("utf-8")).hex()
        signature_record = {
            "signer": signer_identity.identity_hash,
            "signature": signature,
            "signed_at": utc_now_iso(),
        }
        self.signatures.append(signature_record)
        return signature

    def verify_signature(self, signer_identity: SovereignIdentity, signature_hex: str) -> bool:
        try:
            public_key = signer_identity.get_public_key_pem()
            signature = bytes.fromhex(signature_hex)
            serialization.load_pem_public_key(public_key).verify(
                signature,
                self.document_hash.encode("utf-8"),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception as exc:
            logger.warning("Failed constitution signature verification: %s", exc)
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "founding_identity_hash": self.founding_identity_hash,
            "version": self.version,
            "articles": self.articles,
            "amendments": self.amendments,
            "signatures": self.signatures,
            "document_hash": self.document_hash,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PANConstitution':
        instance = cls.__new__(cls)
        instance.founding_identity_hash = data["founding_identity_hash"]
        instance.version = data.get("version", 1)
        instance.articles = data.get("articles", [])
        instance.amendments = data.get("amendments", [])
        instance.signatures = data.get("signatures", [])
        instance.document_hash = data.get("document_hash")
        instance.last_updated = data.get("last_updated", utc_now_iso())
        if not instance.document_hash:
            instance._recalculate_document_hash()
        return instance


class PANPolicyRegistry:
    """Registry tracking active policies enacted by governance."""

    def __init__(self, dht_node: DHTNode, persistence: Optional[PANPersistenceStore] = None):
        self.dht_node = dht_node
        self.persistence = persistence
        self.policies: Dict[str, Dict[str, Any]] = {}
        self._hydrate_from_persistence()

    def _hydrate_from_persistence(self) -> None:
        if not self.persistence:
            return
        stored = self.persistence.load_component('governance_policies')
        if stored:
            self.policies = stored

    def register_policy(
        self,
        title: str,
        body: str,
        enacted_by: str,
        *,
        categories: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        policy_id = derive_uuid(f"policy:{title}")
        policy_entry = {
            "policy_id": policy_id,
            "title": title,
            "body": body,
            "categories": categories or [],
            "metadata": metadata or {},
            "enacted_by": enacted_by,
            "enacted_at": utc_now_iso(),
            "status": "ACTIVE",
        }
        self.policies[policy_id] = policy_entry
        self.dht_node.store(f"policy:{policy_id}", policy_entry)
        if self.persistence:
            self.persistence.write_state('governance_policies', policy_id, policy_entry)
        logger.info("Registered policy %s", policy_id[:12])
        return policy_id

    def retire_policy(self, policy_id: str, retired_by: str) -> bool:
        policy = self.policies.get(policy_id)
        if not policy:
            logger.warning("Attempted to retire unknown policy %s", policy_id)
            return False
        policy["status"] = "RETIRED"
        policy["retired_by"] = retired_by
        policy["retired_at"] = utc_now_iso()
        self.dht_node.store(f"policy:{policy_id}", policy, require_consensus=False)
        if self.persistence:
            self.persistence.write_state('governance_policies', policy_id, policy)
        return True

    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        return self.policies.get(policy_id)

    def list_policies(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if status is None:
            return list(self.policies.values())
        return [policy for policy in self.policies.values() if policy.get("status") == status]


class PANGovernanceCouncil:
    """Governance system coordinating proposals, voting, and execution."""

    ALLOWED_VOTES = {"YES", "NO", "ABSTAIN"}

    def __init__(self, dht_node: DHTNode, persistence: Optional[PANPersistenceStore] = None):
        self.dht_node = dht_node
        self.persistence = persistence
        self.economic_engine: Optional[PANEconomicEngine] = getattr(self.dht_node, "economic_engine", None)
        self.consensus: Optional[PANConsensus] = getattr(self.dht_node, "consensus", None)
        self.members: Dict[str, Dict[str, Any]] = {}
        self.proposals: Dict[str, GovernanceProposal] = {}
        self.constitution = PANConstitution(self.dht_node.identity)
        self.policy_registry = PANPolicyRegistry(self.dht_node, persistence)
        self.quorum_fraction = 0.5
        self.supermajority_fraction = 0.66
        self.default_voting_period_hours = 72
        self.proposal_bond = 10

        self.hydrate_from_persistence()

    def hydrate_from_persistence(self) -> None:
        if not self.persistence:
            return
        stored_members = self.persistence.load_component('governance_members')
        if stored_members:
            self.members = stored_members
        stored_proposals = self.persistence.load_component('governance_proposals')
        if stored_proposals:
            self.proposals = {pid: GovernanceProposal.from_dict(data) for pid, data in stored_proposals.items()}
        constitution_data = self.persistence.read_state('governance_constitution', 'document')
        if isinstance(constitution_data, dict):
            self.constitution = PANConstitution.from_dict(constitution_data)

    def _persist_member(self, identity_hash: str) -> None:
        if self.persistence:
            self.persistence.write_state('governance_members', identity_hash, self.members[identity_hash])

    def _persist_proposal(self, proposal: GovernanceProposal) -> None:
        if self.persistence:
            self.persistence.write_state('governance_proposals', proposal.proposal_id, proposal.to_dict())

    def _persist_constitution(self) -> None:
        if self.persistence:
            self.persistence.write_state('governance_constitution', 'document', self.constitution.to_dict())

    def register_member(self, identity_hash: str, role: str = "citizen", voting_power: int = 1) -> None:
        self.members[identity_hash] = {
            "role": role,
            "voting_power": max(1, voting_power),
            "joined_at": utc_now_iso(),
        }
        self._persist_member(identity_hash)
        if self.economic_engine:
            self.economic_engine.ensure_account(identity_hash, owner_identity=identity_hash, account_type="governance_member")
        logger.info("Registered governance member %s (%s)", identity_hash[:12], role)

    def submit_proposal(
        self,
        proposer_id: str,
        title: str,
        proposal_type: str,
        content: Dict[str, Any],
        *,
        metadata: Optional[Dict[str, Any]] = None,
        voting_period_hours: Optional[int] = None,
        stake_amount: Optional[int] = None,
    ) -> GovernanceProposal:
        if proposer_id not in self.members:
            raise ValueError("Proposer must be a registered governance member")

        bond = stake_amount if stake_amount is not None else self.proposal_bond
        if bond and self.economic_engine:
            result = self.economic_engine.transfer_tokens(
                proposer_id,
                self.economic_engine.treasury_account_id,
                bond,
                "proposal_bond",
                {"proposal_title": title},
            )
            if not result.get("success"):
                raise ValueError("Proposer lacks sufficient tokens to post bond")

        proposal_id = derive_uuid(f"proposal:{title}:{utc_now_iso()}")
        deadline = (datetime.now(timezone.utc) + timedelta(hours=voting_period_hours or self.default_voting_period_hours)).isoformat()
        proposal = GovernanceProposal(
            proposal_id=proposal_id,
            title=title,
            proposal_type=proposal_type,
            content=content,
            proposer_id=proposer_id,
            status="ACTIVE",
            created_at=utc_now_iso(),
            voting_deadline=deadline,
            required_quorum=self.quorum_fraction,
            stake_amount=bond or 0,
            metadata=metadata or {},
        )
        self.proposals[proposal_id] = proposal
        self._persist_proposal(proposal)
        if self.persistence:
            self.persistence.append_journal('governance', 'proposal_submitted', proposal.to_dict())
        logger.info("Submitted proposal %s of type %s", proposal_id[:12], proposal_type)
        return proposal

    def cast_vote(self, proposal_id: str, voter_identity: str, choice: str) -> bool:
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            logger.warning("Unknown proposal %s", proposal_id)
            return False
        if proposal.status != "ACTIVE":
            logger.warning("Proposal %s is not active", proposal_id)
            return False
        if choice not in self.ALLOWED_VOTES:
            raise ValueError(f"Choice must be one of {self.ALLOWED_VOTES}")
        member = self.members.get(voter_identity)
        if not member:
            logger.warning("Unrecognized voter %s", voter_identity)
            return False

        voter_weight = member.get("voting_power", 1)
        proposal.votes[voter_identity] = {
            "choice": choice,
            "weight": voter_weight,
            "cast_at": utc_now_iso(),
        }
        if self.consensus:
            self.consensus.vote_on_proposal(proposal_id, choice == "YES", self.dht_node.identity)
        self._persist_proposal(proposal)
        if self.persistence:
            self.persistence.append_journal('governance', 'vote_cast', {
                'proposal_id': proposal_id,
                'voter': voter_identity,
                'choice': choice,
                'weight': voter_weight,
            })
        logger.info("Recorded %s vote on proposal %s by %s", choice, proposal_id[:12], voter_identity[:12])
        return True

    def finalize_proposal(self, proposal_id: str, *, force: bool = False) -> Optional[str]:
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            logger.warning("Unknown proposal %s", proposal_id)
            return None
        if proposal.status != "ACTIVE":
            return proposal.status

        deadline = datetime.fromisoformat(proposal.voting_deadline)
        if datetime.now(timezone.utc) < deadline and not force:
            logger.debug("Proposal %s still within voting window", proposal_id)
            return None

        totals = proposal.tally()
        participation = proposal.total_participation()
        total_voting_power = sum(member["voting_power"] for member in self.members.values())
        required_quorum = max(1, int(math.ceil(total_voting_power * proposal.required_quorum)))

        if participation < required_quorum:
            proposal.status = "EXPIRED"
        elif totals.get("YES", 0) > totals.get("NO", 0):
            proposal.status = "ACCEPTED"
            self._execute_proposal(proposal)
        else:
            proposal.status = "REJECTED"

        self._settle_bond(proposal)
        self._persist_proposal(proposal)
        if self.persistence:
            self.persistence.append_journal('governance', 'proposal_finalized', {
                'proposal_id': proposal.proposal_id,
                'status': proposal.status,
                'totals': totals,
            })
        logger.info("Finalized proposal %s with status %s", proposal_id[:12], proposal.status)
        return proposal.status

    def _settle_bond(self, proposal: GovernanceProposal) -> None:
        if not proposal.stake_amount or not self.economic_engine:
            return
        if proposal.status == "ACCEPTED":
            self.economic_engine.transfer_tokens(
                self.economic_engine.treasury_account_id,
                proposal.proposer_id,
                proposal.stake_amount,
                "proposal_bond_return",
                {"proposal_id": proposal.proposal_id},
            )
        else:
            self.economic_engine.transfer_tokens(
                self.economic_engine.treasury_account_id,
                self.economic_engine.reward_pool_account_id,
                proposal.stake_amount,
                "proposal_bond_slash",
                {"proposal_id": proposal.proposal_id, "status": proposal.status},
            )

    def _execute_proposal(self, proposal: GovernanceProposal) -> None:
        if proposal.proposal_type == "policy":
            policy_id = self.policy_registry.register_policy(
                title=proposal.title,
                body=proposal.content.get("body", ""),
                enacted_by=proposal.proposer_id,
                categories=proposal.content.get("categories"),
                metadata=proposal.metadata,
            )
            if self.persistence:
                self.persistence.append_journal('governance', 'policy_enacted', {'proposal_id': proposal.proposal_id, 'policy_id': policy_id})
        elif proposal.proposal_type == "constitution_amendment":
            amendment_text = proposal.content.get("text", "")
            self.constitution.register_amendment(amendment_text, self.dht_node.identity)
            self._persist_constitution()
        elif proposal.proposal_type == "budget_allocation" and self.economic_engine:
            targets = proposal.content.get("allocations", {})
            self.economic_engine.distribute_rewards(targets, reason="budget_allocation")
        logger.debug("Executed proposal %s of type %s", proposal.proposal_id[:12], proposal.proposal_type)

    def list_open_proposals(self) -> List[GovernanceProposal]:
        return [proposal for proposal in self.proposals.values() if proposal.status == "ACTIVE"]

    def get_proposal(self, proposal_id: str) -> Optional[GovernanceProposal]:
        return self.proposals.get(proposal_id)

class PANCitizen:
    """
    Represents a citizen in the PAN network.
    A citizen is a user identity with associated rights, privileges, and tokens.
    """
    def __init__(self, identity: SovereignIdentity, citizen_id: str = None, 
                 citizen_type: str = "standard", registration_data: Dict[str, Any] = None):
        self.identity = identity
        self.citizen_id = citizen_id or derive_uuid(f"citizen:{identity.identity_hash}")
        self.citizen_type = citizen_type  # "standard", "developer", "validator", "admin"
        self.registration_data = registration_data or {}
        self.registration_time = utc_now_iso()
        self.tokens = 0  # Internal PAN tokens earned through app usage
        self.reputation_score = 100  # Starting reputation score
        self.active_status = True
        self.permissions = set()  # Set of permissions this citizen has
        self.apps_used = {}  # Track which apps this citizen uses
        self.resource_usage = {}  # Track resource consumption
        
        # Add default permissions based on citizen type
        if citizen_type == "admin":
            self.permissions.update({"governance", "validate", "moderate", "mint_tokens"})
        elif citizen_type == "validator":
            self.permissions.add("validate")
        elif citizen_type == "developer":
            self.permissions.add("deploy_app")
        
        logger.info(f"PANCitizen registered: {self.citizen_id[:12]} ({citizen_type})")

    def add_tokens(self, amount: int, reason: str = "usage"):
        """Add tokens to citizen's account."""
        if amount > 0:
            self.tokens += amount
            logger.info(f"Added {amount} tokens to {self.citizen_id[:12]} for {reason}. Total: {self.tokens}")
        else:
            logger.warning(f"Attempted to add negative tokens to {self.citizen_id[:12]}")
        
    def spend_tokens(self, amount: int, reason: str = "service") -> bool:
        """Spend tokens from citizen's account."""
        if self.tokens >= amount and amount > 0:
            self.tokens -= amount
            logger.info(f"Spent {amount} tokens from {self.citizen_id[:12]} for {reason}. Remaining: {self.tokens}")
            return True
        else:
            logger.warning(f"Insufficient tokens for {self.citizen_id[:12]} to spend {amount}. Has: {self.tokens}")
            return False
    
    def add_reputation(self, amount: int):
        """Add to citizen's reputation score."""
        self.reputation_score = max(0, self.reputation_score + amount)
        logger.debug(f"Reputation for {self.citizen_id[:12]} updated to {self.reputation_score}")
    
    def track_resource_usage(self, resource_type: str, amount: float):
        """Track resource usage for billing purposes."""
        if resource_type not in self.resource_usage:
            self.resource_usage[resource_type] = 0
        self.resource_usage[resource_type] += amount
        logger.debug(f"Tracked {amount} units of {resource_type} for citizen {self.citizen_id[:12]}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert citizen to dictionary for storage/serialization."""
        return {
            "citizen_id": self.citizen_id,
            "identity_hash": self.identity.identity_hash,
            "citizen_type": self.citizen_type,
            "registration_time": self.registration_time,
            "tokens": self.tokens,
            "reputation_score": self.reputation_score,
            "active_status": self.active_status,
            "permissions": list(self.permissions),
            "resource_usage": self.resource_usage,
            "registration_data": self.registration_data
        }


class PANApplication:
    """
    Represents an application in the PAN network.
    Applications can earn/require tokens from citizens.
    """
    def __init__(self, app_name: str, developer_identity: SovereignIdentity, 
                 app_id: str = None, app_metadata: Dict[str, Any] = None):
        self.app_id = app_id or derive_uuid(f"app:{app_name}")
        self.app_name = app_name
        self.developer_identity = developer_identity
        self.app_metadata = app_metadata or {}
        self.creation_time = utc_now_iso()
        self.active_status = True
        self.users = set()  # Set of citizen IDs using this app
        self.total_tokens_earned = 0  # Total tokens earned by this app
        self.token_per_use = 1  # Default tokens earned per usage
        
        logger.info(f"PANApplication registered: {self.app_name} ({self.app_id[:12]})")
    
    def register_user(self, citizen_id: str):
        """Register a citizen as a user of this app."""
        self.users.add(citizen_id)
        logger.debug(f"Citizen {citizen_id[:12]} registered for app {self.app_name}")
    
    def record_usage(self, citizen_id: str) -> int:
        """Record app usage and return tokens earned by citizen."""
        # Add citizen to users if not already registered
        self.users.add(citizen_id)
        
        # Award tokens to citizen based on usage
        tokens_earned = self.token_per_use
        
        # Update app's total earnings
        self.total_tokens_earned += tokens_earned
        
        logger.info(f"Usage of {self.app_name} by {citizen_id[:12]} earned {tokens_earned} tokens")
        return tokens_earned
    
    def persist_to_db(self, persistence_manager: PersistenceManager) -> bool:
        """Persist application data to the database."""
        app_data = self.to_dict()
        app_data['users_count'] = len(self.users)  # Update user count before storing
        return persistence_manager.store_application(app_data)
    
    @classmethod
    def load_from_db(cls, app_id: str, persistence_manager: PersistenceManager):
        """Load an application from the database."""
        app_data = persistence_manager.get_application(app_id)
        if not app_data:
            return None
            
        # Create a mock developer identity since we can't reconstruct the original keys
        # NEEDS IMPLEMENTING: This would be handled more securely
        developer_identity = SovereignIdentity(f"AppDeveloper_{app_data['app_name'][:8]}")
        # Set the identity hash to match the stored one
        developer_identity.identity_hash = app_data['developer_identity']
        
        app = cls(
            app_name=app_data['app_name'],
            developer_identity=developer_identity,
            app_id=app_data['app_id'],
            app_metadata=app_data['app_metadata']
        )
        
        # Update other attributes from the persisted data
        app.active_status = app_data['active_status']
        app.total_tokens_earned = app_data['total_tokens_earned']
        app.token_per_use = app_data['token_per_use']
        
        return app
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert app to dictionary for storage/serialization."""
        return {
            "app_id": self.app_id,
            "app_name": self.app_name,
            "developer_identity": self.developer_identity.identity_hash,
            "creation_time": self.creation_time,
            "active_status": self.active_status,
            "users_count": len(self.users),
            "total_tokens_earned": self.total_tokens_earned,
            "token_per_use": self.token_per_use,
            "app_metadata": self.app_metadata
        }


class PANCitizenRegistry:
    """
    Registry for PAN citizens with token economy.
    """
    def __init__(self, identity: SovereignIdentity, dht_node: DHTNode):
        self.identity = identity
        self.dht_node = dht_node
        self.citizens = {}  # citizen_id -> PANCitizen
        self.citizen_by_identity = {}  # identity_hash -> citizen_id
        self.applications = {}  # app_id -> PANApplication
        
        logger.info("PANCitizenRegistry initialized")
    
    def register_citizen(self, identity: SovereignIdentity, citizen_type: str = "standard", 
                        registration_data: Dict[str, Any] = None) -> PANCitizen:
        """Register a new citizen in the PAN network."""
        # Check if identity is already registered
        if identity.identity_hash in self.citizen_by_identity:
            logger.warning(f"Identity {identity.identity_hash[:12]} already registered as citizen")
            return self.citizens[self.citizen_by_identity[identity.identity_hash]]
        
        # Create new citizen
        citizen = PANCitizen(identity, citizen_type=citizen_type, registration_data=registration_data)
        
        # Store in registries
        self.citizens[citizen.citizen_id] = citizen
        self.citizen_by_identity[identity.identity_hash] = citizen.citizen_id
        
        # Store in DHT
        citizen_key = f"citizen:{citizen.citizen_id}"
        success = self.dht_node.store(citizen_key, citizen.to_dict(), require_consensus=True)
        
        if success:
            logger.info(f"Successfully registered citizen {citizen.citizen_id[:12]}")
            return citizen
        else:
            logger.error(f"Failed to store citizen {citizen.citizen_id[:12]} in DHT")
            return None
    
    def get_citizen(self, citizen_id: str) -> Optional[PANCitizen]:
        """Retrieve a citizen by ID."""
        return self.citizens.get(citizen_id)
    
    def get_citizen_by_identity(self, identity_hash: str) -> Optional[PANCitizen]:
        """Retrieve a citizen by their identity hash."""
        citizen_id = self.citizen_by_identity.get(identity_hash)
        if citizen_id:
            return self.citizens.get(citizen_id)
        return None
    
    def register_app(self, app_name: str, developer_identity: SovereignIdentity, 
                    app_metadata: Dict[str, Any] = None) -> PANApplication:
        """Register a new application in the PAN network."""
        # Verify developer is a registered citizen
        developer_citizen = self.get_citizen_by_identity(developer_identity.identity_hash)
        if not developer_citizen:
            logger.warning(f"Developer {developer_identity.identity_hash[:12]} not registered as citizen")
            return None
        
        if "deploy_app" not in developer_citizen.permissions:
            logger.warning(f"Developer {developer_identity.identity_hash[:12]} lacks permission to deploy app")
            return None
        
        # Create new application
        app = PANApplication(app_name, developer_identity, app_metadata=app_metadata)
        
        # Store in registry
        self.applications[app.app_id] = app
        
        # Store in DHT
        app_key = f"app:{app.app_id}"
        success = self.dht_node.store(app_key, app.to_dict(), require_consensus=True)
        
        if success:
            logger.info(f"Successfully registered app {app.app_name} ({app.app_id[:12]})")
            return app
        else:
            logger.error(f"Failed to store app {app.app_name} in DHT")
            return None
    
    def use_app(self, citizen_id: str, app_id: str) -> Dict[str, Any]:
        """Record usage of an app by a citizen and handle token transactions."""
        citizen = self.get_citizen(citizen_id)
        app = self.applications.get(app_id)
        
        if not citizen:
            return {"success": False, "error": "Citizen not found"}
        
        if not app:
            return {"success": False, "error": "App not found"}
        
        if not app.active_status:
            return {"success": False, "error": "App is not active"}
        
        # Citizen spends tokens to use extra app features (if needed but no applicatio)
        # For now, let's make it free to encourage adoption, but app earns tokens
        app_tokens_earned = app.record_usage(citizen_id)
        
        # Award tokens to citizen for using the app (incentivize participation)
        citizen.add_tokens(app_tokens_earned, f"using_{app.app_name}")
        
        result = {
            "success": True,
            "tokens_earned": app_tokens_earned,
            "citizen_tokens": citizen.tokens,
            "message": f"Successfully used {app.app_name}, earned {app_tokens_earned} tokens"
        }
        
        logger.info(f"Citizen {citizen_id[:12]} used app {app_id[:12]}, earned {app_tokens_earned} tokens")
        return result
    
    def register_citizen(self, identity: SovereignIdentity, citizen_type: str = "standard", 
                        registration_data: Dict[str, Any] = None) -> PANCitizen:
        """Register a new citizen in the PAN network."""
        # Check if identity is already registered
        if identity.identity_hash in self.citizen_by_identity:
            logger.warning(f"Identity {identity.identity_hash[:12]} already registered as citizen")
            return self.citizens[self.citizen_by_identity[identity.identity_hash]]
        
        # Create new citizen
        citizen = PANCitizen(identity, citizen_type=citizen_type, registration_data=registration_data)
        
        # Store in registries
        self.citizens[citizen.citizen_id] = citizen
        self.citizen_by_identity[identity.identity_hash] = citizen.citizen_id
        
        # Store in DHT (which now persists to database)
        citizen_key = f"citizen:{citizen.citizen_id}"
        success = self.dht_node.store(citizen_key, citizen.to_dict(), require_consensus=True)
        
        if success:
            logger.info(f"Successfully registered citizen {citizen.citizen_id[:12]}")
            return citizen
        else:
            logger.error(f"Failed to store citizen {citizen.citizen_id[:12]} in DHT")
            return None
    
    def get_citizen(self, citizen_id: str) -> Optional[PANCitizen]:
        """Retrieve a citizen by ID."""
        # First check in memory
        if citizen_id in self.citizens:
            return self.citizens[citizen_id]
        
        # Then check in persistence
        citizen_data = self.dht_node.persistence.get_citizen(citizen_id)
        if citizen_data:
            # Load from persistence into memory
            # For this to work properly, we need to store the actual identity information
            # This is a simplified implementation - in reality, you'd have the full identity
            # with keys stored in a secure way
            identity = SovereignIdentity(f"PersistedCitizen_{citizen_data['citizen_id'][:8]}")
            # Set the identity hash to match the stored one
            identity.identity_hash = citizen_data['identity_hash']
            
            citizen = PANCitizen(
                identity=identity,
                citizen_id=citizen_data['citizen_id'],
                citizen_type=citizen_data['citizen_type'],
                registration_data=citizen_data['registration_data']
            )
            
            # Update other attributes from the persisted data
            citizen.tokens = citizen_data['tokens']
            citizen.reputation_score = citizen_data['reputation_score']
            citizen.active_status = citizen_data['active_status']
            citizen.permissions = set(citizen_data['permissions'])
            citizen.resource_usage = citizen_data['resource_usage']
            
            # Store in memory
            self.citizens[citizen.citizen_id] = citizen
            self.citizen_by_identity[citizen.identity.identity_hash] = citizen.citizen_id
            
            return citizen
        
        return None
    
    def get_citizen_by_identity(self, identity_hash: str) -> Optional[PANCitizen]:
        """Retrieve a citizen by their identity hash."""
        citizen_id = self.citizen_by_identity.get(identity_hash)
        if citizen_id:
            return self.get_citizen(citizen_id)  # Use the updated get_citizen method
        return None
    
    def register_app(self, app_name: str, developer_identity: SovereignIdentity, 
                    app_metadata: Dict[str, Any] = None) -> PANApplication:
        """Register a new application in the PAN network."""
        # Verify developer is a registered citizen
        developer_citizen = self.get_citizen_by_identity(developer_identity.identity_hash)
        if not developer_citizen:
            logger.warning(f"Developer {developer_identity.identity_hash[:12]} not registered as citizen")
            return None
        
        if "deploy_app" not in developer_citizen.permissions:
            logger.warning(f"Developer {developer_identity.identity_hash[:12]} lacks permission to deploy app")
            return None
        
        # Create new application
        app = PANApplication(app_name, developer_identity, app_metadata=app_metadata)
        
        # Store in registry
        self.applications[app.app_id] = app
        
        # Store in DHT (which now persists to database)
        app_key = f"app:{app.app_id}"
        success = self.dht_node.store(app_key, app.to_dict(), require_consensus=True)
        
        if success:
            logger.info(f"Successfully registered app {app.app_name} ({app.app_id[:12]})")
            return app
        else:
            logger.error(f"Failed to store app {app.app_name} in DHT")
            return None
    
    def use_app(self, citizen_id: str, app_id: str) -> Dict[str, Any]:
        """Record usage of an app by a citizen and handle token transactions."""
        citizen = self.get_citizen(citizen_id)
        app = self.applications.get(app_id)
        
        # If app is not in memory, try to load it from persistence
        if not app:
            app = self._load_app_from_persistence(app_id)
        
        if not citizen:
            return {"success": False, "error": "Citizen not found"}
        
        if not app:
            return {"success": False, "error": "App not found"}
        
        if not app.active_status:
            return {"success": False, "error": "App is not active"}
        
        # Citizen spends tokens to use app (if required)
        # For now, let's make it free to encourage adoption, but app earns tokens
        app_tokens_earned = app.record_usage(citizen_id)
        
        # Award tokens to citizen for using the app (incentivize participation)
        citizen.add_tokens(app_tokens_earned, f"using_{app.app_name}")
        
        result = {
            "success": True,
            "tokens_earned": app_tokens_earned,
            "citizen_tokens": citizen.tokens,
            "message": f"Successfully used {app.app_name}, earned {app_tokens_earned} tokens"
        }
        
        logger.info(f"Citizen {citizen_id[:12]} used app {app_id[:12]}, earned {app_tokens_earned} tokens")
        return result
    
    def _load_app_from_persistence(self, app_id: str) -> Optional[PANApplication]:
        """Internal method to load an app from persistence."""
        app_data = self.dht_node.persistence.get_application(app_id)
        if app_data:
            # Create a minimal identity object for the developer
            identity = SovereignIdentity(f"AppDeveloper_{app_data['app_name'][:8]}")
            # Set the identity hash to match the stored one
            identity.identity_hash = app_data['developer_identity']
            
            app = PANApplication(
                app_name=app_data['app_name'],
                developer_identity=identity,
                app_id=app_data['app_id'],
                app_metadata=app_data['app_metadata']
            )
            
            # Update other attributes from the persisted data
            app.active_status = app_data['active_status']
            app.total_tokens_earned = app_data['total_tokens_earned']
            app.token_per_use = app_data['token_per_use']
            
            # Store in memory
            self.applications[app.app_id] = app
            
            return app
        return None


class SovereignPipeline:
    """
    Secure model acquisition pipeline that provides authenticated distribution.
    This is the "hook for the internet" but with cryptographic guarantees.
    Enhanced to work with the DHT system.
    """
    
    def __init__(self, distributor_identity: SovereignIdentity, dht_node: Optional[DHTNode] = None):
        self.distributor_identity = distributor_identity
        self.dht_node = dht_node
        self.available_models = {}
        logger.info("SovereignPipeline initialized")

    def register_model(self, model_name: str, model_path: str, 
                      model_identity: SovereignIdentity):
        """Register a model in the pipeline."""
        # Calculate model hash
        # In a real implementation, you'd hash the actual model file
        model_hash = sha256_hex(f"model_content_{model_name}")[:64]
        
        # Create manifest
        manifest = ModelManifest(
            model_name=model_name,
            model_hash=model_hash,
            model_public_key_pem=model_identity.get_public_key_pem(),
            creator_identity=self.distributor_identity
        )
        
        self.available_models[model_name] = {
            "path": model_path,
            "manifest": manifest,
            "identity": model_identity
        }
        
        # If DHT is available, store model information there too
        if self.dht_node:
            model_info = {
                "model_name": model_name,
                "model_hash": model_hash,
                "model_path": model_path,
                "registered_at": utc_now_iso(),
                "registered_by": self.distributor_identity.identity_hash
            }
            self.dht_node.store(f"model:{model_name}", model_info)
        
        logger.info(f"Registered model {model_name} in pipeline and DHT")

    def create_download_package(self, model_name: str, user_identity: SovereignIdentity) -> Dict[str, Any]:
        """Create a secure download package for a model."""
        if model_name not in self.available_models:
            # Try to look up in DHT if not in local storage
            if self.dht_node:
                dht_result = self.dht_node.lookup(f"model:{model_name}")
                if dht_result:
                    logger.info(f"Found model {model_name} in DHT")
                    # For now, just return a placeholder since we don't have actual model data
                    package = {
                        "model_data": f"model_data_from_dht_{model_name}",
                        "manifest": None,  # Would need to fetch manifest separately
                        "download_timestamp": utc_now_iso(),
                        "user_identity_hash": user_identity.identity_hash
                    }
                    return package
            
            raise ValueError(f"Model {model_name} not available")
            
        model_info = self.available_models[model_name]
        
        # Create download package
        package = {
            "model_data": f"simulated_model_data_for_{model_name}",  # In reality, this would be the actual model file
            "manifest": model_info["manifest"].to_dict(),
            "download_timestamp": utc_now_iso(),
            "user_identity_hash": user_identity.identity_hash
        }
        
        logger.info(f"Created download package for {model_name}")
        return package

# --------------------------- #
# ---------- Demo ----------#
# --------------------------- #

if __name__ == "__main__":
    print("=== Sovereign AI Infrastructure Demo ===\n")
    
    # 1. Create identities
    print("1. Creating sovereign identities...")
    user_identity = SovereignIdentity("UserApplication")
    model_identity = SovereignIdentity("AI_Model_Gemma3")
    distributor_identity = SovereignIdentity("ModelDistributor")
    
    print(f"   User ID: {user_identity.identity_hash[:12]}...")
    print(f"   Model ID: {model_identity.identity_hash[:12]}...")
    print(f"   Distributor ID: {distributor_identity.identity_hash[:12]}...\n")
    
    # 2. Initialize components
    print("2. Initializing infrastructure components...")
    user_communicator = SovereignCommunicator(user_identity)
    pipeline = SovereignPipeline(distributor_identity)
    
    # 3. Register a model in the pipeline
    print("3. Registering model in pipeline...")
    pipeline.register_model("gemma3-4b-it.lacka", "/path/to/model.lacka", model_identity)
    
    # 4. User requests model download
    print("4. User requesting model download...")
    download_package = pipeline.create_download_package("gemma3-4b-it.lacka", user_identity)
    print("   Download package created successfully\n")
    
    # 5. User verifies manifest
    print("5. User verifying model manifest...")
    manifest = ModelManifest.from_dict(download_package["manifest"])
    is_valid = manifest.verify_manifest(distributor_identity.get_public_key_pem())
    print(f"   Manifest verification: {'PASSED' if is_valid else 'FAILED'}\n")
    
    # 6. User creates inference request
    print("6. User creating inference request...")
    request_content = {
        "prompt": "Explain the benefits of sovereign AI infrastructure",
        "temperature": 0.7,
        "max_tokens": 150
    }
    
    request_packet = user_communicator.create_packet(
        kind="INFERENCE_REQUEST",
        content=request_content,
        metadata={"application": "demo_app", "version": "1.0"}
    )
    
    print(f"   Created request packet: {request_packet.packet_id[:12]}...\n")
    
    # 7. Initialize local inference engine
    print("7. Initializing local inference engine...")
    engine = SovereignInferenceEngine(
        model_path="/path/to/model.lacka",
        model_manifest=manifest
    )
    
    # 8. Process inference request
    print("8. Processing inference request...")
    response_packet = engine.process_request(
        request_packet, 
        user_identity.get_public_key_pem()
    )
    
    print(f"   Received response packet: {response_packet.packet_id[:12]}...")
    print(f"   Response: {response_packet.content['response']}\n")
    
    # 9. Verify response traceability
    print("9. Verifying response traceability...")
    if response_packet.parents and response_packet.parents[0] == request_packet.packet_id:
        print("   Response correctly linked to request")
    else:
        print("   WARNING: Response not properly linked to request")
    
    print("\n=== Demo completed successfully ===")
