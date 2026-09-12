# SCOPE — CLOSED 2026-09-12: KVM inaccessible falls back to TCG

**Status:** CLOSED after `test/thyris_vm/test_thyris_android_boot.py` 4/4
(Linux TCG, ISOLINUX, `phone_ready` false).
**Base:** `c1bcf6b`. Installer-boot design, disk-create, ROE, and
BlockchainThreatIntelligence were not redone.

## Engagement 5 — select_qemu_accelerator (CLOSED)

- mode: EDIT
- target_module: telecom/phone_orchestrator.py
- target_symbol: select_qemu_accelerator
- closed: 2026-09-12 after Linux boot consumer 20260912_094201
