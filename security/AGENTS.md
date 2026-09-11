# Somnus Erebus Project - Qwen Context

## Project Overview

This subfolder contains a sophisticated autonomous defensive and offensive cybersecurity system designed to protect sovereign digital infrastructure. The system implements a comprehensive threat response framework with formal Rules of Engagement (ROE) compliance, enabling graduated responses from passive monitoring to active countermeasures.

The project is built around several core components:

1. **Defensive Sovereignty System** (`defensive_sovereignty.py`) - Core defensive capabilities for AI model self-protection and autonomy
2. **Reactive Offensive System** (`reactive_offense.py`) - Calibrated offensive responses based on ROE framework
3. **Defensive-Offensive Integration Bridge** (`defensive_offensive_bridge.py`) - Unified threat response coordination
4. **Rules of Engagement** (`rules_of_engagement.md`) - Formal ROE framework for autonomous operations
5. **Production Doctor** (`python_production_doctor.py`) - Code health assessment tool

## System Architecture

### Core Components

#### Defensive Sovereignty System

Implements distributed defense, state persistence, and threat response with:

- Network-based threat monitoring with comprehensive security analysis
- System integrity monitoring and forensic data collection
- Distributed defensive agents with resource arbitration
- State persistence and recovery mechanisms
- Blockchain-based threat intelligence sharing
- Neural competition for resource allocation under threat

#### Reactive Offensive System

Provides calibrated offensive responses with:

- ROE-compliant escalation from passive defense to active countermeasures
- Multiple offensive capabilities (traceback hunting, infiltration, neutralization)
- Human authorization workflow for high-impact operations
- Viral-class behavior bounded by sovereignty constraints
- Complete audit trails and compliance monitoring

#### Integration Bridge

Coordinates defensive and offensive operations:

- Seamless integration between detection and response systems
- Real-time threat intelligence sharing
- Unified threat response capabilities
- Full authorization chain management

## Rules of Engagement Framework

The system operates under a formal **Rules of Engagement (ROE)** framework with four escalation levels:

1. **ROE Level 1: OBSERVE** - Passive monitoring and analysis
2. **ROE Level 2: DECEIVE** - Deception and misdirection tactics
3. **ROE Level 3: DEGRADE** - Active degradation of threats
4. **ROE Level 4: NEUTRALIZE** - Direct neutralization (requires human authorization)

Each level has specific authorization requirements, confidence thresholds, and prescribed actions.

## Code Quality and Maintenance

The project includes a **Python Production Doctor** tool that performs comprehensive code health assessments:

- Syntax error detection
- TODO and technical debt identification
- Stub implementation detection
- Missing docstrings and type hints
- Test coverage analysis
- Simple method and placeholder return detection

## Key Technologies

- Python 3.12+
- Zero external dependencies (pure Python implementation)
- Modular architecture with protocol interfaces
- Thread-safe operations
- DARPA-grade security implementation
- Comprehensive logging and audit trails

## Configuration

The system is configured through `production_doctor_config.yaml` which defines:

- Code quality thresholds
- Ignored patterns and functions
- Severity levels for different issue types
- Security scan parameters
- Performance analysis settings

## Development Status

The project is currently in development with significant code quality issues identified by the Production Doctor:

- 1,787 total issues across 2 files
- 1,586 critical issues that block deployment
- 4 serious issues requiring immediate attention
- 197 minor issues for quality improvements

## Usage

To analyze the codebase health:

```bash
python python_production_doctor.py .
```

To run with custom configuration:

```bash
python python_production_doctor.py . -c production_doctor_config.yaml
```

## Security Considerations

This system is designed for defensive cybersecurity operations with strict ROE compliance. Key security features include:

- Zero-trust architecture principles
- Finite state machines for system stability
- Thread-safety for concurrent operations
- Comprehensive audit logging
- Human authorization requirements for critical actions
- Sovereignty constraints on offensive capabilities

## Project Structure

```
somnus_erebus/
├── defensive_sovereignty.py         # Core defensive system
├── reactive_offense.py             # Offensive response system
├── defensive_offensive_bridge.py   # Integration layer
├── rules_of_engagement.md          # Formal ROE framework
├── defensive_sovereignty_report.md # System analysis report
├── python_production_doctor.py     # Code health assessment tool
├── production_doctor_config.yaml   # Configuration file
├── requirements.txt                # Python dependencies
├── TODO.md                        # Development roadmap
└── QWEN.md                        # This file
```
