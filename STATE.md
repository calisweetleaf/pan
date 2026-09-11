# PAN SDK — Current State

**Updated:** 2026-09-10
**Canon lock:** PLAN.md and docs/research/Building a Sovereign Digital Nation.md
remain the north-star direction. Do not replace their architecture with an
invented alternative.

## What exists now

- Production topology: sdk/, telecom/, security/, tools/, and test/.
- sdk/PAN_SDK.py is the central PAN monolith; companion SDK, personal-data,
  phone, security, and test surfaces are present in the generated filetree.md.
- Historical lineage: reference-code/mtl.py,
  reference-code/unified_dag_blockchain.py, four archives/*.zip files, and the
  Windows result under results/.
- Persistent repository control plane: AGENTS.md, STATE.md, ANTITHESIS.md,
  BRAINSTORM.md, CONTEXT.md, MEMORY.md, and NOTEPAD.md.
- Cursor control plane: four scoped rules and four operator commands under
  .cursor/.

## Verified baseline

- **RED, last verified 2026-09-09:**
  python3 -m py_compile sdk/PAN_SDK.py fails with IndentationError at
  sdk/PAN_SDK.py:1034; direct inspection attributes the causal dedent to
  persist_name at line 1025.
- **RED, last verified 2026-09-09:** importing sdk fails through the same
  syntax error.
- **RED, last verified 2026-09-09:** imports expecting top-level PAN_SDK fail
  because this checkout owns sdk/, not a PAN_SDK/ package.
- The 2025-10-02 Windows system result is historical partial evidence only:
  six persisted slices matched; ledger, pending transaction timestamp, and
  citizen permission-order comparisons differed. It predates the present
  personal-data and phone sweep.

## Active frontier

1. Repair the mechanical syntax blocker while preserving the current API, then
   prove the first import consumer.
2. Resolve the sdk/ versus PAN_SDK import contract as an explicit architecture
   decision before applying a package layout change.
3. Once the import path is coherent, run focused persistence/manifest/phone
   consumers, then the system scenario and append a new Kubuntu result.

## Control-plane change, 2026-09-10

- Replaced template residue in the root execution packet with PAN-specific
  authority, direct-integration, verification, and stop-condition rules.
- Added Cursor project rules and recover/implement/verify/handoff commands.
- Added ANTITHESIS.md and BRAINSTORM.md; replaced placeholder-only CONTEXT.md
  and MEMORY.md with grounded entries.
- No production Python, tests, result logs, archive contents, or reference code
  changed in this control-plane update.

## Known decision boundaries

- Cursor may perform a mechanically demonstrated repair that preserves a clear
  contract and validate it at the consumer boundary.
- Cursor must present evidence and options before selecting a package-layout,
  persistence-semantic, protocol/service-boundary, deployment, publication, or
  external-action direction.
- Do not add a wrapper, shim, proxy package, or parallel implementation merely
  to bypass the direct integration decision.

## Generated-map status

filetree.md was correctly generated at 2026-09-10 21:11 before the control
plane files were added. It is now structurally stale because .cursor/ gained
tracked files and ANTITHESIS.md / BRAINSTORM.md were added. Regenerate it with
FileTree Pro; do not hand-edit it.

## Next justified action

Run the /implement Cursor command on the syntax blocker as an EDIT-mode,
consumer-bound repair. Stop before choosing an import-layout strategy unless
evidence makes the existing contract unambiguous.
