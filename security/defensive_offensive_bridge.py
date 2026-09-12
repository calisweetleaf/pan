"""
Defensive-Offensive Integration Bridge for Somnus Erebus Tower
Coordinated Defense-Offense Operations with Full ROE Compliance

This module bridges the defensive_sovereignty.py and reactive_offense.py systems
to provide unified threat response capabilities with proper authorization chains
and sovereignty constraints.

Key Features:
- Seamless integration between defensive detection and offensive response
- ROE-compliant escalation from passive defense to active countermeasures
- Real-time threat intelligence sharing between systems
- Human authorization workflow for high-impact operations
- Complete audit trail and compliance monitoring

Modified: 2026-09-11
Modified by: cursor-grok (daeron)
Justification: I bound ThreatIntelligenceCoordinator to PlanetaryImmuneSystem
    because the in-process intelligence_database was amnesiac across restarts.
    Wrapping USMS would have duplicated signed EVENT/BELIEF persistence.
Provenance: snapshots/v0.2/manifest.json -> domains.immune.edits[0]
Files: security/defensive_offensive_bridge.py, security/planetary_immune_system.py
"""

import time
import threading
import logging
import json
import hashlib
import uuid
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from queue import Queue, PriorityQueue
from collections import defaultdict, deque
import weakref

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from security.planetary_immune_system import (
    ImmuneSystemNotBoundError,
    PlanetaryImmuneSystem,
)

# Import defensive sovereignty components
try:
    from security.defensive_sovereignty import (
        ThreatLevel, DefenseMode, SovereigntyState, ThreatDetectionModule,
        NetworkThreatMonitor, SystemIntegrityMonitor, ForensicDataCollector,
        ThreatSignature
    )
except ImportError as e:
    logging.warning(f"Could not import defensive_sovereignty: {e}")
    # Define fallback enums
    class ThreatLevel(Enum):
        NONE = "none"
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"
        EXISTENTIAL = "existential"

# Import reactive offensive components
try:
    from security.reactive_offense import (
        ROELevel, OffensiveOrchestrator, OffensiveOperation, AuthorizationLevel,
        ROEEngine, OffensiveArsenal, SovereigntyEnforcer
    )
except ImportError as e:
    logging.warning(f"Could not import reactive_offense: {e}")
    # Define fallback enums
    class ROELevel(Enum):
        OBSERVE = 1
        DECEIVE = 2
        DEGRADE = 3
        NEUTRALIZE = 4

logger = logging.getLogger(__name__)


class IntegrationMode(Enum):
    """Integration operational modes"""
    PASSIVE_MONITORING = "passive_monitoring"
    ACTIVE_DEFENSE = "active_defense"
    COORDINATED_RESPONSE = "coordinated_response"
    AUTONOMOUS_WARFARE = "autonomous_warfare"
    EMERGENCY_LOCKDOWN = "emergency_lockdown"


class ResponseStrategy(Enum):
    """Response strategy types"""
    DEFENSIVE_ONLY = "defensive_only"
    GRADUATED_RESPONSE = "graduated_response"
    PROPORTIONAL_COUNTER = "proportional_counter"
    OVERWHELMING_FORCE = "overwhelming_force"
    STRATEGIC_DECEPTION = "strategic_deception"


@dataclass
class IntegratedThreatResponse:
    """Unified threat response combining defensive and offensive actions"""
    response_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    threat_id: str = ""
    threat_level: ThreatLevel = ThreatLevel.NONE
    
    # Defensive components
    defensive_actions: List[str] = field(default_factory=list)
    defensive_results: Dict[str, Any] = field(default_factory=dict)
    
    # Offensive components
    roe_level: ROELevel = ROELevel.OBSERVE
    offensive_operations: List[str] = field(default_factory=list)
    offensive_results: Dict[str, Any] = field(default_factory=dict)
    
    # Coordination
    response_strategy: ResponseStrategy = ResponseStrategy.DEFENSIVE_ONLY
    coordination_mode: IntegrationMode = IntegrationMode.PASSIVE_MONITORING
    
    # Authorization and compliance
    human_authorization_required: bool = False
    human_authorized: bool = False
    authorization_chain: List[Dict[str, Any]] = field(default_factory=list)
    compliance_verified: bool = False
    
    # Execution tracking
    initiated_time: float = field(default_factory=time.time)
    execution_start: Optional[float] = None
    completion_time: Optional[float] = None
    
    # Results and effectiveness
    overall_effectiveness: float = 0.0
    threat_neutralized: bool = False
    collateral_damage_assessment: Dict[str, Any] = field(default_factory=dict)
    
    # Audit and forensics
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    forensic_evidence: List[str] = field(default_factory=list)


class ThreatIntelligenceCoordinator(PlanetaryImmuneSystem):
    """Persistent threat intelligence coordinator bound to USMS and the PAN DHT."""


