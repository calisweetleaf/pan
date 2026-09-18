# Thyris Android guest boot run 20260918_025309

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260918_025309.
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
  - error: `CheckFailure: Android ADB userspace failed loud: No adb shell within 900.0s on 127.0.0.1:57135. Detecting Android-x86 / init markers are not READY. detail="adb devices listed offline/unauthorized. connect='failed to connect to 127.0.0.1:57135' devices='List of devices attached\\r\\n127.0.0.1:57135\\toffline'" markers=['Detecting Android-x86', 'init: '] debug_exits=2 stale_qemu=[] stderr='' console='854] type=1400 audit(1789717135.348:79): avc: denied { remove_name } for pid=1424 comm="sed" name="dev2modS8rcPS" dev="rootfs" ino=8256 scontext=u:r:kernel:s0 tcontext=u:object_r:rootfs:s0 tclass=dir permissive=1\n[   59.434369] type=1400 audit(1789717139.808:142): avc: denied { write } for pid=1440 comm="sed" name="tmp" dev="rootfs" ino=5683 scontext=u:r:kernel:s0 tcontext=u:object_r:rootfs:s0 tclass=dir permissive=1\n[   59.434369] type=1400 audit(1789717139.808:143): avc: denied { remove_name } for pid=1440 comm="sed" name="dev2modQcCP4n" dev="rootfs" ino=8361 scontext=u:r:kernel:s0 tcontext=u:object_r:rootfs:s0 tclass=dir permissive=1\n[   59.445623] type=1400 audit(1789717139.808:143): avc: denied { remove_name } for pid=1440 comm="sed" name="dev2modQcCP4n" dev="rootfs" ino=8361 scontext=u:r:kernel:s0 tcontext=u:object_r:rootfs:s0 tclass=dir permissive=1\n[   59.445623] type=1400 audit(1789717139.808:144): avc: denied { add_name } for pid=1440 comm="sed" name="dev2mod" dev="rootfs" ino=8334 scontext=u:r:kernel:s0 tcontext=u:object_r:rootfs:s0 tclass=dir permissive=1\n[   59.445623] type=1400 audit(1789717139.808:144): avc: denied { add_name } for pid=1440 comm="sed" name="dev2mod" dev="rootfs" ino=8334 scontext=u:r:kernel:s0 tcontext=u:object_r:rootfs:s0 tclass=dir permissive=1\n[   59.445623] type=1400 audit(1789717139.817:145): avc: denied { search } for pid=1459 comm="sh" name="/" dev="tmpfs" ino=125 scontext=u:r:kernel:s0 tcontext=u:object_r:tmpfs:s0 tclass=dir permissive=1\n[  119.948374] type=1400 audit(1789717139.817:145): avc: denied { search } for pid=1459 comm="sh" name="/" dev="tmpfs" ino=125 scontext=u:r:kernel:s0 tcontext=u:object_r:tmpfs:s0 tclass=dir permissive=1\n[  119.988374] type=1400 audit(1789717205.341:154): avc: denied { read } for pid=2173 comm="sh" name="bus" dev="sysfs" ino=8 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=dir permissive=1\n[  119.993464] type=1400 audit(1789717205.341:154): avc: denied { read } for pid=2173 comm="sh" name="bus" dev="sysfs" ino=8 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=dir permissive=1\n[  119.993464] type=1400 audit(1789717205.344:155): avc: denied { open } for pid=2173 comm="sh" path="/sys/bus" dev="sysfs" ino=8 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=dir permissive=1\n[  120.004678] type=1400 audit(1789717205.344:155): avc: denied { open } for pid=2173 comm="sh" path="/sys/bus" dev="sysfs" ino=8 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=dir permissive=1\n[  120.007037] type=1400 audit(1789717205.347:156): avc: denied { getattr } for pid=2173 comm="sh" path="/sys/devices/platform/i8042/serio0/uevent" dev="sysfs" ino=8410 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  120.016142] type=1400 audit(1789717205.347:156): avc: denied { getattr } for pid=2173 comm="sh" path="/sys/devices/platform/i8042/serio0/uevent" dev="sysfs" ino=8410 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  120.018734] type=1400 audit(1789717205.407:157): avc: denied { read } for pid=2173 comm="cat" name="uevent" dev="sysfs" ino=2924 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  120.027889] type=1400 audit(1789717205.407:157): avc: denied { read } for pid=2173 comm="cat" name="uevent" dev="sysfs" ino=2924 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  120.028222] type=1400 audit(1789717205.407:158): avc: denied { open } for pid=2173 comm="cat" path="/sys/devices/LNXSYSTM:00/LNXSYBUS:00/ACPI0010:00/uevent" dev="sysfs" ino=2924 scontext=u:r:kernel:s0 tcontext=u:object_r:sysfs:s0 tclass=file permissive=1\n[  120.127020] audit: audit_lost=53 audit_rate_limit=5 audit_backlog_limit=64\n[  120.127772] audit: rate limit exceeded\n[  120.628657] powernow_k8: Power state transitions not supported\n[  120.629865] powernow_k8: Power state transitions not supported\n[  121.131718] init: Untracked pid 1051 exited with status 0\n'`

## Artifacts

- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_025309\result.json`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_025309\result.md`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_025309\result.log`

