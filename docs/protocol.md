# ZOOM LiveTrak L12next – Final reverse-engineered protocol

## Status

Static reverse engineering of the decrypted official `L12next Control` app is complete to the point supported by the binary.

Remaining items are hardware-validation or semantic-label questions, not missing parser mechanics:
- exact meter nibble `0..15 -> dBFS` thresholds;
- live capture validation of one complete `31 04` meter frame;
- live capture validation of one complete `2B` global dump;
- human-readable label for the app-private 14-bit field at `0x74F0/0x74F1`;
- human-readable labels for opaque Patch Data Dump envelope fields `A/BLOB/C`.

## Common SysEx framing

```text
F0 52 00 00 ... F7
```

Known command families:

```text
01 Parameters
02 Parameters In
03 Parameters14
06 Identity
07 Patch Info
08 Patch Data Dump
2B Global Setting Dump
31 xx realtime/event family
32 Patch Action
4C Fader Mode Change
50 Enter PC Mode
51 Terminate PC Mode
```

## Session and identity

```text
F0 52 00 00 50 F7
```
Enter PC Mode, no payload.

```text
F0 52 00 00 51 F7
```
Terminate PC Mode, no payload.

Identity request:

```text
F0 52 00 00 06 F7
```

Identity response:

```text
F0 52 00 00 06 [4-byte firmware version] F7
```

The app reads exactly four bytes and logs them as `Firmware version: %s`.

## Parameters

```text
F0 52 00 00 01 Bn CC VV F7
F0 52 00 00 02 Bn CC VV F7
```

For `03 Parameters14`:

```text
F0 52 00 00 03 [Bn CC MSB] [Bm CC LSB] F7
value14 = (MSB << 7) | LSB
```

Known pairs:

```text
EFX TONE/TIME       B4 4E MSB + B5 4E LSB
EFX DECAY/FEEDBACK  BC 4E MSB + BD 4E LSB
```

## Realtime events

```text
31 00 Project Name Changed
31 01 Scene Changed
31 02 Channel Name Changed
31 03 Channel Color Changed
31 04 Meters Changed
31 05 Display Time

31 0A Project Name Change
31 2A Channel Name Change
31 3A Channel Color Change
31 5A Display Locate Time
```

## Native meters

Exact frame:

```text
F0 52 00 00 31 04 [31-byte payload] F7
```

Total length: 38 bytes.

Payload:

```text
0       fader/meter mode
1..12   nibble-packed signal + companion bank
13..14  EFX/aux
15..26  principal 12-channel bank
27..28  EFX L/R
29..30  MASTER L/R
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

Wire domain is `0..15`. UI meter is 8-segment. Exact dBFS thresholds require hardware measurement.

## Fader Mode Change

```text
F0 52 00 00 4C MODE F7
```

`FaderMode` discriminator order:

```text
0 master
1 monitorA
2 monitorB
3 monitorC
4 monitorD
5 monitorE
6 monitorF
```

## Patch Info

Requests:

```text
F0 52 00 00 07 00 F7  scene
F0 52 00 00 07 01 F7  efx1
```

`LibraryType`:

```text
0 scene
1 efx1
```

Response body:

```text
COUNT:uint14
repeat COUNT:
  INDEX:uint14
  FLAG:uint8
  NAME:17 bytes
