# PAN SDK — Brainstorm Field

Non-canonical working surface for architecture exploration. Promote only
evidence-backed decisions to the appropriate authority surface.

## Active questions

- What packaging contract lets the PAN SDK remain a single, locally operated
  product while exposing deliberate application-facing entry points?
- How should a real `SovereignInferenceEngine._run_inference` owner join the
  existing treasury Proof-of-Inference FSM without a second ledger?
- What is the first real Thyris disk-create / QEMU boot consumer once
  qemu-img, qemu-system-x86_64, and an Android image exist on the host?

## Resolved in exploration (promoted)

- Whitepaper phone / treasury / communications / persistence lanes: treasury,
  email_social, and master_db landed 2026-09-10; Thyris owners import as of
  2026-09-11. QEMU boot is still unproven. See STATE.md.

## Resolved in exploration (promoted)

- `sdk/` versus `PAN_SDK` import mismatch: the consumed contract was `PAN_SDK`.
  Directory renamed 2026-09-11. See ANTITHESIS.md and STATE.md.

## Constraints for exploration

- Preserve the monolith doctrine and existing owning modules.
- Prefer direct integration over adapter accumulation.
- Treat the whitepaper as direction, not proof that an unlocated module exists.
- Any proposed code path must identify its consumed boundary and verification
  surface before promotion.
