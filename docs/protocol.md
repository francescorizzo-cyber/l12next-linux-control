# ZOOM LiveTrak L12next – reverse engineered protocol

## Status

This document consolidates the reverse engineering of the ZOOM LiveTrak L12next control protocol from:

- hardware observation/replay;
- official ZOOM MIDI documentation;
- static analysis of the decrypted official `L12next Control` app.

Evidence labels:

- **hardware-confirmed** – observed/replayed on the physical mixer;
- **manual-confirmed** – present in official ZOOM MIDI documentation;
- **app-derived** – recovered from the decrypted app;
- **app-derived-strong** – recovered by direct parser/serializer/control-flow analysis;
- **probable** – strongly suggested but not yet hardware-validated;
- **unresolved** – structure known, exact semantic label still open.

The decrypted Mach-O reports `cryptid 0`.

---

# 1. MIDI Control Change layer

## recvCC table

Recovered table:

```text
file offset : 0x7AEA4
dimensions  : 128 CC × 16 MIDI channels
entry size  : 12 bytes
index       : base + CC*0xC0 + midi_channel_zero_based*0x0C
entry       : target_id:uint32_le, function_id:uint32_le, aux:uint32_le
```

Core function map:

| Function ID | CC | Meaning |
|---:|---:|---|
| 1 | 0x01 | COMP |
| 2 | 0x03 | USB INPUT SELECT |
| 3 | 0x08 | CHANNEL SELECT BUTTON |
| 4 | 0x0A | PHASE |
| 5 | 0x0C | PAN |
| 6 | 0x14 | EQ HIGH |
| 7 | 0x18 | EQ MID FREQ |
| 8 | 0x1A | EQ MID GAIN |
| 9 | 0x1C | EQ MID Q |
| 10 | 0x2C | EQ LOW |
| 11 | 0x2E | LOCUT |
| 12 | 0x30 | MUTE |
| 13 | 0x32 | SOLO |
| 14 | 0x34 | SEND EFX |
| 15 | 0x3C | FADER |
| 16 | 0x3E | SEND A |
| 17 | 0x40 | SEND B |
| 18 | 0x42 | SEND C |
| 19 | 0x44 | SEND D |
| 20 | 0x46 | SEND E |
| 21 | 0x4E | EFX TYPE |
| 22 | 0x4E | EFX TONE/TIME 14-bit pair |
| 23 | 0x4E | EFX DECAY/FEEDBACK 14-bit pair |
| 24 | 0x50 | EFX MUTE |
| 25 | 0x50 | EFX SOLO |
| 26 | 0x50 | EFX RETURN FADER |
| 27..31 | 0x51..0x52 | EFX RETURN A..E |
| 32 | 0x53 | MONITOR VOLUME A..E |
| 34 | 0x54 | MASTER MUTE |
| 35 | 0x54 | MASTER FADER |
| 36 | 0x54 | MASTER COMP |
| 37 | 0x55 | MASTER EQ GLOBAL ON |
| 39 | 0x56 | SCENE SAVE |
| 40 | 0x56 | SCENE RECALL |
| 41 | 0x56/0x57/0x59 | SCENE SELECT |
| 42 | 0x57 | SCENE RESET |
| 46 | 0x57 | RECORD STATE |
| 47 | 0x57 | RECORD BUTTON |
| 48 | 0x57 | PLAY |
| 49 | 0x57 | STOP |
| 50 | 0x57 | REW |
| 51 | 0x57 | FAST FORWARD |
| 52 | 0x57 | OVERDUB |
| 53 | 0x57 | MARK STATUS |
| 54 | 0x58 | MARK NUMBER |
| 58 | 0x59 | SAMPLING RATE |
| 59 | 0x59 | BIT DEPTH |
| 60 | 0x59 | SD CARD ICON |
| 61 | 0x59 | METRONOME ICON |
| 62 | 0x59 | PLAY MODE |
| 63 | 0x59 | PROJECT PROTECT |
| 64 | 0x59 | PREVIOUS PROJECT EXISTS |
| 65 | 0x59 | NEXT PROJECT EXISTS |
| 70 | 0x59 | SCENE DELETE |
| 71 | 0x5A | GAIN |
| 72 | 0x5C..0x5E | MASTER EQ BAND ON |
| 73 | 0x5C..0x5E | MASTER EQ TYPE |
| 74 | 0x5C..0x5E | MASTER EQ FREQ |
| 75 | 0x5C..0x5E | MASTER EQ Q |
| 76 | 0x5C..0x5E | MASTER EQ GAIN |
| 78 | 0x60 | GAIN BOOST |

