# SCOPE — EDIT 2026-09-18: thyris-adb-userspace-ready

**Status:** OPEN. `snapshots/v0.15` is NOT promoted. STATE.md is not rewritten
until `check_android_adb_userspace` is pass with `adb_proven=true` on a live
guest. Inference untouched. Erebus untouched.

## Engagement Mode

- mode: EDIT
- army: thyris-adb-userspace-ready
- target_module: telecom/phone_orchestrator.py
- target_module_provenance: snapshots/v0.11/manifest.json domains.thyris
- subsequent_targets:
  - test/thyris_vm/test_thyris_android_boot.py
- justification: I am editing the live Thyris phone owner because TCG
  DEBUG=2 reached Android init/healthd but adbd stayed offline
  (20260918_025416). The ISO init execs chroot when DEBUG is set. WRAP is
  rejected. This continuation uses isolinux livem+nosetup
  (SETUPWIZARD=0 SRC= DATA=) plus vesa nomodeset without vga=ask, refuses
  WHPX, kills leftover qemu/adb, and sets READY only after adb shell
  thyris_adb_health.
- author: daeron
- date: 2026-09-18

## Runtime / host-tool OPTIONS (evidence, then selection)

Surveyed this Windows host and the official ISO (stdlib ISO9660 plus the
isolinux.cfg text at the end of android-x86_64-9.0-r2.iso):

| Option | What it is | Evidence | Verdict |
|---|---|---|---|
| 1. isolinux `label debug` (`DEBUG=2 SRC= DATA=`) | Same-ISO kernel/initrd. ISO init sets SWITCH=chroot. | Consumer FAIL 20260918_025416: 900s TCG, init+healthd, `127.0.0.1:PORT offline`. | Tried. Not READY. |
| 2. isolinux `label livem` + `label nosetup` | `SETUPWIZARD=0 SRC= DATA=`. switch_root. Omit `quiet` for serial evidence. | isolinux.cfg. ISO init writes SETUPWIZARD default.prop then switch_root. | **SELECTED.** |
| 3. isolinux `label vesa` `nomodeset vga=ask` | No GPU accel. | `vga=ask` is interactive. | Take `nomodeset` only. |
| 4. WHPX | Windows hypervisor accel. | qemu-system lists it. | Rejected. Stay TCG. |
| 5. AUTO_INSTALL / serial setprop / prompt_bridge / dummy READY | Shortcuts. | ANTITHESIS. | Rejected. |

Disk-create remains `ISOConverter._create_disk`. `boot_android_installer`
stays ISOLINUX-only and still returns `phone_ready=False` / `adb_proven=False`.

## Fletcher continuation (this pass)

1. Kill leftover qemu/adb before retry; `adb kill-server` after guest dead
2. isolinux livem+nosetup append, not DEBUG=2 chroot, not setprop spam
3. Prove with `python test/thyris_vm/test_thyris_android_boot.py` (1800s ADB wait)
4. READY only via `apply_adb_ready` after the same adb proof. Fail loud if offline.
