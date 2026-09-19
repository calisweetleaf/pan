# SCOPE — EDIT 2026-09-18: thyris-adb-userspace-ready

**Status:** OPEN. B (WHPX livem) and D (AUTO_INSTALL=force then disk)
failed loud on Windows `-nographic`/`-no-reboot`. This Linux Envy
continuation keeps AUTO_INSTALL=force, then disk-boots SRC=/thyris with
VGA+serial (not stdio) and allows guest reboot so first-boot cannot kill
QEMU. `snapshots/v0.15` is NOT promoted until adb shell answers.
STATE.md is not rewritten to READY. `phone_ready` and `adb_proven` stay
false until that proof.

## Engagement Mode

- mode: EDIT
- army: thyris-adb-userspace-ready
- target_module: telecom/phone_orchestrator.py
- target_module_provenance: snapshots/v0.11/manifest.json domains.thyris
- subsequent_targets:
  - test/thyris_vm/test_thyris_android_boot.py
- justification: I am editing the live Thyris phone owner because Windows
  AUTO_INSTALL then disk-boot reached Android console:/ # and QEMU exited
  before TCP adbd (20260918_052020, 20260918_054408). WRAP is rejected.
  This host is daeron-hpenvyx3602in1laptop15ey0xxx with KVM, qemu, adb,
  and the official ISO. Disk-create stays ISOConverter._create_disk.
  READY only after adb shell thyris_adb_health on the qemu user-net
  forward.
- author: daeron
- date: 2026-09-18

## Runtime / host-tool OPTIONS (evidence, then selection)

| Option | What it is | Evidence | Verdict |
|---|---|---|---|
| 1. isolinux debug DEBUG=2 | ISO init chroot | 20260918_025416 TCG 900s, adb offline | Exhausted |
| 2. isolinux livem+nosetup TCG | SETUPWIZARD=0 SRC= DATA= | 20260918_032455, 20260918_035525 1800s Detecting /dev/sr0, adb offline | Exhausted |
| 3. WHPX livem+nosetup | `-accel whpx,kernel-irqchip=off` same ISO | 20260918_050641: ISOLINUX pass, then Detecting /dev/sr0 + `console:/ #`, no adbd. SVM warning only. | Exhausted. Not READY. |
| 4. AUTO_INSTALL=force then disk boot SRC=/thyris | ISO install.img scripts/1-install unattended path. 8G qcow via landed _create_disk. | Windows nographic disk-boot: Congratulations then `console:/ #`, QEMU rc=4294967295, no adbd. | **SELECTED** and continued. |
| 4b. Linux KVM disk-boot VGA+serial, allow reboot, adbd default.prop | Same install owner. Hidden std VGA, serial file (not stdio), no `-no-reboot` on disk-boot. Initrd writes `sys.usb.config=adb` and `ro.adb.secure=0` beside the existing TCP port lines. | This Envy: qemu 10.2.1, KVM open, adb, official ISO SHA-1 match. | **SELECTED on this host.** |
| 5. serial setprop / prompt_bridge / dummy READY / BlissOS download | Shortcuts | ANTITHESIS | Rejected |

Disk-create remains `ISOConverter._create_disk`. `boot_android_installer`
stays ISOLINUX-only and still returns `phone_ready=False` / `adb_proven=False`.

## Linux Envy continuation (this pass)

1. Kill leftover qemu/adb before retry
2. AUTO_INSTALL=force INSTALL_PREFIX=thyris onto 8G qcow (KVM, nographic install)
3. On Congratulations, send Reboot keys; if qcow grew, disk-boot SRC=/thyris
   with `-vga std -display none -serial file:` and without `-no-reboot`
4. READY only via `apply_adb_ready` after host `adb shell echo thyris_adb_health`
   returns the guest token. Do not dummy READY from `console:/ #`.
