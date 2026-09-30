# L12next Linux Control

Experimental, unofficial Linux/Raspberry Pi control and analysis tools for the **ZOOM LiveTrak L12next**.

> This project is independent and is not affiliated with or endorsed by ZOOM Corporation.

## Verified findings

Remote transport control works over the normal BLE-MIDI connection used with the L12next/BTA-1.

| Action | MIDI bytes |
|---|---|
| REC | `B9 57 03` |
| STOP | `BB 57 03` |

The commands were obtained by comparing BLE traffic from the official control app and were then verified experimentally from Linux with `aseqsend`.

The L12next USB Audio capture interface was also observed with 14 channels at 48 kHz, 32-bit, supporting `S32_LE` and `FLOAT_LE`.

## Quick test

Find the current ALSA MIDI destination:

```bash
aconnect -l
```

Example REC:

```bash
printf '\xB9\x57\x03' > /tmp/rec.bin
aseqsend -p 128:0 -s /tmp/rec.bin
```

Example STOP:

```bash
printf '\xBB\x57\x03' > /tmp/stop.bin
aseqsend -p 128:0 -s /tmp/stop.bin
```

The ALSA client number can change after reconnecting, so `128:0` must not be assumed permanently.

See [docs/protocol.md](docs/protocol.md) for reverse-engineering notes.

## Roadmap

The next goal is an experimental Raspberry Pi "automatic sound engineer":

1. capture the 14-channel USB stream;
2. calculate RMS, peak and clipping per channel;
3. detect performance vs real silence;
4. automatically start/stop recording;
5. later test conservative level suggestions and optional small automatic adjustments.

## Disclaimer

Protocol details are based on observation and experimentation and are not official ZOOM documentation. They may change with firmware/app versions. Use at your own risk.
