# ZOOM LiveTrak L12next – protocol reverse engineering

## Status

Static reverse engineering of the official decrypted `L12next Control` app is complete to the point supported by the binary. Remaining unknown labels are fields whose values are parsed/stored but whose semantic names are not exposed by the application. Hardware validation is still useful for meter dB thresholds and complete live captures.

Evidence labels:

- **hardware-confirmed** – observed/replayed on the physical mixer;
- **manual-confirmed** – confirmed by ZOOM documentation;
- **app-derived-strong** – directly recovered from parser/serializer/control flow;
- **opaque** – wire/storage format is known but the app does not expose a reliable semantic label.

---

# 1. MIDI CC layer

Incoming lookup table:

```text
file offset : 0x7AEA4
dimensions  : 128 CC × 16 MIDI channels
entry size  : 12 bytes
entry       : target_id:uint32_le, function_id:uint32_le, aux:uint32_le
index       : base + CC*0xC0 + channel_zero_based*0x0C
```

Core function IDs:

| ID | Meaning |
|---:|---|
| 1 | COMP |
| 2 | USB INPUT SELECT |
| 3 | CHANNEL SELECT |
| 4 | PHASE |
| 5 | PAN |
| 6 | EQ HIGH |
| 7 | EQ MID FREQ |
| 8 | EQ MID GAIN |
| 9 | EQ MID Q |
| 10 | EQ LOW |
| 11 | LOCUT |
| 12 | MUTE |
| 13 | SOLO |
| 14 | SEND EFX |
| 15 | FADER |
| 16..20 | SEND A..E |
| 21 | EFX TYPE |
| 22 | EFX TONE/TIME |
| 23 | EFX DECAY/FEEDBACK |
| 24 | EFX MUTE |
| 25 | EFX SOLO |
| 26 | EFX RETURN FADER |
| 27..31 | EFX RETURN A..E |
| 32 | MONITOR VOLUME A..E |
| 34 | MASTER MUTE |
| 35 | MASTER FADER |
| 36 | MASTER COMP |
| 37 | MASTER EQ GLOBAL ON |
| 39 | SCENE SAVE |
| 40 | SCENE RECALL |
| 41 | SCENE SELECT |
| 42 | SCENE RESET |
| 46 | RECORD STATE |
| 47 | RECORD BUTTON |
| 48 | PLAY |
| 49 | STOP |
| 50 | REW |
| 51 | FAST FORWARD |
| 52 | OVERDUB |
| 53 | MARK STATUS |
| 54 | MARK NUMBER |
| 58 | SAMPLING RATE |
| 59 | BIT DEPTH |
| 60 | SD CARD ICON |
| 61 | METRONOME ICON |
| 62 | PLAY MODE |
| 63 | PROJECT PROTECT |
| 64 | PREVIOUS PROJECT EXISTS |
| 65 | NEXT PROJECT EXISTS |
| 70 | SCENE DELETE |
| 71 | GAIN |
| 72..76 | MASTER EQ band fields |
| 77 | EFX auxiliary 14-bit pair at 0x74F0/0x74F1 |
| 78 | GAIN BOOST |

---

# 2. Hardware-confirmed commands

```text
B9 57 03  RECORD
BA 57 03  PLAY
BB 57 03  STOP
BC 57 03  REW
BD 57 03  FAST FORWARD
BE 57 03  OVERDUB

B8 57 05  recording active feedback
B8 57 00  recording stopped/inactive feedback
```

Scenes:

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

Measured fader law:

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

This is the fader law, not the meter scale.

---

# 3. SysEx framing

Common framing:

```text
F0 52 00 00 ... F7
```

Known command families:

```text
01      Parameters
02      Parameters In
03      Parameters14
06      Identity
07      Patch Info
08      Patch Data Dump
2B      Global Setting Dump
31 xx   realtime/event family
32      Patch Action
4C      Fader Mode Change
50      Enter PC Mode
51      Terminate PC Mode
```

---

# 4. Session / identity

## Enter PC Mode

No payload:

```text
F0 52 00 00 50 F7
```

## Terminate PC Mode

No payload:

