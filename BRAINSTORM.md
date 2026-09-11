# PAN SDK — Brainstorm Field

Non-canonical working surface for architecture exploration. Promote only
evidence-backed decisions to the appropriate authority surface.

## Active questions

- What packaging contract lets the PAN SDK remain a single, locally operated
  product while exposing deliberate application-facing entry points?
- Which existing sdk/PAN_SDK.py boundaries are stable enough to support the
  whitepaper's future phone, treasury, communications, and persistence lanes
  without a service decomposition?
- Does the sdk/ versus PAN_SDK import mismatch reflect historical archive
  extraction, a rename, or an unfinished packaging decision? Inspect lineage
  before selecting a repair.

## Constraints for exploration

- Preserve the monolith doctrine and existing owning modules.
- Prefer direct integration over adapter accumulation.
- Treat the whitepaper as direction, not proof that an unlocated module exists.
- Any proposed code path must identify its consumed boundary and verification
  surface before promotion.