Important correction: function 3 is CHANNEL SELECT, while PAN is function 5.

---

# 2. Hardware-confirmed commands

## Transport

```text
B9 57 03  RECORD
BA 57 03  PLAY
BB 57 03  STOP
BC 57 03  REW
BD 57 03  FAST FORWARD
BE 57 03  OVERDUB
```

Recorder feedback:

```text
B8 57 05  REC active
B8 57 00  REC inactive/stopped
```

## Scenes

```text
B9 56 03  SAVE
BA 56 03  RECALL
B4 57 03  RESET

BB 56 03  Scene 1
BC 56 03  Scene 2
BD 56 03  Scene 3
BE 56 03  Scene 4
BF 56 03  Scene 5
B0 57 03  Scene 6
B1 57 03  Scene 7
B2 57 03  Scene 8
B3 57 03  Scene 9
BC 59 03  Scene 10
```

## Fader law measured on hardware

Controlled test: tone on CH11/12, reading on master.

| MIDI | dB |
|---:|---:|
| 87 | +0.0 |
| 81 | -1.7 |
| 75 | -3.3 |
| 69 | -5.0 |
| 63 | -6.7 |
| 58 | -8.1 |
| 53 | -9.4 |
| 49 | -11.1 |
| 45 | -13.2 |
| 40 | -15.8 |
| 35 | -18.4 |
| 29 | -23.3 |
| 23 | -30.0 |
| 17 | -36.7 |
| 11 | -49.2 |

This is the fader control law, not the meter scale.

---

# 3. Common SysEx framing

Recovered common framing:

```text
F0 52 00 00 ... F7
```

Known command families:

| Bytes after `52 00 00` | Meaning |
|---|---|
| 01 | Parameters |
| 02 | Parameters In |
| 03 | Parameters14 |
| 06 | Identity |
| 07 | Patch Info |
| 08 | Patch Data Dump |
| 2B | Global Setting Dump |
| 31 xx | realtime/event family |
| 32 | Patch Action |
| 4C | Fader Mode Change |
| 50 | Enter PC Mode |
| 51 | Terminate PC Mode |

---

# 4. Parameters: 01 / 02 / 03

The app uses a 0x48-byte message descriptor whose byte pattern can contain `FF` wildcards.

The generic descriptor is:

```text
FF FF FF
```

meaning one arbitrary 3-byte MIDI message.

## 01 – Parameters

One MIDI CC triple:

```text
F0 52 00 00 01
   Bn CC VV
F7
```

Evidence: app-derived-strong.

## 02 – Parameters In

Incoming triple:

```text
F0 52 00 00 02
   Bn CC VV
F7
```

The handler converts status `B0..BF` to MIDI channel 0..15 and reinjects the record into the normal `recvCC` dispatcher.

## 03 – Parameters14

Two complete MIDI CC triples:

```text
F0 52 00 00 03
   Bn CC MSB
   Bm CC LSB
F7
```

The app reconstructs:

```text
value14 = (MSB << 7) | LSB
```

Confirmed examples:

```text
EFX TONE/TIME
B4 4E MSB
B5 4E LSB

EFX DECAY/FEEDBACK
BC 4E MSB
BD 4E LSB
```

This is a paired-CC 14-bit value, not NRPN.

---

# 5. Realtime/event family 31

Recovered command descriptions:

```text
31 00  Project Name Changed
31 01  Scene Changed
31 02  Channel Name Changed
31 03  Channel Color Changed
31 04  Meters Changed
31 05  Display Time

31 0A  Project Name Change
31 2A  Channel Name Change
31 3A  Channel Color Change
31 5A  Display Locate Time
```

