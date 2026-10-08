# Native meter reverse engineering

## Resolved SysEx frame

The official decrypted L12next Control app identifies meter updates with:

```text
52 00 00 31 04
```

The complete MIDI SysEx frame is:

```text
F0 52 00 00 31 04 [31-byte payload] F7
```

Breakdown:

```text
F0       SysEx start
52       ZOOM manufacturer ID
00 00    L12next prefix
31       main command family
04       meter subcommand
31 bytes payload
F7       SysEx end
```

Total frame size: **38 bytes**.

The internal app identifier associated with this path is `0x0314`, but that is not the literal wire sequence. The actual command bytes are `31 04`.

Evidence level: **app-derived-strong**.

---

## Payload layout

The 31-byte payload is consumed by the lower-level meter decoder.

| Payload index | Meaning |
|---:|---|
| 0 | fader/meter mode |
| 1..12 | 12 nibble-packed values; high nibble = signal/input-side data, low nibble = companion meter-bank data |
| 13..14 | two EFX/aux values |
| 15..26 | 12 principal track/bridge meter values |
| 27..28 | EFX L/R |
| 29..30 | MASTER L/R |

The decoder repeatedly performs:

```text
value & 0x0F
value >> 4
```

Therefore the on-wire magnitude is **4-bit**, with raw domain `0..15`.

The first payload byte is not audio. It is compared against the internal fader/meter mode and can trigger:

```text
WARNING: discrepancy between meter msg and internal fader mode
```

---

## Channel order

The 12-channel groups are ordered as:

```text
0  CH1
1  CH2
2  CH3
3  CH4
4  CH5
5  CH6
6  CH7
7  CH8
8  CH9/10 L
9  CH9/10 R
10 CH11/12 L
11 CH11/12 R
```

For the principal group:

```text
payload[15] CH1
payload[16] CH2
payload[17] CH3
payload[18] CH4
payload[19] CH5
payload[20] CH6
payload[21] CH7
payload[22] CH8
payload[23] CH9/10 L
payload[24] CH9/10 R
payload[25] CH11/12 L
payload[26] CH11/12 R
payload[27] EFX L
payload[28] EFX R
payload[29] MASTER L
payload[30] MASTER R
```

---

## Internal MeterParams families

The app exposes these decoded meter groups:

| Group | Count |
|---|---:|
| track | 12 |
| track EFX | 2 |
| signal | 12 |
| bridge | 12 |
| bridge EFX | 2 |
| master | 2 |

The higher-level app state stores decoded values as bytes, but the SysEx wire format is nibble-packed.

---

## Rendering

The app contains a dedicated `LEDAudioMeter` UI component and the concepts:

```text
lowerMeterHeight
warnMeterHeight
peakMeterHeight
LedAudioMeter_ON
LedAudioMeter_OFF
```

This proves a segmented LED-style presentation with lower/warning/peak regions.

### Important correction

Earlier notes that described the native wire meter as an **8-step** protocol should not be treated as final. Static analysis of the lower-level SysEx decoder shows that the transmitted meter magnitudes are 4-bit nibble values, i.e. `0..15`.

The UI may remap or group those values visually, but that is a rendering detail and is separate from the wire representation.

---

## dB conversion

The exact mapping:

```text
raw meter nibble 0..15 -> dBFS
```

is **not yet proven** by the app.

Do not derive it from the fader law. The fader control law and the meter quantization law are two different functions.

To recover exact meter dB thresholds, use either:

1. mixer/firmware specification, or
2. controlled tests correlating known input level with nibble transitions.

---

## Separate hardware-measured fader law

A controlled test with tone on CH11/12 and reading on master produced:

| MIDI fader value | Measured level |
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

This table is useful for fader control/reconstruction only. It is not the meter dB scale.

---

## Current confidence

**Resolved:**

- common SysEx framing `F0 52 00 00 ... F7`;
- meter command family `31`;
- meter subcommand `04`;
- payload length 31 bytes;
- total frame length 38 bytes;
- fader/meter mode at payload[0];
- nibble packing;
- CH1..CH12 channel order;
- EFX and master locations.

**Still unresolved:**

- exact meter raw-value-to-dBFS thresholds;
- exact semantic naming of every companion/bridge bank under every fader mode;
- hardware capture confirmation of one full `31 04` frame.
