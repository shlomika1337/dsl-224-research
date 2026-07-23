# D-Link DSL-224 Reverse Engineering

Ongoing embedded security research on a D-Link DSL-224 xDSL gateway. The goal is to reach a root shell, extract a bit-exact firmware image, and analyze the platform for vulnerabilities.

**Status: work in progress.** Root shell and full flash extraction are done. Static analysis of the firmware is underway.

## Target

| | |
|---|---|
| Device | D-Link DSL-224 |
| SoC | Realtek RTL8685, MIPS 32-bit, big-endian |
| Flash | Winbond 25Q64JVSIQ, 8 MB SPI NOR, SOIC-8 |
| WLAN | Realtek RTL8192 family |
| Userland | BusyBox |

## UART Access

The board exposes a 4-pin serial header at **CN3**, pin 1 marked, ordered `VCC GND TX RX`. VCC is left disconnected; the target is powered from its own supply with a common ground.

Console parameters were measured rather than guessed. The boot-time TX line was captured on an oscilloscope and the narrowest bit width read directly off the trace, giving **115200 8N1**.

```
CN3
 1  VCC   (not connected)
 2  GND   -> host GND
 3  TX    -> host RX
 4  RX    -> host TX
```

The USB serial link was built from a spare ESP8266 (ideaspark board, CH340). The ESP runs a small SoftwareSerial bridge sketch: the router's TX/RX are wired to GPIO4/GPIO5, and the sketch forwards bytes in both directions between that soft UART and the hardware UART0 that reaches the PC over the onboard CH340. It works, but SoftwareSerial bit-bangs the line in software, so at 115200 full-duplex it drops bytes during bursts (boot spew, dumping a file) even with an enlarged RX buffer.

```
tio -b 115200 /dev/ttyUSB1
```

## Flash Layout

From `/proc/mtd` on the running device:

```
dev:    size     erasesize  name
mtd0: 00020000 00001000 "boot"      128 KB  bootloader
mtd1: 00010000 00001000 "MAK"        64 KB  board data
mtd2: 00010000 00001000 "config"     64 KB  settings
mtd3: 001c0000 00001000 "kernel"   1.75 MB  kernel
mtd4: 00600000 00001000 "rootfs"      6 MB  squashfs
mtd5: 007c0000 00001000 "Linux"    7.75 MB  kernel + rootfs alias
mtd6: 00800000 00001000 "ALL"         8 MB  full chip alias
```

`mtd5` and `mtd6` are aliases over the same physical flash as the earlier partitions, not separate data.

## Firmware Extraction

Host and target were placed on the same subnet over Ethernet (router `192.168.1.1`, host `192.168.1.100/24`), then the full chip was streamed off with BusyBox `nc`.

```
# target
nc -l -p 5555 < /dev/mtd6

# host
nc 192.168.1.1 5555 > dsl224_full_8M.bin
```

Verified against the source before any analysis:

```
# target
md5sum /dev/mtd6
# host
md5sum dsl224_full_8M.bin
ls -l dsl224_full_8M.bin      # 8388608 bytes
```

`binwalk` locates the root filesystem at offset `0x200000`:

```
2097152   0x200000   SquashFS filesystem, little endian, version 4.0,
                      compression: xz, inode count: 1496, image size: 3188780
```

Carve and unpack:

```
dd if=dsl224_full_8M.bin of=rootfs.sqfs bs=4096 skip=512
unsquashfs -d squashfs-root rootfs.sqfs
```

Note that the live `/etc` on the running device is populated into RAM at boot and holds runtime-generated files (wireless `.dat`, state) that do not exist in the read-only squashfs. The baked template is the 3.1 MB image extracted above.

## Findings

**Root shell.** The console drops to an interactive shell running as uid 0 (`/bin/sh`, BusyBox).

**Administrative credential.** `/etc/passwd` on the device contains an inline MD5-crypt hash:

```
admin:$1$lX4V2Kov$W3Mb6EkrSxcT1aHhrA8C//:0:0:root:/:/bin/sh
```

Cracked with hashcat (`-m 500`, rockyou) to `admin`.

```
$1$        MD5-crypt
lX4V2Kov   salt
```

Whether this hash is baked into the firmware image (static across all units) or generated per device is under verification against the extracted rootfs and other firmware versions. Do not treat it as a default credential finding until confirmed.

## In Progress

- Confirm whether the credential salt is fixed in the shipped firmware and identical across DSL-224 firmware versions.
- Map the remaining MTD partitions (`boot`, `MAK`, `config`) and document their contents.
- Static analysis of the `httpd` request handler dispatch in Ghidra for memory-safety and command-injection surface.
- On-target dynamic analysis with gdb-multiarch and a cross-compiled static big-endian MIPS gdbserver.

## Notes

All work was performed on hardware I own. Nothing here should be run against equipment you do not own or have permission to test.