The distinction `Change` vs `Changed` is intentional: request/update and resulting notification are separate protocol commands.

---

# 6. Native meter protocol

Exact frame:

```text
F0 52 00 00 31 04 [31-byte payload] F7
```

Total length: 38 bytes.

The internal ID `0x0314` is not the literal wire sequence `03 14`; the actual command bytes are `31 04`.

## Payload

| Index | Meaning |
|---:|---|
| 0 | fader/meter mode |
| 1..12 | nibble-packed signal + companion bank |
| 13..14 | EFX/aux pair |
| 15..26 | principal 12-channel meter bank |
| 27..28 | EFX L/R |
| 29..30 | MASTER L/R |

Decoder operations:

```text
value & 0x0F
value >> 4
```

Therefore wire meter magnitudes are 4-bit values, nominal range `0..15`.

Principal channel order:

```text
15 CH1
16 CH2
17 CH3
18 CH4
19 CH5
20 CH6
21 CH7
22 CH8
23 CH9/10 L
24 CH9/10 R
25 CH11/12 L
26 CH11/12 R
27 EFX L
28 EFX R
29 MASTER L
30 MASTER R
```

Higher-level meter families:

```text
track        12
track EFX     2
signal       12
bridge       12
bridge EFX    2
master        2
```

The exact `0..15 -> dBFS` threshold table remains unresolved. It must not be inferred from the fader law.

---

# 7. Patch Info – 07

Wire matcher:

```text
F0 52 00 00 07 LL ... F7
```

`LL` identifies a library. The app accepts at least library 0 and 1.

Decoded records contain:

```text
uint16/MIDI-safe patch index
uint8 flag
char[17] patch name
```

The response carries a record count followed by patch metadata records.

---

# 8. Patch Action – 32

Exact logical format:

```text
F0 52 00 00 32
   LL
   ACTION
   INDEX_LOW7
   INDEX_HIGH7
   [optional name data]
F7
```

Index reconstruction:

```text
index = low7 | (high7 << 7)
```

Action mapping recovered from button handlers and serializer:

```text
0 = SAVE
2 = RENAME
4 = DELETE
```

SAVE and RENAME append a 17-byte name field, preceded by the MIDI-safe length:

```text
11 00
[name area, 17 bytes]
```

DELETE does not require the name block.

An internal action value 1 exists in the serializer but its semantic meaning remains unresolved.

---

# 9. Patch Data Dump – 08

Wire family:

```text
F0 52 00 00 08 LL ... F7
```

The common envelope begins with MIDI-safe 14-bit fields:

```text
A        = low7 | high7<<7
LEN      = low7 | high7<<7
blob[LEN]
C        = low7 | high7<<7
```

The exact semantics of A, blob and C remain unresolved; LEN is proven to be the blob length.

## Library 0

Library 0 is the full mixer-scene/state patch family.

Known internal state layout includes:

```text
0x73B3-0x73B4  USB input select, stereo strips
0x73B5-0x740E  channel names, 10 × 9 bytes
0x740F-0x7418  channel colors, 10 bytes
0x7419-0x7422  gain boost
0x7423-0x742C  gain
0x742D-0x7436  compressor
0x7437-0x7440  channel select
0x7441-0x744A  mute
0x744B-0x7454  solo
0x7455-0x745E  phase
0x745F-0x7468  pan
0x7469-0x7472  EQ high
0x7473-0x747C  EQ mid frequency
0x747D-0x7486  EQ mid Q
0x7487-0x7490  EQ mid gain
0x7491-0x749A  EQ low
0x749B-0x74A4  low cut
0x74A5-0x74AE  send EFX

0x74AF-0x74B8  fader
0x74B9-0x74C2  send A
0x74C3-0x74CC  send B
0x74CD-0x74D6  send C
0x74D7-0x74E0  send D
0x74E1-0x74EA  send E

0x74EB          EFX type
0x74EC-0x74ED   EFX 14-bit parameter 1
0x74EE-0x74EF   EFX 14-bit parameter 2
0x74F0-0x74F1   EFX 14-bit parameter 3 / app-private EFX field
0x74F2          EFX mute
0x74F3          EFX solo
0x74F4          EFX return fader
0x74F5          EFX return A
0x74F6          EFX return B
0x74F7          EFX return C
0x74F8          EFX return D
0x74F9          EFX return E

0x74FA          master mute
0x74FB          master comp
0x74FC          master fader
```