```

Each record is 20 bytes.

## Patch Action

```text
F0 52 00 00 32 LIBRARY ACTION INDEX_LOW7 INDEX_HIGH7 [optional name] F7
```

Index:

```text
index = low7 | (high7 << 7)
```

Wire action mapping:

```text
0 SAVE
1 SELECT
2 RENAME
4 DELETE
```

SAVE and RENAME append:

```text
11 00
[17-byte name]
```

## Patch Data Dump

Family:

```text
F0 52 00 00 08 LIBRARY ... F7
```

Common envelope:

```text
A:uint14
LEN:uint14
BLOB:LEN bytes
C:uint14
DATA...
```

`LEN` is proven. `A`, `BLOB`, and `C` are parsed then discarded by the app handler, so their semantic names remain opaque.

### Library 0: scene

Persistent scene data = exactly **310 bytes**.

`CHANNEL SELECT` and `SOLO` are runtime state but are deliberately omitted from the scene dump.

```text
2   USB input select
90  channel names (10 × 9)
10  channel colors
10  gain boost
10  gain
10  compressor
10  mute
10  phase
10  pan
10  EQ high
10  EQ mid frequency
10  EQ mid Q
10  EQ mid gain
10  EQ low
10  low cut
10  send EFX
60  fader + send A/B/C/D/E
1   EFX type
4   EFX params 1 and 2 as two 14-bit pairs
2   EFX auxiliary 14-bit field
1   EFX mute
1   EFX solo
6   EFX return fader + A/B/C/D/E
3   master mute + master comp + master fader
= 310 bytes
```

### Library 1: efx1

```text
EFX type:uint8
EFX parameter 1:uint14
EFX parameter 2:uint14
```

## Global Setting Dump

Request:

```text
F0 52 00 00 2B F7
```

Response:

```text
F0 52 00 00 2B 2D 03 [429 bytes] F7
```

`2D 03` is MIDI-safe uint14(429):

```text
value = low7 | (high7 << 7)
```

Listener command:

```text
2B 0A
```

The listener preserves Monitor A-E while applying the global state.

## recvCC table

```text
file offset : 0x7AEA4
128 CC × 16 channels
entry size  : 12 bytes
entry       : target_id:uint32_le, function_id:uint32_le, aux:uint32_le
index       : base + cc*0xC0 + channel*0x0C
```

Core function mapping:

```text
1 COMP
2 USB_INPUT_SELECT
3 CHANNEL_SELECT
4 PHASE
5 PAN
6 EQ_HIGH
7 EQ_MID_FREQ
8 EQ_MID_GAIN
9 EQ_MID_Q
10 EQ_LOW
11 LOCUT
12 MUTE
13 SOLO
14 SEND_EFX
15 FADER
16..20 SEND_A..E
21 EFX_TYPE
22 EFX_TONE_TIME
23 EFX_DECAY_FEEDBACK
24 EFX_MUTE
25 EFX_SOLO
26 EFX_RETURN_FADER
27..31 EFX_RETURN_A..E
32 MONITOR_VOLUME_A_E
34 MASTER_MUTE
35 MASTER_FADER
36 MASTER_COMP
37 MASTER_EQ_GLOBAL_ON
39 SCENE_SAVE
40 SCENE_RECALL
41 SCENE_SELECT
42 SCENE_RESET
46 RECORD_STATE
47 RECORD_BUTTON
48 PLAY
49 STOP
50 REW
51 FAST_FORWARD
52 OVERDUB
53 MARK_STATUS
54 MARK_NUMBER
58 SAMPLING_RATE
59 BIT_DEPTH
60 SD_CARD_ICON
61 METRONOME_ICON
62 PLAY_MODE
63 PROJECT_PROTECT
64 PREVIOUS_PROJECT_EXISTS
65 NEXT_PROJECT_EXISTS
70 SCENE_DELETE
71 GAIN
72..76 MASTER_EQ fields
77 EFX auxiliary 14-bit pair at 0x74F0/0x74F1
78 GAIN_BOOST
```

## Runtime state map

```text
0x73B3-0x73B4 USB input select
0x73B5-0x740E channel names (10×9)
0x740F-0x7418 channel colors
0x7419-0x7422 gain boost
0x7423-0x742C gain
0x742D-0x7436 compressor
0x7437-0x7440 channel select [runtime only]
0x7441-0x744A mute
0x744B-0x7454 solo [runtime only]
0x7455-0x745E phase
0x745F-0x7468 pan
0x7469-0x7472 EQ high
0x7473-0x747C EQ mid frequency
0x747D-0x7486 EQ mid Q
0x7487-0x7490 EQ mid gain
0x7491-0x749A EQ low
0x749B-0x74A4 low cut
0x74A5-0x74AE send EFX
0x74AF-0x74B8 fader
0x74B9-0x74EA send A-E
0x74EB EFX type
0x74EC-0x74ED EFX parameter 1 (14-bit)
0x74EE-0x74EF EFX parameter 2 (14-bit)
0x74F0-0x74F1 EFX auxiliary field (14-bit, semantic opaque)
0x74F2 EFX mute
0x74F3 EFX solo
0x74F4-0x74F9 EFX return fader + A-E
0x74FA master mute
0x74FB master comp
0x74FC master fader
0x74FD-0x7501 Monitor A-E
0x7502 MASTER EQ GLOBAL ON
0x7503-0x752A MASTER EQ 8×5
0x752B-0x7534 SceneState[10]
0x7535 Scene Reset
0x7536 Scene Save
0x7537 Scene Recall
0x7538 Scene Delete
0x7539-0x755F Project/Recorder state
```

## Enums

Scene cell state:

```text
0 off
1 on
2 blink
3 special/empty-like protocol state outside UI enum
```

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

## Hardware-confirmed CCs

```text
B9 57 03 RECORD
BA 57 03 PLAY
BB 57 03 STOP
BC 57 03 REW
BD 57 03 FAST FORWARD
BE 57 03 OVERDUB

B8 57 05 REC active feedback
B8 57 00 REC stopped feedback

B9 56 03 Scene SAVE
BA 56 03 Scene RECALL
B4 57 03 Scene RESET
```

Scene selectors:

```text
1 BB 56 03
2 BC 56 03
3 BD 56 03
4 BE 56 03
5 BF 56 03
6 B0 57 03
7 B1 57 03
8 B2 57 03
9 B3 57 03
10 BC 59 03
```

## Measured fader law

```text
87 +0.0 dB
81 -1.7
75 -3.3
69 -5.0
63 -6.7
58 -8.1
53 -9.4
49 -11.1
45 -13.2
40 -15.8
35 -18.4
29 -23.3
23 -30.0
17 -36.7
11 -49.2
```