```text
F0 52 00 00 51 F7
```

## Identity – 06

Request has no payload:

```text
F0 52 00 00 06 F7
```

The app response parser reads exactly four bytes and logs them as:

```text
Firmware version: %s
```

Logical response:

```text
F0 52 00 00 06 [4-byte firmware version] F7
```

---

# 5. Parameters 01 / 02 / 03

## 01 Parameters

```text
F0 52 00 00 01 Bn CC VV F7
```

## 02 Parameters In

```text
F0 52 00 00 02 Bn CC VV F7
```

The incoming triple is reinjected into the normal recvCC dispatcher.

## 03 Parameters14

```text
F0 52 00 00 03
   Bn CC MSB
   Bm CC LSB
F7
```

```text
value14 = (MSB << 7) | LSB
```

Known pairs:

```text
EFX TONE/TIME       B4 4E MSB + B5 4E LSB
EFX DECAY/FEEDBACK  BC 4E MSB + BD 4E LSB
```

---

# 6. Realtime family 31

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

---

# 7. Native meters – 31 04

Exact frame:

```text
F0 52 00 00 31 04 [31-byte payload] F7
```

Total frame length: 38 bytes.

Payload:

```text
[0]      fader/meter mode
[1..12]  nibble-packed signal + companion bank
[13..14] EFX/aux
[15..26] principal 12-channel bank
[27..28] EFX L/R
[29..30] MASTER L/R
```

Decoder:

```text
low  = byte & 0x0F
high = byte >> 4
```

Principal order:

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

The wire domain is 4-bit, `0..15`. The app renders an 8-segment LED meter, but the exact nibble-to-dBFS thresholds are not encoded in the UI renderer and remain a hardware-measurement item.

---

# 8. Fader Mode Change – 4C

Exact wire format:

```text
F0 52 00 00 4C MODE F7
```

Swift `FaderMode` discriminator order:

```text
0 master
1 monitorA
2 monitorB
3 monitorC
4 monitorD
5 monitorE
6 monitorF
```

---

# 9. Patch Info – 07

Requests:

```text
F0 52 00 00 07 00 F7   scene library
F0 52 00 00 07 01 F7   EFX1 library
```

`LibraryType`:

```text
0 scene
1 efx1
```

Response body:

```text
COUNT:uint14
repeat COUNT times:
    INDEX:uint14
    FLAG:uint8
    NAME:17 bytes
```

Each record therefore consumes 20 bytes.

---

# 10. Patch Action – 32

```text
F0 52 00 00 32
   LIBRARY
   ACTION
   INDEX_LOW7
   INDEX_HIGH7
   [optional name]
F7
```

```text
index = low7 | (high7 << 7)
```

Action mapping:

```text
0 SAVE
1 SELECT
2 RENAME
4 DELETE
```

`SELECT` is now identified from Swift `LibraryActionType` metadata (`save, select, rename, delete`) and the serializer paths.

SAVE/RENAME append:

```text
11 00           length = 17
[17-byte name]
```

---

# 11. Patch Data Dump – 08

General frame family:

```text
F0 52 00 00 08 LIBRARY ... F7
```

The parser consumes this exact common envelope:

```text
A:uint14
LEN:uint14
BLOB:LEN bytes
C:uint14
DATA...
```

`LEN` is definitely the blob length. `A`, `BLOB`, and `C` are consumed but discarded by the app's patch-data handler; their wire structure is known, but the binary does not expose trustworthy semantic names. They are therefore intentionally documented as opaque metadata.

## Library 0 – scene

The persistent scene payload is exactly **310 bytes**.

Important: CHANNEL SELECT and SOLO exist in shared runtime state but are **not included** in the scene dump.

Persistent scene layout:

```text
2    USB input select
90   channel names (10 × 9)
10   channel colors
10   gain boost
10   gain
10   compressor
10   mute
10   phase
10   pan
10   EQ high
10   EQ mid frequency
10   EQ mid Q
10   EQ mid gain
10   EQ low
10   low cut
10   send EFX
60   fader + send A/B/C/D/E
1    EFX type
4    EFX parameter 1 + parameter 2, two 14-bit pairs stored as 7+7
2    EFX auxiliary 14-bit pair (0x74F0/0x74F1)
1    EFX mute
1    EFX solo
6    EFX return fader + A/B/C/D/E
3    master mute + master comp + master fader
-------------------------------------------
310 bytes
```