Channel SELECT and SOLO are operational state and should not automatically be assumed to be persistent scene content just because they exist in the shared state memory.

## Library 1

Library 1 is the compact EFX patch family:

```text
EFX type
EFX parameter 1, 14-bit
EFX parameter 2, 14-bit
```

---

# 10. Global Setting Dump – 2B

The parser accepts exactly:

```text
0x1AD = 429 bytes
```

and copies them directly into internal state:

```text
0x73B3 ... 0x755F
```

Thus the global dump is an extensive full-state snapshot.

Related command:

```text
2B 0A  Global Setting Dump Listener
```

The listener preserves Monitor A-E while applying the rest of the snapshot.

## Tail of the 429-byte state block

```text
0x74FD  Monitor A
0x74FE  Monitor B
0x74FF  Monitor C
0x7500  Monitor D
0x7501  Monitor E

0x7502  MASTER EQ GLOBAL ON

0x7503-0x752A  MASTER EQ, 8 targets × 5 fields
                  +0 ON
                  +1 TYPE
                  +2 FREQ
                  +3 Q
                  +4 GAIN

0x752B-0x7534  SceneState[10]

0x7535  SCENE RESET state/control
0x7536  SCENE SAVE state/control
0x7537  SCENE RECALL state/control
0x7538  SCENE DELETE state/control

0x7539-0x755F  Project / Recorder State
```

This closes the previously anonymous 5 bytes in the global tail.

---

# 11. Scene-state enum

Swift metadata exposes:

```text
SceneDetailTableViewCellState
  off
  on
  blink
```

Layout/discriminator order:

```text
0 = off
1 = on
2 = blink
```

The GUI explicitly routes state 2 through the scene-cell blinker.

The protocol/state array also contains value 3. It is handled outside the normal 3-case UI enum and behaves like an unavailable/empty/special slot state.

Therefore:

```text
0 = OFF
1 = ON
2 = BLINK
3 = SPECIAL / EMPTY-LIKE   (probable semantic label)
```

`selected` is a separate cell property and is not one of these enum cases.

---

# 12. Project / recorder state

Snapshot base:

```text
0x7539
size 39 bytes
```

Recovered fields:

| Offset | Field |
|---:|---|
| +0 | recorderStatus |
| +1 | overdub |
| +2 | markStatus |
| +3 | markNumber |
| +17 | samplingRate |
| +18 | bitDepth |
| +19 | sdCardIcon |
| +20 | metronomeIcon |
| +21 | playmode |
| +22 | projectProtect |
| +37 | previousExists |
| +38 | nextExists |

Reflection strings expose recorder states:

```text
stop
play
pause
recStandBy
recPause
recPlay
```

Mark states:

```text
atMark
notAtMark
```

Play modes:

```text
playOne
playAll
repeatOne
repeatAll
```

Exact numeric raw values for every recorder/project enum case are not yet fully proven, so names are documented without inventing a raw-value map.

---

# 13. Other recovered SysEx commands

```text
06     Identity
4C     Fader Mode Change
50     Enter PC Mode
51     Terminate PC Mode
```

Their existence and command IDs are app-derived. Payload semantics are not yet all decoded.

---

# 14. Remaining unresolved pieces

The control protocol is now largely reconstructed. Remaining uncertainty is limited to:

1. exact meter nibble `0..15 -> dBFS` thresholds;
2. exact semantic name of the third EFX 14-bit field at `0x74F0-0x74F1`;
3. exact meaning of Patch Data Dump envelope fields `A`, variable blob, and `C`;
4. semantic meaning of internal Patch Action code 1;
5. exact numeric raw-value maps for all recorder/project enums;
6. exact payload semantics for Identity and Fader Mode Change;
7. hardware capture validation of at least one complete `31 04` meter frame and one `2B` global dump.

Everything else above is either hardware-confirmed, manual-confirmed, or statically recovered from the official application with explicit confidence labels.
