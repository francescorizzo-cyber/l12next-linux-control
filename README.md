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

## Interactive protocol tester

The repository now includes a guided tester that sends one command at a time, asks for confirmation before transmission, auto-detects the L12next ALSA MIDI port, and writes a CSV test log.

List confirmed commands:

```bash
python3 tools/protocol_tester.py --list
```

Test all confirmed commands interactively:

```bash
python3 tools/protocol_tester.py
```

Test only one command:

```bash
python3 tools/protocol_tester.py --command REC
```

When new candidate commands are added to `tools/commands.json` with status `experimental`, include them explicitly with:

```bash
python3 tools/protocol_tester.py --experimental
```

The tester intentionally does not brute-force unknown MIDI values. Experimental commands should come from captures or controlled hypotheses and be added to `tools/commands.json` first.

## Quick manual test

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


## Current verified control coverage

The project currently has verified USB ALSA control for:
- transport: PLAY, STOP, REW, FF, RECORD / OVERDUB-related controls
- scene selection 1-10, SAVE and RECALL
- per-channel faders using `Bn 3C vv` (verified on CH1 and CH2)
- AutoFonic gain/trim control already exists in the application logic

### Next AutoFonic priorities

The main protocol work still worth doing is:
- real mixer feedback/state synchronization
- per-channel mute
- Monitor 1 / Monitor 2 sends
- physical REC/STOP event synchronization
- safer, slower gain correction using mixer state feedback
