# SCOPE — EDIT 2026-09-18: thyris-adb-userspace-ready

**Status:** OPEN. B (WHPX livem) and D (AUTO_INSTALL=force then disk)
failed loud. `snapshots/v0.15` is NOT promoted. STATE.md is not rewritten
to READY. `phone_ready` and `adb_proven` stay false.

## Engagement Mode

- mode: EDIT
- army: thyris-adb-userspace-ready
- target_module: telecom/phone_orchestrator.py
- target_module_provenance: snapshots/v0.11/manifest.json domains.thyris
- subsequent_targets:
  - test/thyris_vm/test_thyris_android_boot.py
- justification: I am editing the live Thyris phone owner because WHPX
  livem reached `console:/ #` without adbd (20260918_050641). WRAP is
  rejected. This continuation uses this ISO's own AUTO_INSTALL=force onto
  an 8G qcow from ISOConverter._create_disk, then boots SRC=/thyris without
  live /dev/sr0. READY only after adb shell thyris_adb_health.
- author: daeron
- date: 2026-09-18

## Runtime / host-tool OPTIONS (evidence, then selection)

| Option | What it is | Evidence | Verdict |
|---|---|---|---|
| 1. isolinux debug DEBUG=2 | ISO init chroot | 20260918_025416 TCG 900s, adb offline | Exhausted |
| 2. isolinux livem+nosetup TCG | SETUPWIZARD=0 SRC= DATA= | 20260918_032455, 20260918_035525 1800s Detecting /dev/sr0, adb offline | Exhausted |
| 3. WHPX livem+nosetup | `-accel whpx,kernel-irqchip=off` same ISO | 20260918_050641: ISOLINUX pass, then Detecting /dev/sr0 + `console:/ #`, no adbd. SVM warning only. | Exhausted. Not READY. |
| 4. AUTO_INSTALL=force then disk boot SRC=/thyris | ISO install.img scripts/1-install unattended path. 8G qcow via landed _create_disk. | ISO own installer. Still requires real adb shell. | **SELECTED.** |
| 5. serial setprop / prompt_bridge / dummy READY / BlissOS download | Shortcuts | ANTITHESIS | Rejected |

Disk-create remains `ISOConverter._create_disk`. `boot_android_installer`
stays ISOLINUX-only and still returns `phone_ready=False` / `adb_proven=False`.

## Fletcher continuation (this pass)

1. Kill leftover qemu/adb before retry
2. AUTO_INSTALL=force INSTALL_PREFIX=thyris onto 8G qcow (WHPX)
3. On Congratulations, send Reboot keys; if qcow grew, boot SRC=/thyris with no ISO
4. READY only via `apply_adb_ready` after adb shell thyris_adb_health
