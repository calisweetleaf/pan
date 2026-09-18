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
- justification: I am editing the live Thyris phone owner because
  PhoneVMState.READY is already gated on ADB proof. Fletcher's audit showed
  serial setprop into a kernel log cannot enable TCP adbd, leftover adb.exe
  produced stale connect+offline, and create_phone_vm launched VNC without
  serial. WRAP is rejected. This continuation uses isolinux.cfg label debug
  (DEBUG=2 SRC= DATA=), kills leftover qemu/adb, unifies _start_android_vm
  onto the nographic helper argv, and sets AndroidPhoneVM.vm_state READY
  only after adb shell thyris_adb_health.
- author: daeron
- date: 2026-09-18

## Runtime / host-tool OPTIONS (evidence, then selection)

Surveyed this Windows host and the official ISO (mounted, isolinux.cfg read,
ISO9660 root parsed with stdlib):

| Option | What it is | Evidence | Verdict |
|---|---|---|---|
| 1. Same-ISO kernel/initrd live boot + qemu user-net hostfwd + `adb connect`/`shell` | Extract `/kernel` + `/initrd.img` from android-x86_64-9.0-r2.iso. QEMU `-kernel/-initrd/-append` with isolinux `DEBUG=2 SRC= DATA=`. | isolinux.cfg `label debug` / `livem` / `nosetup`. Prior consumer FAIL 20260918_021830: connect already-connected + device offline; leftover adb PID 26304. | **SELECTED.** Same legal ISO. No new image. No second disk-create owner. Offline. |
| 2. Wait for vesamenu timeout, then Live CD | Keep `-boot order=d`. | `default vesamenu.c32` is a VGA menu. | Rejected as the READY owner. |
| 3. QEMU monitor `sendkey` into ISOLINUX | Keep CDROM boot, inject Return. | Fragile vs vesamenu/nographic. | Not selected. |
| 4. AUTO_INSTALL to the qcow2, reboot from disk | isolinux `AUTO_INSTALL=0`. | Fletcher: no AUTO_INSTALL silent substitute. | Rejected. |
| 5. BlissOS / emulator system.img / downloaded qcow2 | New image. | Public internet. | Rejected. |
| 6. Serial setprop into kernel log | `setprop service.adb.tcp.port` on qemu stdin. | Fletcher: cannot enable TCP adbd. | Rejected. |
| 7. llama / ONNX / prompt_bridge / dummy READY | Claim READY from ISOLINUX or canned adb. | ANTITHESIS + AGENTS.md. | Rejected. |

Selected option 1 with isolinux debug append. Disk-create remains
`ISOConverter._create_disk`. `boot_android_installer` stays ISOLINUX-only
and still returns `phone_ready=False` / `adb_proven=False`.

## Fletcher continuation (this pass)

1. Kill leftover qemu/adb before retry; `adb kill-server` after guest dead
2. isolinux.cfg live/debug append, not setprop spam; keep SRC=
3. Prove with `python test/thyris_vm/test_thyris_android_boot.py`
4. Unify `_start_android_vm` to the nographic helper argv; READY only via
   `apply_adb_ready` after the same adb proof