## Library 1 – efx1

```text
EFX type:uint8
EFX parameter 1:uint14
EFX parameter 2:uint14
```

---

# 12. Global Setting Dump – 2B

Request:

```text
F0 52 00 00 2B F7
```

Response/parser format:

```text
F0 52 00 00 2B
   2D 03          # uint14 length = 429
   [429 bytes]
F7
```

```text
429 decimal = 0x1AD
uint14 = low7 | (high7 << 7)
=> 0x2D 0x03
```

The 429-byte snapshot maps to runtime state:

```text
0x73B3 ... 0x755F
```

Listener variant:

```text
2B 0A
```

It applies the same global snapshot while preserving Monitor A-E.

---

# 13. Shared runtime state map

```text
0x73B3-0x73B4  USB input select
0x73B5-0x740E  channel names (10×9)
0x740F-0x7418  channel colors
0x7419-0x7422  gain boost
0x7423-0x742C  gain
0x742D-0x7436  compressor
0x7437-0x7440  channel select       [runtime only]
0x7441-0x744A  mute
0x744B-0x7454  solo                 [runtime only]
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
0x74EC-0x74ED   EFX parameter 1 (14-bit)
0x74EE-0x74EF   EFX parameter 2 (14-bit)
0x74F0-0x74F1   EFX auxiliary field (14-bit; semantic label opaque)
0x74F2          EFX mute
0x74F3          EFX solo
0x74F4          EFX return fader
0x74F5-0x74F9   EFX return A-E
0x74FA          master mute
0x74FB          master comp
0x74FC          master fader
0x74FD-0x7501   Monitor A-E
0x7502          MASTER EQ GLOBAL ON
0x7503-0x752A   MASTER EQ: 8 targets × 5 fields
0x752B-0x7534   SceneState[10]
0x7535          Scene Reset state/control
0x7536          Scene Save state/control
0x7537          Scene Recall state/control
0x7538          Scene Delete state/control
0x7539-0x755F   Project/Recorder state (39 bytes)
```

Master EQ per target:

```text
+0 ON
+1 TYPE
+2 FREQ
+3 Q
+4 GAIN
```

---

# 14. Scene state

Swift UI enum:

```text
SceneDetailTableViewCellState
0 off
1 on
2 blink
```

The protocol/runtime state also uses value 3, handled outside the 3-case UI enum as a special/unavailable/empty-like state.

`selected` is a separate UI property.

---

# 15. Project / recorder state

Base:

```text
0x7539
size = 39 bytes
```

Known fields:

```text
+0  recorderStatus
+1  overdub
+2  markStatus
+3  markNumber
+17 samplingRate
+18 bitDepth
+19 sdCardIcon
+20 metronomeIcon
+21 playmode
+22 projectProtect
+37 previousExists
+38 nextExists
```

Swift enum discriminator order recovered from reflection metadata:

RecorderStatus:

```text
0 stop
1 play
2 pause
3 recStandBy
4 recPause
5 recPlay
```

MarkStatus:

```text
0 hide
1 atMark
2 notAtMark
```

PlayMode:

```text
0 off
1 playOne
2 playAll
3 repeatOne
4 repeatAll
```

---

# 16. What is still hardware-only

Static reverse engineering is now complete. The remaining items are not missing parser mechanics; they require observation of the physical mixer or firmware-level analysis:

1. exact meter nibble `0..15 -> dBFS` thresholds;
2. hardware confirmation of one complete `31 04` meter frame;
3. hardware confirmation of a complete `2B` global dump;
4. human-readable semantic label for the app-private 14-bit field at `0x74F0/0x74F1`;
5. human-readable labels for opaque Patch Data Dump envelope metadata `A/BLOB/C`.

The wire/storage format of items 4 and 5 is already known; only their semantic names remain opaque in this app build.
