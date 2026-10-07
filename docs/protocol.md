# ZOOM LiveTrak L12next – protocol reverse engineering

## Status

This document combines three evidence classes:

- **hardware-confirmed**: replayed or observed on the physical L12next;
- **manual/app-confirmed**: supported by the official MIDI implementation and/or the decrypted official app;
- **app-derived**: recovered from `L12next Control_decrypted.ipa` and not yet replay-tested.

The decrypted Mach-O reports `LC_ENCRYPTION_INFO_64` with `cryptid 0`.

## Transport and BLE

Observed BLE GATT characteristic:

```text
7772e5db-3868-4112-a1a9-f2669d106bf3
```

USB ALSA has also accepted the same three-byte MIDI Control Change messages.

## Confirmed commands

| Command | Bytes | Evidence |
|---|---|---|
| RECORD | `B9 57 03` | hardware + app function 47 |
| PLAY | `BA 57 03` | hardware + app function 48 |
| STOP | `BB 57 03` | hardware + app function 49 |
| REW | `BC 57 03` | hardware + app function 50 |
| FF | `BD 57 03` | hardware + app function 51 |
| OVERDUB MODE | `BE 57 03` | app/manual + hardware-compatible, function 52 |
| RESET | `B4 57 03` | hardware + app function 42 |
| SCENE SAVE | `B9 56 03` | hardware + app function 39 |
| SCENE RECALL | `BA 56 03` | hardware + app function 40 |
| SCENE DELETE | `BD 59 03` | app/manual; destructive replay not performed |

### Scene selection

| Scene | Bytes |
|---:|---|
| 1 | `BB 56 03` |
| 2 | `BC 56 03` |
| 3 | `BD 56 03` |
| 4 | `BE 56 03` |
| 5 | `BF 56 03` |
| 6 | `B0 57 03` |
| 7 | `B1 57 03` |
| 8 | `B2 57 03` |
| 9 | `B3 57 03` |
| 10 | `BC 59 03` |

All ten scene selectors map to **function ID 41**, with `target_id` 1..10.

To call scene 1:

```text
BB 56 03   # select scene 1
BA 56 03   # recall
```

The obsolete `B7 57 03` scene-1 mapping must not be used.

## Fader

The app table identifies **function ID 15** as the fader family at CC `0x3C`.

Hardware-confirmed:

```text
B0 3C vv   # CH1 fader
B1 3C vv   # CH2 fader
```

Observed CH1 reference values:

```text
00   -inf
1D   approximately -20 dB
35   approximately -10 dB
57   approximately 0 dB
```

## Pan

The decrypted app maps CC `0x08` to **function ID 3** over normal strip targets. This is currently **app-derived probable** and should be replay-tested before promotion to confirmed.

## Feedback

Feedback is distinct from commands.

Hardware-confirmed recording state:

```text
B8 57 05   # REC active
B8 57 00   # recording inactive / STOP
```

The decrypted app maps `B8 / CC 0x57` to **function ID 46**.

Recommended AutoFonic behavior:

```text
B8 57 05 -> AUTOREC ON
B8 57 00 -> AUTOREC OFF
```

### Incoming CC lookup table

A full `recvCC` lookup table is present in the decrypted Mach-O.

- file offset: `0x7AEA4`
- dimensions: `128 CC × 16 MIDI channels`
- entry size: `12` bytes
- non-zero entries recovered: **1464**
- distinct CC values represented: **93**
- function IDs observed: **0..78**

Indexing:

```text
entry = base + CC * 0xC0 + midi_channel_zero_based * 0x0C
```

Each entry is:

```text
uint32_le target_id
uint32_le function_id
uint32_le aux
```

`tools/feedback.json` records table structure, function counts and currently identified semantics. Unknown IDs remain intentionally unnamed.

Known function IDs:

| Function ID | Meaning | Confidence |
|---:|---|---|
| 3 | PAN | app-derived probable |
| 15 | FADER | app + hardware |
| 39 | SCENE SAVE | app + hardware |
| 40 | SCENE RECALL | app + hardware |
| 41 | SCENE SELECT | app + hardware |
| 42 | RESET | app + hardware |
| 46 | RECORD STATE | app + hardware |
| 47 | RECORD BUTTON | app + hardware |
| 48 | PLAY | app + hardware |
| 49 | STOP | app + hardware |
| 50 | REW | app + hardware |
| 51 | FAST FORWARD | app + hardware |
| 52 | OVERDUB MODE | app/manual |
| 70 | SCENE DELETE | app/manual |

## SysEx and meters

The decrypted app contains explicit incoming handlers evidenced by strings including:

```text
TrackParamUpdated
MasterParamUpdated
Scene Changed
Meters Changed
ERROR: invalid indexes for recvCC lookup table!
WARNING: received unhandled CC
Undefined sysEx MIDI message processing cmd
```

This establishes dedicated parsing paths for incoming CC, SysEx and meter/state traffic. It does **not yet** establish the meter frame layout or all SysEx command IDs.

Next reverse-engineering stage:

1. resolve the remaining function IDs by following the receive switch/jump table;
2. extract the SysEx dispatcher and payload structures;
3. extract meter framing/channel ordering;
4. replay-test fader/pan/mute/monitor feedback and promote confirmed mappings.

## AutoFonic integration model

```text
L12next -> incoming CC / SysEx / meters -> state cache -> GUI / AI
                                         |
AutoFonic commands ----------------------+
```

AutoFonic should treat the mixer as the source of truth so physical movements, scene changes and transport state remain synchronized.
