# PAN SDK — Active Notebook

Scratch only; current runtime truth belongs in STATE.md.

## 2026-09-10 control-plane setup

- Root AGENTS.md is now a short PAN execution packet rather than a generic
  template. Cursor-specific rules/commands are live in .cursor/.
- Direct integration is explicit: existing PAN code defaults to EDIT; wrappers
  require a real external seam and may not duplicate logic.
- No production source was touched. Known syntax and import-layout blockers
  remain exactly as recorded in STATE.md.
- CONTEXT.md and MEMORY.md were previously empty templates; they now contain
  grounded first entries. ANTITHESIS.md and BRAINSTORM.md now exist.
- Need regenerate FileTree Pro map after this structural setup; do not hand-edit
  filetree.md.

## Immediate test sequence after an EDIT-mode syntax repair

1. python3 -m py_compile sdk/PAN_SDK.py
2. prove the owning import consumer
3. run the narrow focused test
4. only then widen to the project test gate and scenario
5. write Code Forge run artifacts / SOTA_RUN.md for a promotion claim
