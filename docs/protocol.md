# ZOOM LiveTrak L12next – protocol reverse engineering

## Evidence levels

- **hardware-confirmed**: replayed or observed on the physical mixer.
- **manual-confirmed**: named in the official ZOOM MIDI implementation.
- **app-derived**: recovered from the decrypted `L12next Control` application.

The dumped Mach-O is decrypted: `LC_ENCRYPTION_INFO_64 cryptid 0`.

## BLE and MIDI transport

Observed BLE GATT characteristic:

```text
7772e5db-3868-4112-a1a9-f2669d106bf3
```

The same MIDI Control Change payloads can also be replayed through the USB ALSA mixer-control port.

## Channel parameters

The decrypted app's `recvCC` table maps incoming CC messages to internal function IDs. Cross-checking that table with the official ZOOM MIDI implementation resolves the channel functions:

| Function ID | CC | Parameter |
|---:|---:|---|
| 1 | 1 / 0x01 | COMP |
| 2 | 3 / 0x03 | USB input select |
| 3 | 8 / 0x08 | Channel selection button |
| 4 | 10 / 0x0A | PHASE |
| 5 | 12 / 0x0C | PAN |
| 6 | 20 / 0x14 | EQ HIGH |
| 7 | 24 / 0x18 | EQ MID FREQ |
| 8 | 26 / 0x1A | EQ MID gain |
| 9 | 28 / 0x1C | EQ MID Q |
| 10 | 44 / 0x2C | EQ LOW |
| 11 | 46 / 0x2E | LOCUT |
| 12 | 48 / 0x30 | MUTE |
| 13 | 50 / 0x32 | SOLO |
| 14 | 52 / 0x34 | SEND EFX |
| 15 | 60 / 0x3C | FADER |
| 16 | 62 / 0x3E | SEND A |
| 17 | 64 / 0x40 | SEND B |
| 18 | 66 / 0x42 | SEND C |
| 19 | 68 / 0x44 | SEND D |
| 20 | 70 / 0x46 | SEND E |
| 71 | 90 / 0x5A | GAIN |
| 78 | 96 / 0x60 | GAIN BOOST |

### Important correction

Earlier analysis incorrectly labeled **function ID 3** as PAN. The official MIDI table shows:

```text
CC 0x08 -> channel selection button -> function 3
CC 0x0C -> PAN                      -> function 5
```

The repository now uses the corrected mapping.

### Fader

Hardware-confirmed:

```text
B0 3C vv  # CH1
B1 3C vv  # CH2
```

CH1 reference values observed:

```text
00 -> -inf
1D -> about -20 dB
35 -> about -10 dB
57 -> about 0 dB
```

## Effects and monitor controls

Resolved from the official MIDI table and the app lookup table:

| Function ID | Parameter |
|---:|---|
| 21 | EFX TYPE |
| 22 | EFX TONE/TIME (MSB/LSB) |
| 23 | EFX DECAY/FEEDBACK (MSB/LSB) |
| 24 | EFX MUTE |
| 25 | EFX SOLO |
| 26 | EFX RETURN FADER |
| 27 | EFX RETURN A |
| 28 | EFX RETURN B |
| 29 | EFX RETURN C |
| 30 | EFX RETURN D |
| 31 | EFX RETURN E |
| 32 | MONITOR VOLUME A-E |

The decrypted table sometimes contains two target IDs for effect-related entries. This likely distinguishes effect targets/engines, but that part is still marked app-derived until hardware-validated.

## Master

| Function ID | CC / MIDI channel | Parameter |
|---:|---|---|
| 33 | 84 / ch10 | MASTER MUTE |
| 34 | 84 / ch11 | MASTER FADER |
| 35 | 84 / ch12 | MASTER COMP |
| 37 | 85 / ch16 | MASTER EQ ON |

Function ID 36 is present at CC84/ch13 but is not named in the public MIDI table. The app UI contains a master clear-solo control, but this association is not yet promoted to confirmed.

## Scene and transport

| Function ID | Meaning |
|---:|---|
| 39 | SCENE SAVE |
| 40 | SCENE RECALL |
| 41 | SCENE SELECT |
| 42 | SCENE RESET |
| 47 | RECORD BUTTON |
| 48 | PLAY |
| 49 | STOP |
| 50 | REW |
| 51 | FAST FORWARD |
| 52 | OVERDUB MODE |
| 70 | SCENE DELETE |

Scene selection bytes:

```text
BB 56 03 -> Scene 1
BC 56 03 -> Scene 2
BD 56 03 -> Scene 3
BE 56 03 -> Scene 4
BF 56 03 -> Scene 5
B0 57 03 -> Scene 6
B1 57 03 -> Scene 7
B2 57 03 -> Scene 8
B3 57 03 -> Scene 9
BC 59 03 -> Scene 10
```

Scene 1 call:

```text
BB 56 03
BA 56 03
```

The obsolete `B7 57 03` scene-1 mapping must not be used.

## Feedback

Incoming state is decoded through the same recovered `recvCC` table.

Hardware-confirmed recorder feedback:

```text
B8 57 05 -> REC active
B8 57 00 -> REC stopped/inactive
```

The app maps `B8 57` to **function ID 46**, so this ID is treated as recorder state feedback.

Recommended AutoFonic synchronization:

```text
B8 57 05 -> AUTOREC ON
B8 57 00 -> AUTOREC OFF
```

The app also contains explicit update/event paths:

```text
TrackParamUpdated
ProjectParamUpdated
MasterParamUpdated
Scene Changed
Meters Changed
```

and diagnostic strings for incoming CC, SysEx and meters.

## Master EQ

The recovered table groups master-EQ messages into semantic fields:

| Function ID | Meaning |
|---:|---|
| 72 | EQ ON |
| 73 | TYPE |
| 74 | FREQ |
| 75 | Q |
| 76 | GAIN |

These fields are distributed across CC 92–94. The official MIDI implementation documents the master-EQ fields; the app table shows additional targets/entries, so exact target indexing still needs validation.

## recvCC table layout

Recovered from the decrypted Mach-O:

- base file offset: `0x7AEA4`
- dimensions: `128 CC × 16 MIDI channels`
- entry size: `12 bytes`

Index:

```text
entry = base + CC * 0xC0 + midi_channel_zero_based * 0x0C
```

Entry layout:

```text
uint32_le target_id
uint32_le function_id
uint32_le aux
```

The table contains **1464 non-zero entries**, **93 distinct CC values**, and function IDs in the range **0..78**.

## Unresolved function IDs

The following IDs are still deliberately unnamed rather than guessed:

```text
0, 36, 38, 43, 44, 45, 53, 54, 55, 56, 57,
58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68,
69, 77
```

Many of these cluster around recorder/scene state and app-only state synchronization.

## Meter path

The app contains dedicated meter handling for:

```text
track meter
track efx meter
bridge meter
bridge efx meter
master meter
signal meter
```

It also checks for discrepancies between meter messages and internal fader mode. The meter packet framing and channel ordering remain the next major reverse-engineering target.

## AutoFonic model

```text
L12next -> CC / state / meters -> AutoFonic state cache -> GUI / AI
                                        |
AutoFonic commands ---------------------+
```

The goal is full bidirectional synchronization rather than blind MIDI writes.
