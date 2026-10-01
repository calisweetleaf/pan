# SCOPE — EDIT 2026-10-01: thyris-provision-disk-owner-bind

**Status:** OPEN. This cut is the prerequisite for the Linux↔Windows cross-device PAN phone-call proof. The Envy KVM path already proved installed-disk ADB userspace in snapshot v0.17, but the normal provisioning path still launches the obsolete live `livem -nographic` boot.

## Engagement Mode

- mode: EDIT
- army: thyris-provision-disk-owner-bind
- target_module: telecom/phone_orchestrator.py
- subsequent_targets:
  - test/thyris_vm/test_thyris_android_boot.py
- justification: `provision_sovereign_phone()` must consume the already-landed AUTO_INSTALL → installed-disk owner instead of reopening the exhausted live path. This is a direct edit at the owning seam; no wrapper, third phone stack, prompt bridge, or second disk owner.
- author: daeron
- date: 2026-10-01

## Invariants

1. Disk creation remains `ISOConverter._create_disk`.
2. `PhoneVMState.READY` remains gated on real host `adb shell echo thyris_adb_health`.
3. Final persistent runtime must boot the installed qcow with `SRC=/thyris`, `VIRT_WIFI=0`, hidden VGA, no live ISO, and a bidirectional serial holder.
4. The proof helper may stop its disposable probe VM; the provisioned phone must remain running after READY.
5. Cross-host Highway A→B remains UNVERIFIED until both hosts independently prove READY/ADB. Heartbeats are not a mesh exchange.
6. Windows is not declared fixed by this edit. Existing WHPX/nographic failures remain evidence until a real Windows ADB proof lands.

## Immediate cut

Bind the production provision/start path to the same installed-disk boot semantics already proven on the Envy, add a consumer check that rejects regression to `ANDROID_LIVE_CMDLINE`, then run the focused Thyris consumer on the Envy before attempting the two-host exchange.
