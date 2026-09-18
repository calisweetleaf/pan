# Thyris Android guest boot run 20260918_035525

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260918_035525.
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
  - error: `CheckFailure: Android ADB userspace failed loud: No adb shell within 1800.0s on 127.0.0.1:62452. Detecting Android-x86 / init markers are not READY. detail="adb devices listed offline/unauthorized. connect='failed to connect to 127.0.0.1:62452' devices='List of devices attached\\r\\n127.0.0.1:62452\\toffline'" markers=['Detecting Android-x86', 'init: '] debug_exits=0 stale_qemu=[] stderr='' console='  1.872445] usbcore: registered new interface driver ums-sddr55\n[    1.874857] usbcore: registered new interface driver ums-usbat\n[    1.877506] i8042: PNP: PS/2 Controller [PNP0303:KBD,PNP0f13:MOU] at 0x60,0x64 irq 1,12\n[    1.891004] serio: i8042 KBD port at 0x60,0x64 irq 1\n[    1.891004] serio: i8042 AUX port at 0x60,0x64 irq 12\n[    1.899230] hv_vmbus: registering driver hyperv_keyboard\n[    1.903859] mousedev: PS/2 mouse device common for all mice\n[    1.906711] rtc_cmos 00:05: RTC can wake from S4\n[    1.919626] rtc_cmos 00:05: registered as rtc0\n[    1.919626] rtc_cmos 00:05: setting system clock to 2026-09-18 08:25:07 UTC (1789719907)\n[    1.922920] rtc_cmos 00:05: alarms up to one day, y3k, 242 bytes nvram, hpet irqs\n[    1.928107] IR Sharp protocol handler initialized\n[    1.928688] IR XMP protocol handler initialized\n[    1.928688] device-mapper: uevent: version 1.0.3\n[    1.934563] device-mapper: ioctl: 4.39.0-ioctl (2018-04-03) initialised: dm-devel@redhat.com\n[    1.940418] sdhci: Secure Digital Host Controller Interface driver\n[    1.940759] sdhci: Copyright(c) Pierre Ossman\n[    1.942416] sdhci-pltfm: SDHCI platform and OF driver helper\n[    1.943092] hidraw: raw HID events driver (C) Jiri Kosina\n[    1.953878] usbcore: registered new interface driver usbhid\n[    1.954118] usbhid: USB HID core driver\n[    1.958348] ashmem: initialized\n[    1.963223] oprofile: using NMI interrupt.\n[    1.988033] xt_time: kernel timezone is -0000\n[    1.997611] Initializing XFRM netlink socket\n[    2.023247] NET: Registered protocol family 10\n[    2.042460] ata1.00: ATA-7: QEMU HARDDISK, 2.5+, max UDMA/100\n[    2.042810] ata1.00: 2097152 sectors, multi 16: LBA48 \n[    2.042810] ata1.01: ATAPI: QEMU DVD-ROM, 2.5+, max UDMA/100\n[    2.050285] ata2.00: ATAPI: QEMU DVD-ROM, 2.5+, max UDMA/100\n[    2.063986] Segment Routing with IPv6\n[    2.079799] mip6: Mobile IPv6\n[    2.079799] sit: IPv6, IPv4 and MPLS over IPv4 tunneling driver\n[    2.112841] NET: Registered protocol family 17\n[    2.112841] NET: Registered protocol family 15\n[    2.112841] NET: Registered protocol family 35\n[    2.126937] mce: Using 10 MCE banks\n[    2.127487] scsi 0:0:0:0: Direct-Access     ATA      QEMU HARDDISK    2.5+ PQ: 0 ANSI: 5\n[    2.140892] registered taskstats version 1\n[    2.140892] Loading compiled-in X.509 certificates\n[    2.153968] sd 0:0:0:0: Attached scsi generic sg0 type 0\n[    2.162379] Key type ._fscrypt registered\n[    2.162635] Key type .fscrypt registered\n[    2.168682] Key type fscrypt-provisioning registered\n[    2.189499] scsi 0:0:1:0: CD-ROM            QEMU     QEMU DVD-ROM     2.5+ PQ: 0 ANSI: 5\n[    2.189018]   Magic number: 10:592:422\n[    2.194589] Unstable clock detected, switching default tracing clock to "global"\n[    2.194589] If you want to keep using the local clock, then add:\n[    2.194589]   "trace_clock=local"\n[    2.194589] on the kernel command line\n[    2.195588] sd 0:0:0:0: [sda] 2097152 512-byte logical blocks: (1.07 GB/1.00 GiB)\n[    2.201323] sd 0:0:0:0: [sda] Write Protect is off\n[    2.201323] sd 0:0:0:0: [sda] Write cache: enabled, read cache: enabled, doesn\'t support DPO or FUA\n[    2.218480] sr 0:0:1:0: [sr0] scsi3-mmc drive: 4x/4x cd/rw xa/form2 tray\n[    2.239594] cdrom: Uniform CD-ROM driver Revision: 3.20\n[    2.252853] sr 0:0:1:0: Attached scsi generic sg1 type 5\n[    2.274996] scsi 1:0:0:0: CD-ROM            QEMU     QEMU DVD-ROM     2.5+ PQ: 0 ANSI: 5\n[    2.274996] sd 0:0:0:0: [sda] Attached SCSI disk\n[    2.328939] sr 1:0:0:0: [sr1] scsi3-mmc drive: 4x/4x cd/rw xa/form2 tray\n[    2.335430] sr 1:0:0:0: Attached scsi generic sg2 type 5\n[    2.519764] Freeing unused kernel image memory: 1492K\n[    2.519764] Write protecting the kernel read-only data: 18432k\n[    2.536939] Freeing unused kernel image memory: 2016K\n[    2.543032] Freeing unused kernel image memory: 412K\n[    2.543032] rodata_test: all tests were successful\n[    2.543032] Run /init as init process\nDetecting Android-x86... found at /dev/sr0\n'`

## Artifacts

- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_035525\result.json`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_035525\result.md`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_035525\result.log`

