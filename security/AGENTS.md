# PAN security lane — Operator Packet

**Folder:** security/
**Parent packet:** ../AGENTS.md
**Runtime truth:** ../STATE.md
**ROE:** rules_of_engagement.md
**Packet updated:** 2026-09-12

This folder is the security lane of the PAN monolith. It is not a standalone
`somnus_erebus/` project and it is not an in-phone AI stack.

## Live consumed owners

Erebus cognition in this repository is USMS bound to the PAN mesh:

- `memory/unified_memory_system.py` persists signed Ed25519 EVENT/BELIEF/CONTRADICTION nodes.
- `security/planetary_immune_system.py` binds that DAG to PAN RSA `UnifiedDataPacket` / DHT and broadcasts high-confidence beliefs as `THREAT_MEMORY_BULLETIN`.
- `security/sovereign_firewall.py` is the fail-closed packet border. Security owns it.
- `security/planetary_highway.py` is the consumed packet fabric. AI travel is
  sealed USMS cargo on `UnifiedDataPacket` hops. It is not Erebus cognition
  and it is not a second internet.

Those three security modules are gate compile targets. Consumers are
`test/immune/test_planetary_immune_system.py` and
`test/highway/test_planetary_highway.py`. The project gate includes both
slices (`python test/run_pan_gate.py`).

Do not pull or invent `core.prompt_bridge` as "Erebus cognition." Thyris phones
are telecommunications VMs. They do not contain in-device AI. USMS already owns
immune memory; the planetary immune system already owns the mesh bind.

PAN `SovereignIdentity` (RSA, `PAN_SDK.PAN_SDK`) and USMS `SovereignIdentity`
(Ed25519, `memory.unified_memory_system`) are different cryptography. Bind them.
Do not collapse them into one class.

## Present lineage now compile/import consumed via the bridge

These files exist on disk. The gate compiles them. The immune consumer imports
`DefensiveOffensiveBridge`, which imports the live `security.*` owners and
writes combat memory through `PlanetaryImmuneSystem` / USMS. They are still
not a replacement for the immune owner:

| File | What it is |
|---|---|
| defensive_sovereignty.py | historical coordinator; SMTP/webhook/feeds fail loud; RAM `threat_intelligence` is not combat memory |
| reactive_offense.py | historical ROE coordinator; whois/deauth fail loud; `ROELevel` is imported by the bridge |
| defensive_offensive_bridge.py | D/O bridge; writes through `PlanetaryImmuneSystem`; L4 without a human fails loud |
| planetary_highway.py | consumed packet fabric; identity-hash hops; cargo sealed to destination RSA |

Do not wrap these files to avoid editing `planetary_immune_system.py`. Do not
treat an in-process `intelligence_database` as combat memory. Ephemeral RAM
dictionaries are rejected; USMS is the local substrate.

## Stale QWEN / somnus_erebus tree

An older packet (this file's previous text) described a `somnus_erebus/` layout
with `python_production_doctor.py`, `production_doctor_config.yaml`, `QWEN.md`,
`TODO.md`, and a security-local `requirements.txt`. Those files are not in this
repository's `security/` folder. Do not recreate that tree. Do not run a
Production Doctor command that is not here.

Code health for PAN Python is the Somnus Code Forge loop on the existing
topology (see root AGENTS.md), not a missing doctor script.

Live security tree:

```
security/
├── AGENTS.md
├── rules_of_engagement.md
├── sovereign_firewall.py          # consumed packet border
├── planetary_immune_system.py     # consumed USMS+PAN bind
├── planetary_highway.py           # consumed packet fabric
├── defensive_sovereignty.py       # lineage; WAN fail-loud
├── reactive_offense.py            # lineage; WAN fail-loud
└── defensive_offensive_bridge.py  # lineage; immune-imported
```

## Rules of Engagement

`rules_of_engagement.md` remains the formal ROE text. Four escalation levels:

1. OBSERVE: passive monitoring and analysis
2. DECEIVE: deception and misdirection
3. DEGRADE: active degradation of threats
4. NEUTRALIZE: direct neutralization (requires human authorization)

Keep defensive intent, authorization boundaries, auditability, and fail-loud
evidence intact. Do not convert this lane into uncontrolled external action.
ROE Level 4 against external hosts is not implemented by the current immune
landing and is not authorized by it.

## Verification

    python test/immune/test_planetary_immune_system.py
    python test/highway/test_planetary_highway.py
    python test/run_pan_gate.py

POSIX spelling: `python3` in place of `python`.

## Stop conditions

- Do not log, commit, or print credentials, keys, or tokens.
- Do not invent a `memory_system` package or wrap USMS to look like Thyris `MemoryManager`.
- Do not dummy `schemas.session` or `core.prompt_bridge`.
- Do not restore a host:port consciousness mesh, UDP broadcast, or serialized
  RAM dump as civic travel. Do not collapse PAN RSA and USMS Ed25519.
- Do not reconnect SMTP, HTTP feeds, whois, or RF neutralization.
- Read this packet and `rules_of_engagement.md` before modifying security/.
