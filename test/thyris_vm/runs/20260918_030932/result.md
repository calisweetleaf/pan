# Thyris Android guest boot run 20260918_030932

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260918_030932.
I found status `fail` with 7 passed, 1 failed, 0 skipped.

## What I required

I required qemu-system-x86_64, the official android-x86_64-9.0-r2.iso
(SHA-1 1cc85b5ed7c830ff71aecf8405c7281a9c995aa0), a qcow2 from landed
ISOConverter._create_disk, SeaBIOS/ISOLINUX on installer -nographic stdout,
and a separate live kernel/initrd boot that only sets phone_ready after
adb connect + adb shell. I refused a dummy boot, prompt_bridge, a second
disk-create owner, and READY from ISOLINUX.

Claim: Installer ISOLINUX remains a non-READY proof. ADB userspace was not proven; phone_ready stays false.

## Checks

- `qemu_system_resolves`: pass
- `android_iso_authentic`: pass
- `nographic_argv`: pass
- `adb_resolves`: pass
- `extract_live_boot_files`: pass
- `live_argv_forwards_adb`: pass
- `android_installer_boot`: pass
- `android_adb_userspace`: fail
  - error: `CheckFailure: Android ADB userspace failed loud: No adb shell within 900.0s on 127.0.0.1:64547. Detecting Android-x86 / init markers are not READY. detail="adb devices listed offline/unauthorized. connect='failed to connect to 127.0.0.1:64547' devices='List of devices attached\\r\\n127.0.0.1:64547\\toffline'" markers=['Detecting Android-x86', 'init: ', 'healthd'] debug_exits=2 stale_qemu=[] stderr='' console=' path="/vendor" dev="tmpfs" ino=6431 scontext=u:r:hal_dumpstate_default:s0 tcontext=u:object_r:tmpfs:s0 tclass=lnk_file permissive=1\n[   61.086784] type=1400 audit(1789718119.330:140): avc: denied { getattr } for pid=1562 comm="android.hardwar" path="/vendor" dev="tmpfs" ino=6431 scontext=u:r:hal_power_default:s0 tcontext=u:object_r:tmpfs:s0 tclass=lnk_file permissive=1\n[   61.117233] type=1400 audit(1789718119.330:140): avc: denied { getattr } for pid=1562 comm="android.hardwar" path="/vendor" dev="tmpfs" ino=6431 scontext=u:r:hal_power_default:s0 tcontext=u:object_r:tmpfs:s0 tclass=lnk_file permissive=1\n[   61.117292] type=1400 audit(1789718119.330:141): avc: denied { read } for pid=1562 comm="android.hardwar" name="vendor" dev="tmpfs" ino=6431 scontext=u:r:hal_power_default:s0 tcontext=u:object_r:tmpfs:s0 tclass=lnk_file permissive=1\n[   61.134670] type=1400 audit(1789718119.330:141): avc: denied { read } for pid=1562 comm="android.hardwar" name="vendor" dev="tmpfs" ino=6431 scontext=u:r:hal_power_default:s0 tcontext=u:object_r:tmpfs:s0 tclass=lnk_file permissive=1\n[   61.134670] type=1400 audit(1789718119.420:142): avc: denied { getattr } for pid=1564 comm="lmkd" path="/vendor" dev="tmpfs" ino=6431 scontext=u:r:lmkd:s0 tcontext=u:object_r:tmpfs:s0 tclass=lnk_file permissive=1\n[   61.668271] audit: audit_lost=52 audit_rate_limit=5 audit_backlog_limit=64\n[   61.668271] audit: rate limit exceeded\n[  130.862899] type=1400 audit(1789718123.144:161): avc: denied { execute_no_trans } for pid=1569 comm="sh" path="/android/bin/busybox" dev="tmpfs" ino=6622 scontext=u:r:kernel:s0 tcontext=u:object_r:tmpfs:s0 tclass=file permissive=1\n[  130.862899] type=1400 audit(1789718192.335:165): avc: denied { read } for pid=2173 comm="sh" name="bus" dev="sysfs" ino=8 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=dir permissive=1\n[  130.953718] type=1400 audit(1789718192.335:165): avc: denied { read } for pid=2173 comm="sh" name="bus" dev="sysfs" ino=8 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=dir permissive=1\n[  130.953718] type=1400 audit(1789718192.351:166): avc: denied { open } for pid=2173 comm="sh" path="/sys/bus" dev="sysfs" ino=8 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=dir permissive=1\n[  130.953718] type=1400 audit(1789718192.351:166): avc: denied { open } for pid=2173 comm="sh" path="/sys/bus" dev="sysfs" ino=8 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=dir permissive=1\n[  130.979309] type=1400 audit(1789718192.351:167): avc: denied { getattr } for pid=2173 comm="sh" path="/sys/devices/platform/i8042/serio0/uevent" dev="sysfs" ino=8410 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  130.992702] type=1400 audit(1789718192.351:167): avc: denied { getattr } for pid=2173 comm="sh" path="/sys/devices/platform/i8042/serio0/uevent" dev="sysfs" ino=8410 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  130.992702] type=1400 audit(1789718192.415:168): avc: denied { read } for pid=2173 comm="cat" name="uevent" dev="sysfs" ino=2924 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  130.992702] type=1400 audit(1789718192.415:168): avc: denied { read } for pid=2173 comm="cat" name="uevent" dev="sysfs" ino=2924 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  131.010913] type=1400 audit(1789718192.415:169): avc: denied { open } for pid=2173 comm="cat" path="/sys/devices/LNXSYSTM:00/LNXSYBUS:00/ACPI0010:00/uevent" dev="sysfs" ino=2924 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  131.119007] audit: audit_lost=55 audit_rate_limit=5 audit_backlog_limit=64\n[  131.119007] audit: rate limit exceeded\n[  131.842668] powernow_k8: Power state transitions not supported\n[  131.842962] powernow_k8: Power state transitions not supported\n[  132.596333] init: Untracked pid 1052 exited with status 0\n[  374.395192] hrtimer: interrupt took 4630600 ns\n'`

## Artifacts

- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_030932\result.json`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_030932\result.md`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_030932\result.log`

