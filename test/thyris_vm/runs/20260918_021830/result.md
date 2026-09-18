# Thyris Android guest boot run 20260918_021830

I ran `python test/thyris_vm/test_thyris_android_boot.py` at 20260918_021830.
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
  - error: `CheckFailure: Android ADB userspace failed loud: No adb shell within 900.0s on 127.0.0.1:60455. ISOLINUX/userspace console is not READY. detail="connect='already connected to 127.0.0.1:60455' shell='adb.exe: device offline' rc=1" markers=['Detecting Android-x86', 'init: '] stderr='' console='   1.721484] usbcore: registered new interface driver ums-sddr55\n[    1.721827] usbcore: registered new interface driver ums-usbat\n[    1.724458] i8042: PNP: PS/2 Controller [PNP0303:KBD,PNP0f13:MOU] at 0x60,0x64 irq 1,12\n[    1.732495] serio: i8042 KBD port at 0x60,0x64 irq 1\n[    1.735225] serio: i8042 AUX port at 0x60,0x64 irq 12\n[    1.738339] hv_vmbus: registering driver hyperv_keyboard\n[    1.739631] mousedev: PS/2 mouse device common for all mice\n[    1.741977] rtc_cmos 00:05: RTC can wake from S4\n[    1.748935] rtc_cmos 00:05: registered as rtc0\n[    1.750080] rtc_cmos 00:05: setting system clock to 2026-09-18 07:03:31 UTC (1789715011)\n[    1.752316] rtc_cmos 00:05: alarms up to one day, y3k, 242 bytes nvram, hpet irqs\n[    1.753599] IR Sharp protocol handler initialized\n[    1.754036] IR XMP protocol handler initialized\n[    1.755011] device-mapper: uevent: version 1.0.3\n[    1.756734] device-mapper: ioctl: 4.39.0-ioctl (2018-04-03) initialised: dm-devel@redhat.com\n[    1.760715] sdhci: Secure Digital Host Controller Interface driver\n[    1.760980] sdhci: Copyright(c) Pierre Ossman\n[    1.761963] sdhci-pltfm: SDHCI platform and OF driver helper\n[    1.763542] hidraw: raw HID events driver (C) Jiri Kosina\n[    1.766771] usbcore: registered new interface driver usbhid\n[    1.767083] usbhid: USB HID core driver\n[    1.769643] ashmem: initialized\n[    1.774896] oprofile: using NMI interrupt.\n[    1.789779] xt_time: kernel timezone is -0000\n[    1.798959] Initializing XFRM netlink socket\n[    1.800604] NET: Registered protocol family 10\n[    1.812463] Segment Routing with IPv6\n[    1.814397] mip6: Mobile IPv6\n[    1.818368] sit: IPv6, IPv4 and MPLS over IPv4 tunneling driver\n[    1.827884] NET: Registered protocol family 17\n[    1.828845] NET: Registered protocol family 15\n[    1.830077] NET: Registered protocol family 35\n[    1.834068] mce: Using 10 MCE banks\n[    1.837752] registered taskstats version 1\n[    1.838036] Loading compiled-in X.509 certificates\n[    1.839619] Key type ._fscrypt registered\n[    1.840040] Key type .fscrypt registered\n[    1.840225] Key type fscrypt-provisioning registered\n[    1.847541]   Magic number: 10:624:66\n[    1.850201] Unstable clock detected, switching default tracing clock to "global"\n[    1.850201] If you want to keep using the local clock, then add:\n[    1.850201]   "trace_clock=local"\n[    1.850201] on the kernel command line\n[    1.864355] ata2.00: ATAPI: QEMU DVD-ROM, 2.5+, max UDMA/100\n[    1.869141] ata1.00: ATA-7: QEMU HARDDISK, 2.5+, max UDMA/100\n[    1.869452] ata1.00: 2097152 sectors, multi 16: LBA48 \n[    1.870010] ata1.01: ATAPI: QEMU DVD-ROM, 2.5+, max UDMA/100\n[    1.890884] scsi 0:0:0:0: Direct-Access     ATA      QEMU HARDDISK    2.5+ PQ: 0 ANSI: 5\n[    1.897707] sd 0:0:0:0: Attached scsi generic sg0 type 0\n[    1.902153] scsi 0:0:1:0: CD-ROM            QEMU     QEMU DVD-ROM     2.5+ PQ: 0 ANSI: 5\n[    1.907430] sd 0:0:0:0: [sda] 2097152 512-byte logical blocks: (1.07 GB/1.00 GiB)\n[    1.910122] sd 0:0:0:0: [sda] Write Protect is off\n[    1.911428] sr 0:0:1:0: [sr0] scsi3-mmc drive: 4x/4x cd/rw xa/form2 tray\n[    1.912682] cdrom: Uniform CD-ROM driver Revision: 3.20\n[    1.913376] sd 0:0:0:0: [sda] Write cache: enabled, read cache: enabled, doesn\'t support DPO or FUA\n[    1.919478] sr 0:0:1:0: Attached scsi generic sg1 type 5\n[    1.925162] scsi 1:0:0:0: CD-ROM            QEMU     QEMU DVD-ROM     2.5+ PQ: 0 ANSI: 5\n[    1.929220] sd 0:0:0:0: [sda] Attached SCSI disk\n[    1.953511] sr 1:0:0:0: [sr1] scsi3-mmc drive: 4x/4x cd/rw xa/form2 tray\n[    1.955737] sr 1:0:0:0: Attached scsi generic sg2 type 5\n[    2.085922] Freeing unused kernel image memory: 1492K\n[    2.085922] Write protecting the kernel read-only data: 18432k\n[    2.100528] Freeing unused kernel image memory: 2016K\n[    2.100528] Freeing unused kernel image memory: 412K\n[    2.100528] rodata_test: all tests were successful\n[    2.100528] Run /init as init process\nDetecting Android-x86... found at /dev/sr0\n'`

## Artifacts

- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_021830\result.json`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_021830\result.md`
- `C:\Users\trent\pan\test\thyris_vm\runs\20260918_021830\result.log`

