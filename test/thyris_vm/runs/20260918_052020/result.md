# Thyris Android guest boot run 20260918_052020

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260918_052020.
I found status `fail` with 7 passed, 1 failed, 0 skipped.

## What I required

I required qemu-system-x86_64, the official android-x86_64-9.0-r2.iso
(SHA-1 1cc85b5ed7c830ff71aecf8405c7281a9c995aa0), a qcow2 from landed
ISOConverter._create_disk, SeaBIOS/ISOLINUX on installer -nographic stdout,
and a disk-install via this ISO's AUTO_INSTALL=force, then a disk boot
that only sets phone_ready after adb connect + adb shell. Windows uses
-accel whpx,kernel-irqchip=off. I refused a dummy boot, prompt_bridge,
a second disk-create owner, and READY from ISOLINUX.

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
  - error: `CheckFailure: Android live boot failed before ADB: disk-boot QEMU exited rc=4294967295 before ADB userspace proof. install_markers=['Congratulations', 'installed successfully', 'Installing Android-x86', 'Syncing to disk', 'Formatting'] stderr="C:\\Program Files\\qemu\\qemu-system-x86_64.exe: warning: host doesn't support requested feature: CPUID[eax=80000001h].ECX.svm [bit 2]\nC:\\Program Files\\qemu\\qemu-system-x86_64.exe: warning: host doesn't support requested feature: CPUID[eax=80000001h].ECX.svm [bit 2]\n" console='[    7.022381] usbcore: registered new interface driver ums-onetouch\n[    7.027388] usbcore: registered new interface driver ums-realtek\n[    7.031982] usbcore: registered new interface driver ums-sddr09\n[    7.036501] usbcore: registered new interface driver ums-sddr55\n[    7.040990] usbcore: registered new interface driver ums-usbat\n[    7.045566] i8042: PNP: PS/2 Controller [PNP0303:KBD,PNP0f13:MOU] at 0x60,0x64 irq 1,12\n[    7.055304] serio: i8042 KBD port at 0x60,0x64 irq 1\n[    7.059661] serio: i8042 AUX port at 0x60,0x64 irq 12\n[    7.066346] hv_vmbus: registering driver hyperv_keyboard\n[    7.071003] mousedev: PS/2 mouse device common for all mice\n[    7.076493] rtc_cmos 00:05: RTC can wake from S4\n[    7.082653] rtc_cmos 00:05: registered as rtc0\n[    7.086901] rtc_cmos 00:05: setting system clock to 2026-09-18 10:35:50 UTC (1789727750)\n[    7.092920] rtc_cmos 00:05: alarms up to one day, y3k, 242 bytes nvram, hpet irqs\n[    7.098690] IR Sharp protocol handler initialized\n[    7.102334] IR XMP protocol handler initialized\n[    7.106287] device-mapper: uevent: version 1.0.3\n[    7.109845] device-mapper: ioctl: 4.39.0-ioctl (2018-04-03) initialised: dm-devel@redhat.com\n[    7.111745] ata1.00: ATA-7: QEMU HARDDISK, 2.5+, max UDMA/100\n[    7.117813] sdhci: Secure Digital Host Controller Interface driver\n[    7.121071] ata1.00: 16777216 sectors, multi 16: LBA48 \n[    7.125895] sdhci: Copyright(c) Pierre Ossman\n[    7.126061] sdhci-pltfm: SDHCI platform and OF driver helper\n[    7.126135] hidraw: raw HID events driver (C) Jiri Kosina\n[    7.126188] usbcore: registered new interface driver usbhid\n[    7.131214] ata2.00: ATAPI: QEMU DVD-ROM, 2.5+, max UDMA/100\n[    7.133104] usbhid: USB HID core driver\n[    7.152690] scsi 0:0:0:0: Direct-Access     ATA      QEMU HARDDISK    2.5+ PQ: 0 ANSI: 5\n[    7.154099] ashmem: initialized\n[    7.160441] sd 0:0:0:0: [sda] 16777216 512-byte logical blocks: (8.59 GB/8.00 GiB)\n[    7.162399] oprofile: using NMI interrupt.\n[    7.168411] sd 0:0:0:0: Attached scsi generic sg0 type 0\n[    7.174773] xt_time: kernel timezone is -0000\n[    7.175288] sd 0:0:0:0: [sda] Write Protect is off\n[    7.178394] Initializing XFRM netlink socket\n[    7.182896] scsi 1:0:0:0: CD-ROM            QEMU     QEMU DVD-ROM     2.5+ PQ: 0 ANSI: 5\n[    7.185348] NET: Registered protocol family 10\n[    7.190779] sd 0:0:0:0: [sda] Write cache: enabled, read cache: enabled, doesn\'t support DPO or FUA\n[    7.197362] Segment Routing with IPv6\n[    7.204475] mip6: Mobile IPv6\n[    7.207406] sit: IPv6, IPv4 and MPLS over IPv4 tunneling driver\n[    7.207652]  sda: sda1\n[    7.212693] NET: Registered protocol family 17\n[    7.215014] sd 0:0:0:0: [sda] Attached SCSI disk\n[    7.217242] NET: Registered protocol family 15\n[    7.217246] NET: Registered protocol family 35\n[    7.227928] mce: Using 0 MCE banks\n[    7.230755] registered taskstats version 1\n[    7.233993] sr 1:0:0:0: [sr0] scsi3-mmc drive: 4x/4x cd/rw xa/form2 tray\n[    7.234000] Loading compiled-in X.509 certificates\n[    7.238717] cdrom: Uniform CD-ROM driver Revision: 3.20\n[    7.245428] Key type ._fscrypt registered\n[    7.246983] sr 1:0:0:0: Attached scsi generic sg1 type 5\n[    7.249103] Key type .fscrypt registered\n[    7.256866] Key type fscrypt-provisioning registered\n[    7.261612]   Magic number: 10:460:578\n[    7.264808] platform pcspkr: hash matches\n[    7.268322] Unstable clock detected, switching default tracing clock to "global"\n[    7.268322] If you want to keep using the local clock, then add:\n[    7.268322]   "trace_clock=local"\n[    7.268322] on the kernel command line\n[    7.286986] Freeing unused kernel image memory: 1492K\n[    7.290947] Write protecting the kernel read-only data: 18432k\n[    7.297718] Freeing unused kernel image memory: 2016K\n[    7.302123] Freeing unused kernel image memory: 412K\n[    7.305798] rodata_test: all tests were successful\n[    7.309421] Run /init as init process\nDetecting Android-x86... found at /dev/sda1\nconsole:/ # '`

## Artifacts

- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_052020\result.json`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_052020\result.md`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_052020\result.log`

