# Thyris Android guest boot run 20260918_050641

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260918_050641.
I found status `fail` with 7 passed, 1 failed, 0 skipped.

## What I required

I required qemu-system-x86_64, the official android-x86_64-9.0-r2.iso
(SHA-1 1cc85b5ed7c830ff71aecf8405c7281a9c995aa0), a qcow2 from landed
ISOConverter._create_disk, SeaBIOS/ISOLINUX on installer -nographic stdout,
and a separate live kernel/initrd boot that only sets phone_ready after
adb connect + adb shell. Windows uses -accel whpx,kernel-irqchip=off.
I refused a dummy boot, prompt_bridge, a second disk-create owner, and
READY from ISOLINUX.

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
  - error: `CheckFailure: Android live boot failed before ADB: QEMU exited rc=4294967295 before ADB userspace proof. stderr="C:\\Program Files\\qemu\\qemu-system-x86_64.exe: warning: host doesn't support requested feature: CPUID[eax=80000001h].ECX.svm [bit 2]\nC:\\Program Files\\qemu\\qemu-system-x86_64.exe: warning: host doesn't support requested feature: CPUID[eax=80000001h].ECX.svm [bit 2]\n" console='sddr55\n[    6.525512] usbcore: registered new interface driver ums-usbat\n[    6.528130] i8042: PNP: PS/2 Controller [PNP0303:KBD,PNP0f13:MOU] at 0x60,0x64 irq 1,12\n[    6.532440] serio: i8042 KBD port at 0x60,0x64 irq 1\n[    6.536177] serio: i8042 AUX port at 0x60,0x64 irq 12\n[    6.538865] hv_vmbus: registering driver hyperv_keyboard\n[    6.541301] mousedev: PS/2 mouse device common for all mice\n[    6.544257] rtc_cmos 00:05: RTC can wake from S4\n[    6.548917] rtc_cmos 00:05: registered as rtc0\n[    6.551174] rtc_cmos 00:05: setting system clock to 2026-09-18 10:06:56 UTC (1789726016)\n[    6.555058] rtc_cmos 00:05: alarms up to one day, y3k, 242 bytes nvram, hpet irqs\n[    6.559018] IR Sharp protocol handler initialized\n[    6.561305] IR XMP protocol handler initialized\n[    6.563444] device-mapper: uevent: version 1.0.3\n[    6.565926] device-mapper: ioctl: 4.39.0-ioctl (2018-04-03) initialised: dm-devel@redhat.com\n[    6.570045] sdhci: Secure Digital Host Controller Interface driver\n[    6.572614] sdhci: Copyright(c) Pierre Ossman\n[    6.574862] sdhci-pltfm: SDHCI platform and OF driver helper\n[    6.578035] hidraw: raw HID events driver (C) Jiri Kosina\n[    6.581061] usbcore: registered new interface driver usbhid\n[    6.583584] usbhid: USB HID core driver\n[    6.585648] ashmem: initialized\n[    6.587208] oprofile: using NMI interrupt.\n[    6.590888] xt_time: kernel timezone is -0000\n[    6.593083] Initializing XFRM netlink socket\n[    6.595374] NET: Registered protocol family 10\n[    6.598947] Segment Routing with IPv6\n[    6.599766] mip6: Mobile IPv6\n[    6.601994] sit: IPv6, IPv4 and MPLS over IPv4 tunneling driver\n[    6.605021] NET: Registered protocol family 17\n[    6.606902] NET: Registered protocol family 15\n[    6.608807] NET: Registered protocol family 35\n[    6.611514] mce: Using 0 MCE banks\n[    6.613853] registered taskstats version 1\n[    6.616267] Loading compiled-in X.509 certificates\n[    6.619063] Key type ._fscrypt registered\n[    6.623539] Key type .fscrypt registered\n[    6.623602] ata2.00: ATAPI: QEMU DVD-ROM, 2.5+, max UDMA/100\n[    6.625724] Key type fscrypt-provisioning registered\n[    6.630538] ata1.00: ATA-7: QEMU HARDDISK, 2.5+, max UDMA/100\n[    6.631439]   Magic number: 10:495:123\n[    6.633744] ata1.00: 2097152 sectors, multi 16: LBA48 \n[    6.634511] acpi LNXSYBUS:01: hash matches\n[    6.637477] ata1.01: ATAPI: QEMU DVD-ROM, 2.5+, max UDMA/100\n[    6.642150] Unstable clock detected, switching default tracing clock to "global"\n[    6.642150] If you want to keep using the local clock, then add:\n[    6.642150]   "trace_clock=local"\n[    6.642150] on the kernel command line\n[    6.663941] scsi 0:0:0:0: Direct-Access     ATA      QEMU HARDDISK    2.5+ PQ: 0 ANSI: 5\n[    6.668135] sd 0:0:0:0: Attached scsi generic sg0 type 0\n[    6.668516] sd 0:0:0:0: [sda] 2097152 512-byte logical blocks: (1.07 GB/1.00 GiB)\n[    6.673683] sd 0:0:0:0: [sda] Write Protect is off\n[    6.673954] scsi 0:0:1:0: CD-ROM            QEMU     QEMU DVD-ROM     2.5+ PQ: 0 ANSI: 5\n[    6.675902] sd 0:0:0:0: [sda] Write cache: enabled, read cache: enabled, doesn\'t support DPO or FUA\n[    6.688029] sr 0:0:1:0: [sr0] scsi3-mmc drive: 4x/4x cd/rw xa/form2 tray\n[    6.688257] sd 0:0:0:0: [sda] Attached SCSI disk\n[    6.692378] cdrom: Uniform CD-ROM driver Revision: 3.20\n[    6.697738] sr 0:0:1:0: Attached scsi generic sg1 type 5\n[    6.700789] scsi 1:0:0:0: CD-ROM            QEMU     QEMU DVD-ROM     2.5+ PQ: 0 ANSI: 5\n[    6.727009] sr 1:0:0:0: [sr1] scsi3-mmc drive: 4x/4x cd/rw xa/form2 tray\n[    6.731448] sr 1:0:0:0: Attached scsi generic sg2 type 5\n[    6.736092] Freeing unused kernel image memory: 1492K\n[    6.738782] Write protecting the kernel read-only data: 18432k\n[    6.742447] Freeing unused kernel image memory: 2016K\n[    6.745597] Freeing unused kernel image memory: 412K\n[    6.747977] rodata_test: all tests were successful\n[    6.750486] Run /init as init process\nDetecting Android-x86... found at /dev/sr0\nconsole:/ # '`

## Artifacts

- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_050641\result.json`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_050641\result.md`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_050641\result.log`

