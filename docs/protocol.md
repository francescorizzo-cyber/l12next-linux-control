# ZOOM LiveTrak L12next – protocol reverse engineering

## Scope

This document consolidates the currently recovered control protocol for the ZOOM LiveTrak L12next from:

- hardware replay/observation on the physical mixer;
- the official ZOOM MIDI implementation;
- static analysis of the decrypted official `L12next Control` app.

Evidence labels:

- **hardware-confirmed**: observed or replayed on the mixer;
- **manual-confirmed**: present in official ZOOM MIDI documentation;
- **app-derived**: recovered from the decrypted app;
- **app-derived-strong**: recovered by following the parser/handler data flow;
- **unresolved**: structure exists but meaning is not yet proven.

The decrypted Mach-O reports `cryptid 0`. Comparison with the encrypted App Store binary showed the same executable size, with changes confined to the DRM/decrypted code page and the expected `cryptid 1 -> 0` change.

---

## MIDI Control Change map

The app contains a `recvCC` lookup table at file offset `0x7AEA4`.

```text
dimensions : 128 CC × 16 MIDI channels
entry size : 12 bytes
index      : base + CC * 0xC0 + midi_channel_zero_based * 0x0C
layout     : target_id:uint32_le, function_id:uint32_le, aux:uint32_le
```

Important corrected mappings:

| Function | CC | Meaning |
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
| 71 | 0x5A | GAIN |
| 78 | 0x60 | GAIN BOOST |

Earlier analysis that mapped function ID 3 to PAN was wrong. The corrected mapping is:

```text
CC 0x08 -> CHANNEL SELECT BUTTON -> function 3
CC 0x0C -> PAN                   -> function 5
```

---

## Fader

Hardware-confirmed family:

```text
Bn 3C vv
```

Examples:

```text
B0 3C vv -> CH1
B1 3C vv -> CH2
```

### Measured fader law

Controlled test: tone on CH11/12, level read on master. The following MIDI fader values were measured on the physical mixer:

| MIDI value | Measured level |
|---:|---:|
| 87 | +0.0 dB |
| 81 | -1.7 dB |
| 75 | -3.3 dB |
| 69 | -5.0 dB |
| 63 | -6.7 dB |
| 58 | -8.1 dB |
| 53 | -9.4 dB |
| 49 | -11.1 dB |
| 45 | -13.2 dB |
| 40 | -15.8 dB |
| 35 | -18.4 dB |
| 29 | -23.3 dB |
| 23 | -30.0 dB |
| 17 | -36.7 dB |
| 11 | -49.2 dB |

This is a **hardware-measured fader law**. It must not be confused with the meter scale discussed below.

---

## Effects, monitor and master

Effect/monitor function IDs:

```text
21 EFX TYPE
22 EFX TONE/TIME
23 EFX DECAY/FEEDBACK
24 EFX MUTE
25 EFX SOLO
26 EFX RETURN FADER
27 EFX RETURN A
28 EFX RETURN B
29 EFX RETURN C
30 EFX RETURN D
31 EFX RETURN E
32 MONITOR VOLUME A-E
```

Master-related mappings:

```text
B8 54 -> function 33, app-only/unknown master-related entry
B9 54 -> MASTER MUTE, function 34
BA 54 -> MASTER FADER, function 35
BB 54 -> MASTER COMP, function 36
BF 55 -> MASTER EQ ON, function 37
```

Master EQ fields use function IDs 72..76 for ON, TYPE, FREQ, Q and GAIN.

---

## Scenes and transport

```text
B9 56 03 -> SCENE SAVE
BA 56 03 -> SCENE RECALL
B4 57 03 -> SCENE RESET

B9 57 03 -> RECORD
BA 57 03 -> PLAY
BB 57 03 -> STOP
BC 57 03 -> REW
BD 57 03 -> FAST FORWARD
BE 57 03 -> OVERDUB MODE
```

Scene selection:

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

The obsolete `B7 57 03` Scene-1 mapping must not be used.

Hardware-confirmed recorder feedback:

```text
B8 57 05 -> REC active
B8 57 00 -> REC stopped/inactive
```

---

# SysEx framing

The official app removes `F0` and `F7` before matching command descriptions. The common framing recovered from the app is:

```text
F0 52 00 00 ... F7
```

Known signatures include:

```text
52 00 00 50 -> Enter PC Mode
52 00 00 51 -> Terminate PC Mode
52 00 00 2A / 2B -> Global Setting Dump family
```

---

# Native meter SysEx

## Exact header and command

Following the command description that reaches the application's **Meters Changed** handler gives:

```text
52 00 00 31 04
```

Therefore the full meter frame is:

```text
F0 52 00 00 31 04 [31-byte payload] F7
```

Interpretation:

```text
F0       SysEx start
52       ZOOM manufacturer ID
00 00    L12next prefix used by the app
31       main meter/state command family
04       meter subcommand
payload  31 bytes
F7       SysEx end
```

Total frame length: **38 bytes**.

The internal app identifier `0x0314` must not be read as literal wire bytes `03 14`; the actual command bytes are `31 04`.

Evidence: **app-derived-strong**.

---

## Meter payload

The lower-level decoder associated with `31 04` consumes 31 payload bytes.

| Payload index | Meaning |
|---:|---|
| 0 | fader/meter mode |
| 1..12 | 12 nibble-packed values: high nibble = signal/input-side meter data; low nibble = companion meter bank |
| 13..14 | two EFX/aux meter values |
| 15..26 | 12 principal track/bridge meter values |
| 27..28 | two EFX meter values |
| 29..30 | MASTER L / MASTER R |

The decoder repeatedly applies:

```text
value & 0x0F
value >> 4
```

so the on-wire meter values are packed in **4-bit nibbles**, nominal raw domain **0..15**.

Payload byte 0 is compared with the app's internal fader/meter mode. A mismatch triggers:

```text
WARNING: discrepancy between meter msg and internal fader mode
```

Therefore payload[0] is state/mode, not an audio level.

---

## Channel ordering

The app exposes six meter families:

```text
track       12
track EFX    2
signal      12
bridge      12
bridge EFX   2
master       2
```

The 12-channel groups map as:

```text
0  -> CH1
1  -> CH2
2  -> CH3
3  -> CH4
4  -> CH5
5  -> CH6
6  -> CH7
7  -> CH8
8  -> CH9/10 L
9  -> CH9/10 R
10 -> CH11/12 L
11 -> CH11/12 R
```

For the principal group:

```text
payload[15] -> CH1
payload[16] -> CH2
payload[17] -> CH3
payload[18] -> CH4
payload[19] -> CH5
payload[20] -> CH6
payload[21] -> CH7
payload[22] -> CH8
payload[23] -> CH9/10 L
payload[24] -> CH9/10 R
payload[25] -> CH11/12 L
payload[26] -> CH11/12 R
payload[27] -> EFX L
payload[28] -> EFX R
payload[29] -> MASTER L
payload[30] -> MASTER R
```

The app's higher-level `MeterParams` representation stores the decoded values as bytes, but the actual SysEx transport is nibble-packed.

---

## Meter scale and UI rendering

The protocol recovery proves the on-wire magnitude is a nibble value, **0..15**. The app then transforms decoded meter state for its LED-style UI.

The app contains a dedicated `LEDAudioMeter` view and the concepts:

```text
lowerMeterHeight
warnMeterHeight
peakMeterHeight
LedAudioMeter_ON
LedAudioMeter_OFF
```

What is proven:

- the SysEx meter magnitude is nibble encoded;
- the app renders a segmented LED meter;
- the app distinguishes lower/warning/peak regions.

What is **not yet proven**:

- the exact dBFS threshold corresponding to each raw meter value 0..15;
- the exact warning/peak dB boundaries;
- whether mixer firmware uses equal-dB steps or a nonlinear lookup.

Do not reuse the fader-law table as a meter-law table: they are different quantities.

---

## Project-state receive path

The receive dispatcher starts around `0x10001893C`, with a 16-bit jump table around `0x100074D24`.

Recovered fields include:

```text
recorderStatus  function 46
overdub         function 52
markStatus      function 53
markNumber      function 54
samplingRate    function 58
bitDepth        function 59
sdCardIcon      function 60
metronomeIcon   function 61
playmode        function 62
projectProtect  function 63
previousExists  function 64
nextExists      function 65
```

The app also contains explicit update strings:

```text
TrackParamUpdated
ProjectParamUpdated
MasterParamUpdated
Scene Changed
Meters Changed
```

and diagnostics:

```text
ERROR: invalid indexes for recvCC lookup table!
WARNING: received unhandled CC
Undefined sysEx MIDI message processing cmd
WARNING: discrepancy between meter msg and internal fader mode
```

---

## Current remaining reverse targets

1. Recover exact raw meter `0..15 -> dBFS` thresholds.
2. Fully name the remaining app-private/unhandled function IDs.
3. Validate the meter frame on hardware with a captured `31 04` message.
4. Correlate controlled known input levels with meter nibble transitions.

The protocol is now sufficiently understood to distinguish clearly between:

```text
fader control law  -> MIDI CC value -> gain in dB
meter transport    -> SysEx 31 04 -> nibble level 0..15
```

These are separate mappings and must remain separate in implementations and documentation.