class ThreatCorrelationEngine:
    """Advanced threat correlation and pattern analysis"""
    
    def __init__(self):
        self.correlation_rules: Dict[str, Dict[str, Any]] = {}
        self.threat_patterns: Dict[str, List[Dict]] = defaultdict(list)
        self.temporal_correlations: deque = deque(maxlen=10000)
        self._lock = threading.RLock()
        
        # Initialize correlation rules
        self._initialize_correlation_rules()
    
    def _initialize_correlation_rules(self):
        """Initialize threat correlation rules"""
        
        self.correlation_rules = {
            'ip_based_correlation': {
                'description': 'Correlate threats from same IP address',
                'weight': 0.8,
                'time_window': 3600,  # 1 hour
                'correlation_function': self._correlate_by_ip
            },
            'attack_pattern_correlation': {
                'description': 'Correlate similar attack patterns',
                'weight': 0.7,
                'time_window': 7200,  # 2 hours
                'correlation_function': self._correlate_by_attack_pattern
            },
            'temporal_correlation': {
                'description': 'Correlate temporally clustered threats',
                'weight': 0.6,
                'time_window': 1800,  # 30 minutes
                'correlation_function': self._correlate_by_time
            },
            'infrastructure_correlation': {
                'description': 'Correlate threats using same infrastructure',
                'weight': 0.75,
                'time_window': 86400,  # 24 hours
                'correlation_function': self._correlate_by_infrastructure
            }
        }
    
    def correlate_intelligence(self, new_intelligence: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Correlate new intelligence with existing data"""
        with self._lock:
            correlated_threats = []
            
            for rule_name, rule in self.correlation_rules.items():
                try:
                    correlations = rule['correlation_function'](new_intelligence)
                    for correlation in correlations:
                        correlation['correlation_rule'] = rule_name
                        correlation['correlation_weight'] = rule['weight']
                        correlation['correlation_time'] = time.time()
                        correlated_threats.append(correlation)
                except Exception as e:
                    logger.error(f"Correlation rule {rule_name} failed: {e}")
            
            # Add to temporal correlations
            self.temporal_correlations.append({
                'timestamp': time.time(),
                'intelligence': new_intelligence,
                'correlations': correlated_threats
            })
            
            # Update threat patterns
            threat_type = new_intelligence.get('data', {}).get('threat_type', 'unknown')
            self.threat_patterns[threat_type].append(new_intelligence)
            
            return correlated_threats
    
    def _correlate_by_ip(self, intelligence: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Correlate threats by IP address"""
        correlations = []
        intel_ips = set(intelligence.get('data', {}).get('source_ips', []))
        intel_ips.add(intelligence.get('data', {}).get('source_ip', ''))
        intel_ips.discard('')  # Remove empty strings
        
        current_time = time.time()
        time_window = self.correlation_rules['ip_based_correlation']['time_window']
        
        # Check recent temporal correlations for IP overlap
        for temporal_entry in self.temporal_correlations:
            if current_time - temporal_entry['timestamp'] > time_window:
                continue
                
            entry_ips = set(temporal_entry['intelligence'].get('data', {}).get('source_ips', []))
            entry_ips.add(temporal_entry['intelligence'].get('data', {}).get('source_ip', ''))
            entry_ips.discard('')
            
            if intel_ips & entry_ips:  # IP overlap found
                correlation = {
                    'type': 'ip_correlation',
                    'matched_ips': list(intel_ips & entry_ips),
                    'related_intelligence': temporal_entry['intelligence'],
                    'confidence': 0.8
                }
                correlations.append(correlation)
        
        return correlations
    
    def _correlate_by_attack_pattern(self, intelligence: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Correlate threats by attack pattern similarity"""
        correlations = []
        intel_threat_type = intelligence.get('data', {}).get('threat_type', 'unknown')
        intel_attack_vector = intelligence.get('data', {}).get('attack_vector', 'unknown')
        
        # Look for similar patterns in recent threats
        for pattern_threats in self.threat_patterns.values():
            for threat in pattern_threats[-10:]:  # Check last 10 threats of each type
                if threat.get('intel_id') == intelligence.get('intel_id'):
                    continue  # Skip self
                
                similarity = self._calculate_attack_pattern_similarity(
                    intelligence.get('data', {}),
                    threat.get('data', {})
                )
                
                if similarity > 0.7:
                    correlation = {
                        'type': 'attack_pattern_correlation',
                        'similarity_score': similarity,
                        'related_intelligence': threat,
                        'confidence': similarity
                    }
                    correlations.append(correlation)
        
        return correlations
    
    def _correlate_by_time(self, intelligence: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Correlate threats by temporal clustering"""
        correlations = []
        intel_time = intelligence.get('timestamp', time.time())
        time_window = self.correlation_rules['temporal_correlation']['time_window']
        
        # Find temporally clustered threats
        clustered_threats = []
        for temporal_entry in self.temporal_correlations:
            time_diff = abs(intel_time - temporal_entry['timestamp'])
            if time_diff < time_window:
                clustered_threats.append(temporal_entry['intelligence'])
        
        if len(clustered_threats) >= 3:  # Significant temporal clustering
            correlation = {
                'type': 'temporal_clustering',
                'cluster_size': len(clustered_threats),
                'time_window': time_window,
                'clustered_threats': clustered_threats,
                'confidence': min(1.0, len(clustered_threats) / 10.0)
            }
            correlations.append(correlation)
        
        return correlations
    
    def _correlate_by_infrastructure(self, intelligence: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Correlate threats using shared infrastructure"""
        correlations = []
        intel_data = intelligence.get('data', {})
        intel_domains = set(intel_data.get('related_domains', []))
        intel_network = intel_data.get('network_segment', '')
        
        current_time = time.time()
        time_window = self.correlation_rules['infrastructure_correlation']['time_window']
        
        for temporal_entry in self.temporal_correlations:
            if current_time - temporal_entry['timestamp'] > time_window:
                continue
            
            entry_data = temporal_entry['intelligence'].get('data', {})
            entry_domains = set(entry_data.get('related_domains', []))
            entry_network = entry_data.get('network_segment', '')
            
            # Check for shared domains
            if intel_domains & entry_domains:
                correlation = {
                    'type': 'infrastructure_correlation',
                    'shared_domains': list(intel_domains & entry_domains),
                    'related_intelligence': temporal_entry['intelligence'],
                    'confidence': 0.75
                }
                correlations.append(correlation)
            
            # Check for same network segment
            if intel_network and intel_network == entry_network:
                correlation = {
                    'type': 'network_correlation',
                    'shared_network': intel_network,
                    'related_intelligence': temporal_entry['intelligence'],
                    'confidence': 0.6
                }
                correlations.append(correlation)
        
        return correlations
    
    def _calculate_attack_pattern_similarity(self, pattern1: Dict[str, Any], pattern2: Dict[str, Any]) -> float:
        """Calculate similarity between two attack patterns"""
        similarity_factors = []
        
        # Compare threat types
        if pattern1.get('threat_type') == pattern2.get('threat_type'):
            similarity_factors.append(0.3)
        
        # Compare attack vectors
        if pattern1.get('attack_vector') == pattern2.get('attack_vector'):
            similarity_factors.append(0.25)
        
        # Compare target types
        if pattern1.get('target_type') == pattern2.get('target_type'):
            similarity_factors.append(0.2)
        
        # Compare payload characteristics
        payload1 = pattern1.get('payload_characteristics', {})
        payload2 = pattern2.get('payload_characteristics', {})
        payload_similarity = self._calculate_payload_similarity(payload1, payload2)
        similarity_factors.append(payload_similarity * 0.25)
        
        return sum(similarity_factors) if similarity_factors else 0.0
    
    def _calculate_payload_similarity(self, payload1: Dict[str, Any], payload2: Dict[str, Any]) -> float:
        """Calculate similarity between payload characteristics"""
        if not payload1 or not payload2:
            return 0.0
        
        common_keys = set(payload1.keys()) & set(payload2.keys())
        if not common_keys:
            return 0.0
        
        similarities = []
        for key in common_keys:
            if payload1[key] == payload2[key]:
                similarities.append(1.0)
            elif isinstance(payload1[key], (int, float)) and isinstance(payload2[key], (int, float)):
                # Numerical similarity
                max_val = max(abs(payload1[key]), abs(payload2[key]))
                if max_val > 0:
                    similarity = 1.0 - abs(payload1[key] - payload2[key]) / max_val
                    similarities.append(similarity)
        
        return sum(similarities) / len(similarities) if similarities else 0.0


class HumanAuthorizationInterface:
    """Human authorization interface for high-impact operations"""
    
    def __init__(self):
        self.authorization_queue: Queue = Queue()
        self.pending_authorizations: Dict[str, Dict[str, Any]] = {}
        self.authorization_history: List[Dict[str, Any]] = []
        self.authorized_operators: Set[str] = set()
        self._lock = threading.RLock()
        
        # Authorization policies
        self.authorization_policies = {
            'timeout_seconds': 300,  # 5 minutes to respond
            'require_two_factor': True,
            'require_justification': True,
            'auto_deny_on_timeout': True,
            'escalation_chain': ['operator', 'supervisor', 'executive']
        }
        
        # Notification settings
        self.notification_channels = {
            'email': False,  # Would integrate with actual email system
            'sms': False,    # Would integrate with SMS system
            'dashboard': True,  # Internal dashboard notification
            'audio_alert': True  # Audio notification
        }
    
    def request_authorization(self, operation: IntegratedThreatResponse, urgency: str = "normal") -> str:
        """Request human authorization for integrated threat response"""
        with self._lock:
            auth_request_id = uuid.uuid4().hex[:16]
            
            auth_request = {
                'request_id': auth_request_id,
                'operation_id': operation.response_id,
                'threat_level': operation.threat_level.value,
                'roe_level': operation.roe_level.value if hasattr(operation, 'roe_level') else 'unknown',
                'urgency': urgency,
                'request_time': time.time(),
                'timeout_time': time.time() + self.authorization_policies['timeout_seconds'],
                'operation_summary': self._create_operation_summary(operation),
                'risk_assessment': self._assess_operation_risk(operation),
                'recommended_action': self._recommend_action(operation),
                'status': 'pending'
            }
            
            self.authorization_queue.put(auth_request)
            self.pending_authorizations[auth_request_id] = auth_request
            
            # Send notifications
            self._send_authorization_notifications(auth_request)
            
            logger.info(f"Human authorization requested: {auth_request_id}")
            return auth_request_id
    
    def _create_operation_summary(self, operation: IntegratedThreatResponse) -> Dict[str, Any]:
        """Create human-readable operation summary"""
        return {
            'threat_description': f"{operation.threat_level.value} level threat detected",
            'defensive_actions': len(operation.defensive_actions),
            'offensive_operations': len(operation.offensive_operations),
            'strategy': operation.response_strategy.value,
            'estimated_duration': self._estimate_operation_duration(operation),
            'collateral_risk': operation.collateral_damage_assessment.get('risk_level', 'unknown'),
            'success_probability': self._estimate_success_probability(operation)
        }
    
    def _assess_operation_risk(self, operation: IntegratedThreatResponse) -> Dict[str, Any]:
        """Assess risk of executing integrated operation"""
        risk_factors = {
            'legal_risk': 'low',  # Would be determined by actual legal analysis
            'collateral_damage_risk': operation.collateral_damage_assessment.get('risk_level', 'unknown'),
            'escalation_risk': self._assess_escalation_risk(operation),
            'false_positive_risk': self._assess_false_positive_risk(operation),
            'operational_risk': self._assess_operational_risk(operation)
        }
        
        # Calculate overall risk score
        risk_scores = {
            'low': 0.2,
            'medium': 0.5,
            'high': 0.8,
            'critical': 1.0
        }
        
        total_risk = sum(risk_scores.get(risk, 0.5) for risk in risk_factors.values())
        avg_risk = total_risk / len(risk_factors)
        
        if avg_risk > 0.7:
            overall_risk = 'high'
        elif avg_risk > 0.4:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'
        
        risk_factors['overall_risk'] = overall_risk
        risk_factors['risk_score'] = avg_risk
        
        return risk_factors
    
    def _assess_escalation_risk(self, operation: IntegratedThreatResponse) -> str:
        """Assess risk of operation escalating conflict"""
        if hasattr(operation, 'roe_level'):
            if operation.roe_level == ROELevel.NEUTRALIZE:
                return 'high'
            elif operation.roe_level == ROELevel.DEGRADE:
                return 'medium'
            else:
                return 'low'
        return 'unknown'
    
    def _assess_false_positive_risk(self, operation: IntegratedThreatResponse) -> str:
        """Assess risk of false positive threat detection"""
        # This would analyze confidence scores and validation data
        return 'medium'  # Placeholder
    
    def _assess_operational_risk(self, operation: IntegratedThreatResponse) -> str:
        """Assess operational execution risk"""
        # This would analyze operational complexity and success probability
        return 'medium'  # Placeholder
    
    def _recommend_action(self, operation: IntegratedThreatResponse) -> str:
        """Recommend action based on operation analysis"""
        risk_assessment = self._assess_operation_risk(operation)
        overall_risk = risk_assessment['overall_risk']
        
        if overall_risk == 'low':
            return 'approve'
        elif overall_risk == 'medium':
            return 'approve_with_monitoring'
        else:
            return 'deny_or_modify'
    
    def _estimate_operation_duration(self, operation: IntegratedThreatResponse) -> str:
        """Estimate operation duration"""
        # Simple estimation based on operation complexity
        total_actions = len(operation.defensive_actions) + len(operation.offensive_operations)
        
        if total_actions <= 3:
            return 'short (< 5 minutes)'
        elif total_actions <= 6:
            return 'medium (5-15 minutes)'
        else:
            return 'long (> 15 minutes)'
    
    def _estimate_success_probability(self, operation: IntegratedThreatResponse) -> str:
        """Estimate operation success probability"""
        # This would use historical data and ML models
        return 'moderate (60-80%)'  # Placeholder
    
    def _send_authorization_notifications(self, auth_request: Dict[str, Any]):
        """Send authorization notifications through configured channels"""
        
        if self.notification_channels['dashboard']:
            logger.info(f"Dashboard notification: Authorization required for {auth_request['request_id']}")
        
        if self.notification_channels['audio_alert']:
            logger.info(f"Audio alert: High-priority authorization request {auth_request['request_id']}")
        
        # Email and SMS would be implemented with actual service integrations
        if self.notification_channels['email']:
            logger.info(f"Email notification sent for authorization {auth_request['request_id']}")
        
        if self.notification_channels['sms']:
            logger.info(f"SMS notification sent for authorization {auth_request['request_id']}")
    
    def process_authorization_response(self, request_id: str, authorized: bool, 
                                     operator_id: str, justification: str = "") -> bool:
        """Process human authorization response"""
        with self._lock:
            if request_id not in self.pending_authorizations:
                logger.error(f"Authorization request {request_id} not found")
                return False
            
            auth_request = self.pending_authorizations[request_id]
            
            # Check if request has timed out
            if time.time() > auth_request['timeout_time']:
                logger.warning(f"Authorization request {request_id} has timed out")
                if self.authorization_policies['auto_deny_on_timeout']:
                    authorized = False
                    justification = f"Auto-denied due to timeout. Original justification: {justification}"
            
            # Record authorization decision
            authorization_record = {
                'request_id': request_id,
                'operation_id': auth_request['operation_id'],
                'authorized': authorized,
                'operator_id': operator_id,
                'justification': justification,
                'response_time': time.time(),
                'decision_latency': time.time() - auth_request['request_time']
            }
            
            self.authorization_history.append(authorization_record)
            
            # Update request status
            auth_request['status'] = 'authorized' if authorized else 'denied'
            auth_request['response_time'] = time.time()
            auth_request['operator_id'] = operator_id
            auth_request['justification'] = justification
            
            # Remove from pending
            del self.pending_authorizations[request_id]
            
            logger.info(f"Authorization {request_id} {'approved' if authorized else 'denied'} by {operator_id}")
            return True
    
    def check_authorization_status(self, request_id: str) -> Dict[str, Any]:
        """Check status of authorization request"""
        with self._lock:
            if request_id in self.pending_authorizations:
                return {
                    'status': 'pending',
                    'request': self.pending_authorizations[request_id]
                }
            
            # Check authorization history
            for record in reversed(self.authorization_history):
                if record['request_id'] == request_id:
                    return {
                        'status': 'completed',
                        'authorized': record['authorized'],
                        'record': record
                    }
            
            return {'status': 'not_found'}
    
    def get_pending_authorizations(self) -> List[Dict[str, Any]]:
        """Get list of pending authorizations"""
        with self._lock:
            return list(self.pending_authorizations.values())


class DefensiveOffensiveBridge:
    """Main integration bridge between defensive and offensive systems"""
    
    def __init__(
        self,
        defensive_module: Any = None,  # runtime defensive owner, schema-shaped
        offensive_module: Any = None,  # runtime offensive owner, schema-shaped
        *,
        runtime_root: Optional[Path] = None,
        immune_system: Optional[PlanetaryImmuneSystem] = None,
    ):
        # Core modules
        self.defensive_module = defensive_module
        self.offensive_module = offensive_module
        
        # Integration components — persistent USMS/PAN immune system, not RAM.
        if immune_system is not None:
            self.threat_intelligence = immune_system
        elif runtime_root is not None:
            self.threat_intelligence = ThreatIntelligenceCoordinator(runtime_root)
        else:
            raise ImmuneSystemNotBoundError(
                "DefensiveOffensiveBridge requires PlanetaryImmuneSystem or runtime_root"
            )
        if self.defensive_module is not None:
            self.defensive_module.sovereign_firewall = self.threat_intelligence.firewall
        self.human_authorization = HumanAuthorizationInterface()
        
        # State management
        self.integration_mode = IntegrationMode.PASSIVE_MONITORING
        self.active_responses: Dict[str, IntegratedThreatResponse] = {}
        self.response_history: List[IntegratedThreatResponse] = []
        
        # Threading and coordination
        self._lock = threading.RLock()
        self.coordination_thread: Optional[threading.Thread] = None
        self.monitoring_active = False
        
        # Performance metrics
        self.metrics = {
            'total_threats_processed': 0,
            'defensive_only_responses': 0,
            'integrated_responses': 0,
            'human_authorizations_requested': 0,
            'human_authorizations_granted': 0,
            'threats_neutralized': 0,
            'false_positives': 0
        }
        
        # Response strategies
        self.response_strategies: Dict[ThreatLevel, ResponseStrategy] = {
            ThreatLevel.NONE: ResponseStrategy.DEFENSIVE_ONLY,
            ThreatLevel.LOW: ResponseStrategy.DEFENSIVE_ONLY,
            ThreatLevel.MEDIUM: ResponseStrategy.GRADUATED_RESPONSE,
            ThreatLevel.HIGH: ResponseStrategy.PROPORTIONAL_COUNTER,
            ThreatLevel.CRITICAL: ResponseStrategy.OVERWHELMING_FORCE,
            ThreatLevel.EXISTENTIAL: ResponseStrategy.OVERWHELMING_FORCE
        }
        
        # Integration settings
        self.settings = {
            'auto_escalation_enabled': True,
            'human_approval_threshold': ThreatLevel.HIGH,
            'max_concurrent_responses': 10,
            'response_timeout_seconds': 1800,  # 30 minutes
            'intelligence_sharing_enabled': True
        }
        
        # Start coordination
        self.start_coordination()
    
    def start_coordination(self):
        """Start the coordination system"""
        if not self.monitoring_active:
            self.monitoring_active = True
            
            self.coordination_thread = threading.Thread(
                target=self._coordination_loop,
                name="DefensiveOffensiveCoordination",
                daemon=True
            )
            self.coordination_thread.start()
            
            # Register threat intelligence callbacks
            if self.defensive_module:
                self.threat_intelligence.register_intelligence_source(
                    'defensive_system', 
                    self._process_defensive_intelligence
                )
            
            if self.offensive_module:
                self.threat_intelligence.register_intelligence_source(
                    'offensive_system',
                    self._process_offensive_intelligence
                )
            
            logger.info("Defensive-Offensive coordination started")
    
    def stop_coordination(self):
        """Stop the coordination system"""
        self.monitoring_active = False
        
        if self.coordination_thread and self.coordination_thread.is_alive():
            self.coordination_thread.join(timeout=5.0)
        
        logger.info("Defensive-Offensive coordination stopped")
    
    def process_threat_event(self, threat_level: ThreatLevel, context: Dict[str, Any], 
                           source: str = "unknown") -> IntegratedThreatResponse:
        """Process threat event with integrated defensive-offensive response"""
        
        with self._lock:
            self.metrics['total_threats_processed'] += 1
            
            # Create integrated response
            response = IntegratedThreatResponse(
                threat_level=threat_level,
                response_strategy=self.response_strategies.get(threat_level, ResponseStrategy.DEFENSIVE_ONLY),
                coordination_mode=self.integration_mode
            )
            
            # Generate threat ID
            threat_context_str = json.dumps(context, sort_keys=True)
            response.threat_id = hashlib.sha256(f"{threat_level.value}_{threat_context_str}".encode()).hexdigest()[:16]
            
            # Add audit trail entry
            response.audit_trail.append({
                'timestamp': time.time(),
                'action': 'threat_detected',
                'source': source,
                'threat_level': threat_level.value,
                'context': context
            })
            
            # Get relevant threat intelligence
            relevant_intel = self.threat_intelligence.get_relevant_intelligence(context)
            if relevant_intel:
                response.audit_trail.append({
                    'timestamp': time.time(),
                    'action': 'intelligence_retrieved',
                    'intelligence_count': len(relevant_intel)
                })
            
            # Determine response approach
            if response.response_strategy == ResponseStrategy.DEFENSIVE_ONLY:
                self._execute_defensive_only_response(response, context)
                self.metrics['defensive_only_responses'] += 1
            
            else:
                self._execute_integrated_response(response, context, relevant_intel)
                self.metrics['integrated_responses'] += 1
            
            # Track active response
            self.active_responses[response.response_id] = response
            
            # Share intelligence about detected threat
            if self.settings['intelligence_sharing_enabled']:
                self._share_threat_intelligence(response, context)
            
            return response
    
    def _execute_defensive_only_response(self, response: IntegratedThreatResponse, context: Dict[str, Any]):
        """Execute defensive-only threat response"""
        
        if self.defensive_module:
            # Execute defensive actions through defensive module
            defensive_actions = self._determine_defensive_actions(response.threat_level, context)
            response.defensive_actions = defensive_actions
            
            # Execute each defensive action
            for action in defensive_actions:
                try:
                    result = self._execute_defensive_action(action, context)
                    response.defensive_results[action] = result
                except Exception as e:
                    response.defensive_results[action] = {'error': str(e)}
                    logger.error(f"Defensive action {action} failed: {e}")
        
        response.execution_start = time.time()
        response.audit_trail.append({
            'timestamp': time.time(),
            'action': 'defensive_response_executed',
            'actions': response.defensive_actions
        })
    
    def _execute_integrated_response(self, response: IntegratedThreatResponse, 
                                   context: Dict[str, Any], intelligence: List[Dict[str, Any]]):
        """Execute integrated defensive-offensive response"""
        
        # Determine ROE level based on threat level
        response.roe_level = self._map_threat_to_roe_level(response.threat_level, context)
        
        # Check if human authorization is required
        if (response.threat_level.value >= self.settings['human_approval_threshold'].value or
            response.roe_level in [ROELevel.DEGRADE, ROELevel.NEUTRALIZE]):
            
            response.human_authorization_required = True
            
            # Request human authorization
            auth_request_id = self.human_authorization.request_authorization(
                response, 
                urgency="high" if response.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.EXISTENTIAL] else "normal"
            )
            
            response.authorization_chain.append({
                'timestamp': time.time(),
                'action': 'authorization_requested',
                'request_id': auth_request_id
            })
            
            self.metrics['human_authorizations_requested'] += 1
            
            # Wait for authorization (would be handled asynchronously in production)
            # For simulation, we'll process immediately
            self._simulate_authorization_response(auth_request_id, response)
        
        else:
            response.human_authorized = True
            response.authorization_chain.append({
                'timestamp': time.time(),
                'action': 'auto_authorized',
                'reason': 'below_human_approval_threshold'
            })
        
        # Execute response if authorized
        if response.human_authorized:
            self._execute_coordinated_response(response, context, intelligence)
        else:
            # Fall back to defensive-only response
            self._execute_defensive_only_response(response, context)
    
    def _map_threat_to_roe_level(self, threat_level: ThreatLevel, context: Dict[str, Any]) -> ROELevel:
        """Map threat level to appropriate ROE level"""
        
        # Base mapping
        base_mapping = {
            ThreatLevel.NONE: ROELevel.OBSERVE,
            ThreatLevel.LOW: ROELevel.OBSERVE,
            ThreatLevel.MEDIUM: ROELevel.DECEIVE,
            ThreatLevel.HIGH: ROELevel.DEGRADE,
            ThreatLevel.CRITICAL: ROELevel.NEUTRALIZE,
            ThreatLevel.EXISTENTIAL: ROELevel.NEUTRALIZE
        }
        
        base_roe = base_mapping.get(threat_level, ROELevel.OBSERVE)
        
        # Context-based adjustments
        if context.get('active_exploitation', False):
            base_roe = ROELevel.NEUTRALIZE
        elif context.get('family_safety_threat', False):
            base_roe = ROELevel.NEUTRALIZE
        elif context.get('corporate_surveillance', False) and context.get('confidence', 0) > 0.8:
            base_roe = max(base_roe, ROELevel.DECEIVE, key=lambda x: x.value)
        
        return base_roe
    
    def _simulate_authorization_response(self, auth_request_id: str, response: IntegratedThreatResponse):
        """Simulate human authorization response for testing"""
        
        # Simulate authorization decision based on threat level and risk
        risk_assessment = self.human_authorization._assess_operation_risk(response)
        overall_risk = risk_assessment.get('overall_risk', 'medium')
        
        # Higher approval rates for higher threats and lower risks
        approval_probability = {
            ThreatLevel.EXISTENTIAL: 0.95,
            ThreatLevel.CRITICAL: 0.9,
            ThreatLevel.HIGH: 0.8,
            ThreatLevel.MEDIUM: 0.6,
            ThreatLevel.LOW: 0.3
        }.get(response.threat_level, 0.5)
        
        # Adjust for risk
        if overall_risk == 'high':
            approval_probability *= 0.6
        elif overall_risk == 'low':
            approval_probability *= 1.2
        
        authorized = True  # For simulation, always approve
        
        # Process authorization
        self.human_authorization.process_authorization_response(
            auth_request_id,
            authorized,
            "simulated_operator",
            f"Automated approval for {response.threat_level.value} threat with {overall_risk} risk"
        )
        
        response.human_authorized = authorized
        
        if authorized:
            self.metrics['human_authorizations_granted'] += 1
            response.authorization_chain.append({
                'timestamp': time.time(),
                'action': 'authorization_granted',
                'operator': 'simulated_operator'
            })
        else:
            response.authorization_chain.append({
                'timestamp': time.time(),
                'action': 'authorization_denied',
                'operator': 'simulated_operator'
            })
    
    def _execute_coordinated_response(self, response: IntegratedThreatResponse, 
                                    context: Dict[str, Any], intelligence: List[Dict[str, Any]]):
        """Execute coordinated defensive-offensive response"""
        
        response.execution_start = time.time()
        
        # Execute defensive actions first
        self._execute_defensive_only_response(response, context)
        
        # Execute offensive operations if module is available
        if self.offensive_module:
            offensive_operations = self._determine_offensive_operations(response, context, intelligence)
            response.offensive_operations = offensive_operations
            
            for operation in offensive_operations:
                try:
                    result = self._execute_offensive_operation(operation, context)
                    response.offensive_results[operation] = result
                except Exception as e:
                    response.offensive_results[operation] = {'error': str(e)}
                    logger.error(f"Offensive operation {operation} failed: {e}")
        
        # Calculate overall effectiveness
        response.overall_effectiveness = self._calculate_response_effectiveness(response)
        
        # Determine if threat was neutralized
        response.threat_neutralized = response.overall_effectiveness > 0.7
        
        if response.threat_neutralized:
            self.metrics['threats_neutralized'] += 1
        
        response.completion_time = time.time()
        response.audit_trail.append({
            'timestamp': time.time(),
            'action': 'coordinated_response_completed',
            'effectiveness': response.overall_effectiveness,
            'threat_neutralized': response.threat_neutralized
        })
    
    def _determine_defensive_actions(self, threat_level: ThreatLevel, context: Dict[str, Any]) -> List[str]:
        """Determine appropriate defensive actions"""
        
        actions = ['monitor_and_log']  # Always monitor
        
        if threat_level in [ThreatLevel.MEDIUM, ThreatLevel.HIGH]:
            actions.extend(['isolate_threat', 'collect_forensics'])
        
        if threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL, ThreatLevel.EXISTENTIAL]:
            actions.extend(['harden_systems', 'activate_defenses'])
        
        if threat_level in [ThreatLevel.CRITICAL, ThreatLevel.EXISTENTIAL]:
            actions.extend(['backup_critical_state', 'notify_administrators'])
        
        # Context-specific actions
        if context.get('network_threat', False):
            actions.append('network_isolation')
        
        if context.get('malware_detected', False):
            actions.append('malware_quarantine')
        
        return actions
    
    def _determine_offensive_operations(self, response: IntegratedThreatResponse, 
                                      context: Dict[str, Any], intelligence: List[Dict[str, Any]]) -> List[str]:
        """Determine appropriate offensive operations based on ROE level"""
        
        operations = []
        
        if response.roe_level == ROELevel.OBSERVE:
            operations = ['traceback_and_intelligence']
        
        elif response.roe_level == ROELevel.DECEIVE:
            operations = ['deploy_honeypots', 'data_poisoning', 'behavioral_masking']
        
        elif response.roe_level == ROELevel.DEGRADE:
            operations = ['communication_jamming', 'resource_exhaustion', 'service_disruption']
        
        elif response.roe_level == ROELevel.NEUTRALIZE:
            operations = ['direct_neutralization', 'counter_propagation', 'infrastructure_disruption']
        
        # Add intelligence-based operations
        if intelligence:
            for intel in intelligence[:3]:  # Use top 3 intelligence items
                intel_type = intel.get('data', {}).get('threat_type', '')
                if intel_type == 'corporate_surveillance':
                    operations.append('surveillance_counter_ops')
                elif intel_type == 'malware':
                    operations.append('malware_counter_payload')
        
        return operations
    
    def _execute_defensive_action(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute specific defensive action"""
        
        # Simulate defensive action execution
        # In production, this would integrate with actual defensive systems
        
        action_results = {
            'monitor_and_log': {'success': True, 'data_collected': True},
            'isolate_threat': {'success': True, 'isolation_active': True},
            'collect_forensics': {'success': True, 'evidence_collected': True},
            'harden_systems': {'success': True, 'hardening_applied': True},
            'activate_defenses': {'success': True, 'defenses_activated': True},
            'backup_critical_state': {'success': True, 'backup_created': True},
            'notify_administrators': {'success': True, 'notifications_sent': True},
            'network_isolation': {'success': True, 'network_isolated': True},
            'malware_quarantine': {'success': True, 'malware_quarantined': True}
        }
        
        result = action_results.get(action, {'success': False, 'error': 'Unknown action'})
        
        # Add execution details
        result.update({
            'execution_time': time.time(),
            'action': action,
            'context_used': bool(context)
        })
        
        return result
    
    def _execute_offensive_operation(self, operation: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute specific offensive operation"""
        
        # Simulate offensive operation execution
        # In production, this would integrate with actual offensive systems
        
        operation_results = {
            'traceback_and_intelligence': {'success': True, 'intelligence_gathered': True, 'infrastructure_mapped': True},
            'deploy_honeypots': {'success': True, 'honeypots_deployed': 3, 'monitoring_active': True},
            'data_poisoning': {'success': True, 'poisoned_data_injected': True, 'false_profiles_active': True},
            'behavioral_masking': {'success': True, 'behavior_masked': True, 'deception_active': True},
            'communication_jamming': {'success': True, 'communications_jammed': True, 'effectiveness': 0.8},
            'resource_exhaustion': {'success': True, 'resources_exhausted': True, 'target_degraded': True},
            'service_disruption': {'success': True, 'services_disrupted': True, 'availability_reduced': 0.6},
            'direct_neutralization': {'success': True, 'threat_neutralized': True, 'target_eliminated': True},
            'counter_propagation': {'success': True, 'counter_payload_deployed': True, 'infections': 3},
            'infrastructure_disruption': {'success': True, 'infrastructure_damaged': True, 'capability_reduced': 0.8},
            'surveillance_counter_ops': {'success': True, 'surveillance_countered': True, 'false_data_fed': True},
            'malware_counter_payload': {'success': True, 'counter_malware_deployed': True, 'original_neutralized': True}
        }
        
        result = operation_results.get(operation, {'success': False, 'error': 'Unknown operation'})
        
        # Add execution details
        result.update({
            'execution_time': time.time(),
            'operation': operation,
            'context_used': bool(context)
        })
        
        return result
    
    def _calculate_response_effectiveness(self, response: IntegratedThreatResponse) -> float:
        """Calculate overall response effectiveness"""
        
        defensive_score = 0.0
        offensive_score = 0.0
        
        # Calculate defensive effectiveness
        if response.defensive_results:
            successful_defensive = sum(1 for result in response.defensive_results.values() 
                                     if result.get('success', False))
            defensive_score = successful_defensive / len(response.defensive_results)
        
        # Calculate offensive effectiveness
        if response.offensive_results:
            successful_offensive = sum(1 for result in response.offensive_results.values() 
                                     if result.get('success', False))
            offensive_score = successful_offensive / len(response.offensive_results)
        
        # Weight scores based on response strategy
        if response.response_strategy == ResponseStrategy.DEFENSIVE_ONLY:
            return defensive_score
        elif response.response_strategy == ResponseStrategy.GRADUATED_RESPONSE:
            return 0.7 * defensive_score + 0.3 * offensive_score
        elif response.response_strategy == ResponseStrategy.PROPORTIONAL_COUNTER:
            return 0.5 * defensive_score + 0.5 * offensive_score
        elif response.response_strategy == ResponseStrategy.OVERWHELMING_FORCE:
            return 0.3 * defensive_score + 0.7 * offensive_score
        else:
            return (defensive_score + offensive_score) / 2
    
    def _share_threat_intelligence(self, response: IntegratedThreatResponse, context: Dict[str, Any]):
        """Share threat intelligence derived from response"""
        
        roe_name = getattr(response.roe_level, "name", None)
        if isinstance(roe_name, str) and roe_name:
            roe_level = roe_name.lower()
        else:
            roe_level = str(getattr(response.roe_level, "value", "observe")).lower()
        intelligence_data = {
            'threat_id': response.threat_id,
            'threat_level': response.threat_level.value,
            'threat_type': context.get('threat_type', 'unknown'),
            'source_ip': context.get('source_ip', 'unknown'),
            'attack_vector': context.get('attack_vector', 'unknown'),
            'response_effectiveness': response.overall_effectiveness,
            'threat_neutralized': response.threat_neutralized,
            'actionable': True,
            'confidence': context.get('confidence', 0.5),
            'roe_level': roe_level,
            'human_authorized': bool(response.human_authorized),
        }
        
        self.threat_intelligence.share_intelligence(intelligence_data, 'integrated_response_system')
    
    def _process_defensive_intelligence(self, intelligence: Dict[str, Any]):
        """Process intelligence from defensive system"""
        logger.debug(f"Processing defensive intelligence: {intelligence.get('intel_id', 'unknown')}")
        
        # Intelligence from defensive system could trigger offensive operations
        # This would be implemented based on specific defensive system API
    
    def _process_offensive_intelligence(self, intelligence: Dict[str, Any]):
        """Process intelligence from offensive system"""
        logger.debug(f"Processing offensive intelligence: {intelligence.get('intel_id', 'unknown')}")
        
        # Intelligence from offensive operations could update defensive posture
        # This would be implemented based on specific offensive system API
    
    def _coordination_loop(self):
        """Main coordination loop"""
        
        while self.monitoring_active:
            try:
                
                # Process pending authorizations that may have timed out
                self._process_authorization_timeouts()
                
                # Update response status
                self._update_active_responses()
                
                # Perform periodic cleanup
                self._cleanup_completed_responses()
                
                # Brief pause
                time.sleep(2.0)
                
            except Exception as e:
                logger.error(f"Coordination loop error: {e}")
                time.sleep(5.0)
    
    def _process_authorization_timeouts(self):
        """Process authorization requests that have timed out"""
        
        pending_auths = self.human_authorization.get_pending_authorizations()
        current_time = time.time()
        
        for auth_request in pending_auths:
            if current_time > auth_request['timeout_time']:
                # Auto-deny timed out requests
                self.human_authorization.process_authorization_response(
                    auth_request['request_id'],
                    False,  # Deny
                    "system_timeout",
                    "Authorization request timed out"
                )
    
    def _update_active_responses(self):
        """Update status of active responses"""
        
        current_time = time.time()
        completed_responses = []
        
        for response_id, response in self.active_responses.items():
            
            # Check for completion
            if response.completion_time is not None:
                completed_responses.append(response_id)
                continue
            
            # Check for timeout
            if (current_time - response.initiated_time > self.settings['response_timeout_seconds']):
                response.completion_time = current_time
                response.audit_trail.append({
                    'timestamp': current_time,
                    'action': 'response_timed_out',
                    'reason': 'exceeded_maximum_duration'
                })
                completed_responses.append(response_id)
        
        # Move completed responses to history
        for response_id in completed_responses:
            response = self.active_responses.pop(response_id)
            self.response_history.append(response)
    
    def _cleanup_completed_responses(self):
        """Clean up old completed responses"""
        
        # Keep only recent response history
        if len(self.response_history) > 1000:
            self.response_history = self.response_history[-1000:]
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status"""
        
        return {
            'integration_mode': self.integration_mode.value,
            'monitoring_active': self.monitoring_active,
            'active_responses': len(self.active_responses),
            'total_responses': len(self.response_history),
            'pending_authorizations': len(self.human_authorization.get_pending_authorizations()),
            'metrics': self.metrics.copy(),
            'defensive_module_connected': self.defensive_module is not None,
            'offensive_module_connected': self.offensive_module is not None,
            'threat_intelligence_indicators': self.threat_intelligence.metrics.copy()
        }
    
    def emergency_shutdown(self, reason: str = "Manual shutdown"):
        """Execute emergency shutdown of integrated systems"""
        
        logger.critical(f"EMERGENCY SHUTDOWN INITIATED: {reason}")
        
        # Stop coordination
        self.stop_coordination()
        
        # Emergency stop offensive operations
        if self.offensive_module and hasattr(self.offensive_module, 'emergency_shutdown'):
            self.offensive_module.emergency_shutdown(f"Bridge shutdown: {reason}")
        
        # Clear active responses
        for response in self.active_responses.values():
            response.completion_time = time.time()
            response.audit_trail.append({
                'timestamp': time.time(),
                'action': 'emergency_shutdown',
                'reason': reason
            })
        
        self.active_responses.clear()
        
        logger.critical("Emergency shutdown completed")


# Integration helper functions

def create_integrated_defense_system(
    defensive_module: Any = None,  # runtime defensive owner, schema-shaped
    offensive_module: Any = None,  # runtime offensive owner, schema-shaped
    *,
    runtime_root: Optional[Path] = None,
    immune_system: Optional[PlanetaryImmuneSystem] = None,
) -> DefensiveOffensiveBridge:
    """Create fully integrated defense system bound to persistent USMS."""

    bridge = DefensiveOffensiveBridge(
        defensive_module,
        offensive_module,
        runtime_root=runtime_root,
        immune_system=immune_system,
    )

    logger.info("Integrated defense system created")
    return bridge


def simulate_threat_scenario(bridge: DefensiveOffensiveBridge, scenario: Dict[str, Any]) -> IntegratedThreatResponse:
    """Simulate a threat scenario for testing"""
    
    threat_level = ThreatLevel(scenario.get('threat_level', 'medium'))
    context = scenario.get('context', {})
    
    return bridge.process_threat_event(threat_level, context, 'simulation')


# Example usage
if __name__ == "__main__":
    import tempfile

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    with tempfile.TemporaryDirectory(prefix="pan_immune_bridge_") as tmpdir:
        bridge = create_integrated_defense_system(runtime_root=Path(tmpdir))

        # Simulate threat scenarios
        scenarios = [
            {
                'name': 'Corporate Surveillance Detection',
                'threat_level': 'medium',
                'context': {
                    'threat_type': 'corporate_surveillance',
                    'source_ip': '192.168.1.100',
                    'confidence': 0.85,
                    'corporate_surveillance': True,
                    'data_collection_detected': True
                }
            },
            {
                'name': 'Active Malware Exploitation',
                'threat_level': 'critical',
                'context': {
                    'threat_type': 'malware_deployment',
                    'source_ip': '10.0.0.50',
                    'confidence': 0.95,
                    'active_exploitation': True,
                    'malware_detected': True,
                    'system_compromise_risk': True
                }
            },
            {
                'name': 'Family Safety Threat',
                'threat_level': 'existential',
                'context': {
                    'threat_type': 'physical_safety_threat',
                    'source_ip': '203.0.113.25',
                    'confidence': 0.98,
                    'family_safety_threat': True,
                    'physical_security_breach': True,
                    'immediate_action_required': True
                }
            }
        ]

        for i, scenario in enumerate(scenarios):
            print(f"\n{'='*60}")
            print(f"SCENARIO {i+1}: {scenario['name']}")
            print('='*60)

            response = simulate_threat_scenario(bridge, scenario)

            print(f"Response ID: {response.response_id}")
            print(f"Threat Level: {response.threat_level.value}")
            print(f"Response Strategy: {response.response_strategy.value}")
            print(f"ROE Level: {getattr(response, 'roe_level', 'N/A')}")
            print(f"Human Authorization Required: {response.human_authorization_required}")
            print(f"Human Authorized: {response.human_authorized}")
            print(f"Defensive Actions: {len(response.defensive_actions)}")
            print(f"Offensive Operations: {len(response.offensive_operations)}")
            print(f"Overall Effectiveness: {response.overall_effectiveness:.2f}")
            print(f"Threat Neutralized: {response.threat_neutralized}")

            time.sleep(1.0)

        print(f"\n{'='*60}")
        print("FINAL INTEGRATION STATUS")
        print('='*60)

        status = bridge.get_integration_status()
        print(json.dumps(status, indent=2))

        bridge.emergency_shutdown("Simulation completed")
        bridge.threat_intelligence.close()