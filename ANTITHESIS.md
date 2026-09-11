# PAN SDK — Antithesis

This document narrows the design space. It records transitions that PAN must not
take unless Daeron explicitly changes the product thesis.

## Rejected transitions

- **Microservice conversion:** PAN is not to be decomposed into service fleets,
  queues, container orchestration, or networked control planes merely to appear
  scalable. Its production architecture is a resilient, modular Python monolith.
- **Wrapper-first evasion:** do not add shims, adapters, proxy packages, or
  parallel modules when the owning PAN module should be edited directly. A real
  adapter is allowed only for a concrete external boundary and must contain no
  duplicated domain logic.
- **Test laundering:** do not weaken assertions, add skips, introduce mocks, or
  normalize away mismatches to manufacture green status. Diagnose and repair the
  actual producer/consumer contract.
- **Architecture by filename:** a historical archive, reference implementation,
  whitepaper noun, or future aspiration is not a live dependency. Locate the
  owning source and consumed interface before building on it.
- **Premature infrastructure:** do not add cloud, telecom-provider, external
  database, deployment, telemetry, or public API dependencies when the current
  offline SQLite-backed implementation does not own that boundary.
- **Unproven success:** syntax, static checks, old Windows evidence, or an
  import-only test does not prove a working PAN integration.
- **Security theater:** do not log secrets, claim air-gap status without
  evidence, or turn security code into uncontrolled external action.
- **Ephemeral threat intelligence:** do not store combat memory in process
  dictionaries or queues that die on restart. USMS is the local substrate;
  PAN `UnifiedDataPacket` + DHT is the mesh. A wrapper that copies USMS
  persistence into a second store is rejected.
- **Identity collapse:** do not pretend PAN RSA `SovereignIdentity` and USMS
  Ed25519 `SovereignIdentity` are the same type. Bind them; do not forge a
  single key class without an explicit decision and tests.
- **Memory-system package:** do not create `memory_system` beside `memory/`.
  Thyris VM memory is `memory.memory_core` / `memory.system_cache`. USMS stays
  `memory.unified_memory_system`. Do not wrap one to look like the other.
- **Dummy Thyris owners:** do not stub `core.prompt_bridge`, `schemas.session`,
  QEMU, or Android images to make phone orchestration look complete.
- **Email overlay on every DHTNode:** do not auto-construct `EmailSocialNode`
  (and its firewall sqlite) inside `DHTNode.__init__`. Civic tests use
  TemporaryDirectory; an extra unclosed sqlite handle fails Windows cleanup.
  Relays stay blind; they are not content moderators.
- **Second sqlite engine for CRDTs:** `MasterDatabase` joins through
  `PANPersistenceStore`. A parallel sqlite connection for the national store
  is a split-brain waiting to happen.

## Current explicit boundaries

- PLAN.md and the sovereign-digital-nation whitepaper are directional canon;
  they do not authorize invention of absent modules or replacement architecture.
- The package directory is `PAN_SDK/`. That layout was resolved by the consumed
  import contract (2026-09-11). Do not reintroduce `sdk/`, a proxy package, or a
  PYTHONPATH shim.
- Historical reference-code/ and archives/ preserve lineage; they are not
  production runtime authority.
