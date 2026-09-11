"""
Sovereign Firewall - Anti-Surveillance Wrapper for Data Flows
A middleware that wraps PAN pipelines in "firewall" rules: auto-detects/blocks 
"suspicious" patterns (e.g., telemetry-like exports or external API calls),
compresses sensitive data on-the-fly, and logs to the offline ledger.
"""
import re
from typing import Optional, Callable, Dict, Any
from .PAN_SDK import UnifiedDataPacket, sha256_hex


class SovereignFirewall:
    def __init__(self):
        self.rules = {  # User-configurable rules
            "block_telemetry": re.compile(r"(?i)(google|palantir|nist|api\.cloud|telemetry|metrics|analytics|log\.|track)"),  # Pattern match
            "compress_sensitive": lambda content: any(keyword in str(content).lower() 
                                                    for keyword in ["sensitive", "private", "secret", "token", "password", "key"]),
            "log_all": True
        }
        self.blocked_count = 0
        self.allowed_count = 0
        self.blocked_packets = []  # Keep track of blocked packets for analysis
        self.ledger_log = []  # Offline ledger for firewall events
    
    def inspect_packet(self, packet: UnifiedDataPacket, custom_rule: Optional[Callable] = None) -> bool:
        """Inspect and filter packet; return True if allowed."""
        try:
            content_str = str(packet.content)
            
            # Check for surveillance patterns
            if self.rules["block_telemetry"].search(content_str):
                self._log_block("Telemetry detected", packet.packet_id, packet.content)
                self.blocked_count += 1
                self.blocked_packets.append({
                    "packet_id": packet.packet_id,
                    "reason": "telemetry_pattern",
                    "timestamp": packet.timestamp
                })
                return False
            
            # Auto-compress sensitive data (placeholder for .lacka, and all other bespoke Somnus model and other binary formats. Needs to be extended to include general sensitive data not just model or binary architectures.)
            if self.rules["compress_sensitive"](packet.content):
                original_content = packet.content
                packet.content = self._mock_lacka_compress(packet.content)  # Your real .lacka here
                packet.content_hash = sha256_hex(str(packet.content))
                self._log_event("Compressed sensitive data", packet.packet_id, {"original_size": len(str(original_content)), "compressed_size": len(str(packet.content))})
            
            # Custom user rule (e.g., "only allow PAN-routed")
            if custom_rule and not custom_rule(packet):
                self._log_block("Custom rule violation", packet.packet_id, packet.content)
                self.blocked_count += 1
                return False
            
            # Check for non-PAN destinations
            if hasattr(packet, 'destination_identity_hash') and packet.destination_identity_hash:
                # In a real implementation, we'd verify this is a known PAN identity
                # For now, we'll assume PAN identities have a specific format or are in a registry
                pass
            
            self.allowed_count += 1
            self._log_event("Allowed packet", packet.packet_id, {"kind": packet.kind})
            return True
            
        except Exception as e:
            self._log_block("Inspection error", packet.packet_id, {"error": str(e)})
            self.blocked_count += 1
            return False
    
    def _mock_lacka_compress(self, data: Any) -> str:
        """Placeholder that should be removed and replaced as .lacka is now longer in consideration for pan_sdk or distribution Compress with lacka logic for compression of data at high ratio."""
        # Real impl: data -> .lacka binary -> base64 or bytes
        original_size = len(str(data))
        compressed_size = max(1, original_size // 1000)  # Simulate high compression ratio
        return f".lacka_compressed_data_size_{compressed_size}"
    
    def _log_event(self, event: str, packet_id: str, metadata: Dict[str, Any] = None):
        if self.rules["log_all"]:
            log_entry = {
                "event": event,
                "packet_id": packet_id[:12],  # Short ID
                "timestamp": "now",  # Would be actual timestamp in real implementation
                "metadata": metadata or {}
            }
            self.ledger_log.append(log_entry)
            print(f"[FIREWALL] {event} for packet {packet_id[:8]}")  # Ledger this in real SDK
    
    def _log_block(self, event: str, packet_id: str, content: Any):
        """Log blocked packets with details."""
        self._log_event(f"BLOCKED: {event}", packet_id, {"content_preview": str(content)[:100]})
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "blocks": self.blocked_count,
            "allowed": self.allowed_count,
            "total_processed": self.blocked_count + self.allowed_count,
            "rules_active": len(self.rules),
            "blocked_packets": len(self.blocked_packets),
            "ledger_entries": len(self.ledger_log)
        }
    
    def add_custom_rule(self, name: str, rule_func: Callable[[UnifiedDataPacket], bool]):
        """Add a custom rule function to the firewall."""
        self.rules[name] = rule_func
    
    def block_identity(self, identity_hash: str):
        """Add an identity hash to the blocklist."""
        if "identity_blocklist" not in self.rules:
            self.rules["identity_blocklist"] = set()
        self.rules["identity_blocklist"].add(identity_hash)
    
    def is_identity_blocked(self, identity_hash: str) -> bool:
        """Check if an identity is blocked."""
        blocklist = self.rules.get("identity_blocklist", set())
        return identity_hash in blocklist
    
    def inspect_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inspect content directly (not as a packet) and return a sanitized version.
        Useful for inspecting content before packet creation.
        """
        content_str = str(content)
        result = {
            "blocked": False,
            "sanitized_content": content,
            "reason": None,
            "modified": False
        }
        
        # Check for telemetry patterns
        if self.rules["block_telemetry"].search(content_str):
            result["blocked"] = True
            result["reason"] = "telemetry_content"
            return result
        
        # Check for sensitive data and potentially compress it
        if self.rules["compress_sensitive"](content):
            result["sanitized_content"] = self._mock_lacka_compress(content)
            result["modified"] = True
            result["reason"] = "sensitive_content_compressed"
        
        return result


# Example usage
if __name__ == "__main__":
    print("=== Sovereign Firewall Demo ===\n")
    
    fw = SovereignFirewall()
    
    # Test with simulated packet
    from .PAN_SDK import UnifiedDataPacket, SovereignIdentity
    
    identity = SovereignIdentity("TestUser")
    
    # Safe packet
    safe_packet = UnifiedDataPacket(
        packet_id="test123",
        kind="CHAT_MESSAGE",
        content={"message": "Hello in the sovereign network", "timestamp": "now"},
        author_identity_hash=identity.identity_hash,
        timestamp="now",
        parents=[],
        metadata={}
    )
    
    is_allowed = fw.inspect_packet(safe_packet)
    print(f"Safe packet allowed: {is_allowed}")
    
    # Telemetry packet (should be blocked)
    telemetry_packet = UnifiedDataPacket(
        packet_id="telem456",
        kind="METRICS_UPLOAD",
        content={"data": "user_activity_data_for_google_analytics", "count": 42},
        author_identity_hash=identity.identity_hash,
        timestamp="now",
        parents=[],
        metadata={}
    )
    
    is_allowed = fw.inspect_packet(telemetry_packet)
    print(f"Telemetry packet allowed: {is_allowed}")
    
    # Sensitive data packet (should be compressed)
    sensitive_packet = UnifiedDataPacket(
        packet_id="sens789",
        kind="DATA_TRANSFER",
        content={"private_token": "abc123def456", "user_data": "sensitive information"},
        author_identity_hash=identity.identity_hash,
        timestamp="now",
        parents=[],
        metadata={}
    )
    
    original_hash = sensitive_packet.content_hash
    is_allowed = fw.inspect_packet(sensitive_packet)
    print(f"Sensitive packet allowed: {is_allowed}")
    print(f"Content was modified: {sensitive_packet.content != {'private_token': 'abc123def456', 'user_data': 'sensitive information'}}")
    
    # Status report
    status = fw.get_status()
    print(f"\nFirewall Status: {status}")
    print("\n=== Firewall demo completed ===")