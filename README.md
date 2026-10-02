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


## Complete command table

| Command | Category | MIDI bytes | Status | Notes |
|---|---|---|---|---|
| CH1_FADER | channel | `B0 3C vv` | confirmed | Channel 1 fader, absolute 7-bit value. Verified via USB ALSA. Captured reference values: -inf=00, ~-20dB=1D, ~-10dB=35, 0dB=57. |
| CH2_FADER | channel | `B1 3C vv` | confirmed | Channel 2 fader, absolute 7-bit value. Verified via USB ALSA. |
| CHANNEL_FADER_PATTERN | channel | `Bn 3C vv` | confirmed | General fader pattern: MIDI status Bn selects mixer channel (n=0..15 => CH1..CH16), CC 0x3C, vv is absolute 7-bit fader position. Verified on CH1 and CH2 and generalized from MIDI channel mapping. |
| OVERDUB_MODE | recording | `BE 57 03` | confirmed | OVERDUB MODE button according to the official L12next MIDI implementation (CC 0x57, MIDI channel 15). |
| SCENE_DELETE | scene | `BD 59 03` | manual_confirmed | Scene DELETE. Official L12next MIDI implementation lists CC 0x59 on MIDI channel 14 for Scene Delete. Value 03 matches the verified button-press convention; destructive hardware replay not yet performed. |
| SCENE_RECALL | scene | `BA 56 03` | confirmed | Triggers RECALL for the currently selected scene. Verified on hardware over USB ALSA. |
| SCENE_SAVE | scene | `B9 56 03` | confirmed | Saves the currently selected scene. Verified by direct USB ALSA hardware test. |
| SCENE_SELECT_1 | scene | `BB 56 03` | confirmed | Selects scene 1. CALL/activate scene 1 by following with `BA 56 03` (RECALL). |
| SCENE_SELECT_10 | scene | `BC 59 03` | confirmed | Selects scene 10. Verified by direct USB ALSA hardware test. |
| SCENE_SELECT_2 | scene | `BC 56 03` | confirmed | Selects scene 2. Verified by direct USB ALSA hardware test. |
| SCENE_SELECT_3 | scene | `BD 56 03` | confirmed | Selects scene 3. Verified by direct USB ALSA hardware test. |
| SCENE_SELECT_4 | scene | `BE 56 03` | confirmed | Selects scene 4. Verified by direct USB ALSA hardware test. |
| SCENE_SELECT_5 | scene | `BF 56 03` | confirmed | Selects scene 5. Verified by direct USB ALSA hardware test. |
| SCENE_SELECT_6 | scene | `B0 57 03` | confirmed | Selects scene 6; leaves scene operation pending until RECALL. |
| SCENE_SELECT_7 | scene | `B1 57 03` | confirmed | Selects scene 7; leaves scene operation pending until RECALL. |
| SCENE_SELECT_8 | scene | `B2 57 03` | confirmed | Selects scene 8; leaves scene operation pending until RECALL. |
| SCENE_SELECT_9 | scene | `B3 57 03` | confirmed | Selects scene 9; leaves scene operation pending until RECALL. |
| RESET | system | `B4 57 03` | confirmed | Triggers RESET. Reconfirmed by direct USB ALSA hardware test. |
| FF | transport | `BD 57 03` | confirmed | Fast-forward command verified on hardware over USB ALSA. |
| PLAY | transport | `BA 57 03` | confirmed | Starts playback ('PLAY SOUND'). Verified by direct USB ALSA hardware test. |
| RECORD | transport | `B9 57 03` | confirmed | RECORD BUTTON according to the official L12next MIDI implementation (CC 0x57, MIDI channel 10). On the tested mixer this was observed to arm channels while Overdub mode was active. |
| REW | transport | `BC 57 03` | confirmed | Rewind command verified on hardware over USB ALSA. |
| STOP | transport | `BB 57 03` | confirmed | Stops playback/transport. Verified by direct USB ALSA hardware test. |


## Scene 1 CALL

The verified sequence to activate scene 1 is:

```
BB 56 03  -> select scene 1
BA 56 03  -> RECALL
```

The older `B7 57 03` mapping should not be used for scene 1.
