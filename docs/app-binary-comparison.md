# L12next Control: encrypted vs decrypted binary comparison

## Result

The original installed App Store application and the Frida-dumped decrypted IPA were compared byte-for-byte.

| Property | Original | Decrypted |
|---|---:|---:|
| Main executable size | 879,936 bytes | 879,936 bytes |
| Mach-O architecture | arm64 | arm64 |
| cryptid | 1 | 0 |
| cryptoff | 0x3C000 | 0x3C000 |
| cryptsize | 0x1000 | 0x1000 |

There are **4,078 differing bytes** in the executable.

The differences are:
- one byte at file offset `0x0DE0`, the encryption flag (`cryptid 1 -> 0`);
- decrypted code bytes inside the single 4 KiB DRM range `0x3C000-0x3CFFF`.

No size expansion, repacking, or broad rewrite of the Mach-O was observed.

## Meaning for the reverse engineering

This confirms that the decrypted IPA is a faithful copy of the installed app with the protected code page restored from memory.

The recovered MIDI structures are therefore suitable for protocol analysis:
- `recvCC` lookup table;
- command/feedback dispatch;
- scene/transport mapping;
- channel and master parameter mapping.

The `recvCC` table is located outside the DRM page at file offset `0x7AEA4`.

## Decrypted DRM page

Disassembly of the restored page shows Swift application logic, including paths that construct or use peer/data dictionary keys (for example `p2pDataKey` and `p2pStringKey`-style keys).

So the protected 4 KiB page does not appear to be the sole storage location of the MIDI command map. Most of the MIDI mapping data was already outside the protected page; the decrypted page is still valuable because it makes the executable complete and allows control-flow analysis without a missing block.

## Important master-control correction

The raw incoming table contains:

```text
B8 54 -> function 33 -> undocumented/app-only
B9 54 -> function 34 -> MASTER MUTE
BA 54 -> function 35 -> MASTER FADER
BB 54 -> function 36 -> MASTER COMP
```

The public ZOOM MIDI table confirms MASTER MUTE/FADER/COMP on MIDI channels 10/11/12 respectively. Function 33 therefore remains unnamed until its app handler is proven.
