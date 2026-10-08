# Native meter reverse engineering

## Meter handler

The decrypted app processes meter updates in the routine at approximately:

```text
0x100038368
```

The function receives a `MeterParams`-style structure made from pointer/length pairs.

## MeterParams layout

| Struct offset | Group | Required size |
|---:|---|---:|
| 0x00 | track | 12 bytes |
| 0x10 | track EFX | 2 bytes |
| 0x20 | signal | 12 bytes |
| 0x30 | bridge | 12 bytes |
| 0x40 | bridge EFX | 2 bytes |
| 0x50 | master | 2 bytes |
| 0x60 | auxiliary group 6 | dynamic |
| 0x70 | auxiliary group 7 | dynamic |

The app has explicit size checks with these diagnostics:

```text
WARNING: Incorrect track meter values size!
WARNING: Incorrect track efx meter values size!
WARNING: Incorrect bridge meter values size!
WARNING: Incorrect bridge efx meter values size!
WARNING: Incorrect master meter values size!
WARNING: Incorrect signal meter values size!
```

## Track channel packing

The 12 track-meter bytes are not 12 separate UI strips. The ARM64 loop maps them into 10 channel strips:

```text
raw[0]  -> CH1
raw[1]  -> CH2
raw[2]  -> CH3
raw[3]  -> CH4
raw[4]  -> CH5
raw[5]  -> CH6
raw[6]  -> CH7
raw[7]  -> CH8
raw[8]  -> CH9/10 L
raw[9]  -> CH9/10 R
raw[10] -> CH11/12 L
raw[11] -> CH11/12 R
```

The code does this explicitly:

- for indices 0..7: strip index = raw index, side = 0;
- for indices 8..11: strip index = 8 + ((raw_index - 8) >> 1), side = raw_index & 1.

This strongly matches the L12next physical layout: eight mono strips plus two stereo strips.

The bridge 12-byte group uses the same packing.

## EFX and master

```text
track EFX  : 2 bytes -> stereo EFX return L/R
bridge EFX : 2 bytes -> stereo bridge EFX L/R
master     : 2 bytes -> master L/R
```

## Signal group

The signal meter group is also exactly 12 bytes and follows the same physical 12-channel packing.

The app contains the fields:

```text
inputLevelMetersPre
efxReturnLevelMetersPre
```

and also checks:

```text
WARNING: discrepancy between meter msg and internal fader mode
```

This suggests the app can switch between normal track/bridge meter data and pre/signal meter data depending on internal fader/meter mode.

## Value representation

The handler loads each meter entry with `ldrb` and stores the raw byte as an integer in the app meter arrays.

Therefore each meter lane is an unsigned **8-bit raw meter value**.

What is not yet proven:

- exact raw-value to dBFS conversion;
- clip/peak thresholds;
- whether the raw scale is linear in dB, segmented, or LED-index based.

Those conversions happen later in the UI/meter rendering path rather than in this packet handler.

## Why this is useful for AutoFonic

Once the raw packet framing is identified on the Linux side, a native meter backend can expose:

```text
CH1..CH8
CH9/10 L/R
CH11/12 L/R
EFX L/R
MASTER L/R
```

without capturing USB audio.

The remaining work is:

1. locate the incoming MIDI/SysEx frame that constructs `MeterParams`;
2. derive the raw byte -> dB/LED conversion from `LEDAudioMeter`;
3. validate one or two raw meter captures against known signal levels.


## LED level encoding recovered

The UI update path finally resolves the representation of each meter byte.

Before assigning a meter value to `LEDAudioMeter`, the app performs:

```text
SCVTF raw_integer -> Double
FMUL  value, 0.125
```

So:

```text
normalized_level = raw / 8.0
```

Inside `LEDAudioMeter` at approximately `0x10005A738`, the renderer does the inverse:

```text
level * 8
FCVTZS -> integer LED level
8 - LED level
```

and uses that result to crop/position the ON/OFF meter images.

Therefore the received meter byte is not a continuous 0..255 dB value. It is a discrete **8-step LED level**:

```text
raw 0 -> 0/8 LEDs
raw 1 -> 1/8 LEDs
...
raw 8 -> 8/8 LEDs
```

Values outside the valid integer range would trip Swift overflow/trap paths in this renderer, which is further evidence that the intended domain is 0..8.

### Consequence

For AutoFonic we can implement the native meter immediately as an 8-step meter without knowing a dB conversion:

```python
normalized = raw / 8.0
```

The exact dB threshold represented by each of the eight steps is **not converted in the app**. The app receives an already-quantized level and only renders the number of illuminated LEDs. Therefore the dB thresholds are probably decided by the mixer/firmware before the packet reaches the app.

To recover exact dB thresholds we need either:

1. a mixer-side specification/firmware mapping, or
2. a controlled signal-level test correlating known dBFS input with raw meter values 0..8.

This is separate from the fader law, which is a different nonlinear MIDI-value-to-dB mapping.


## Raw meter payload is nibble-packed

A lower-level C++ meter decoder at approximately `0x1000190AC` reveals how the meter payload is unpacked before it reaches the Swift/UI `MeterParams` bridge.

The decoder repeatedly reads payload bytes and uses:

```text
AND value, 0x0F
LSR value, 4
```

to split a byte into low and high nibbles.

This is strong static evidence that the actual mixer meter transport is **4-bit/nibble encoded**, consistent with the UI's final 0..8 LED domain. The Swift side stores meter values in bytes, but the useful meter magnitude itself occupies only a nibble.

The parser also processes blocks of 12 entries and 2-entry stereo groups, matching the already recovered channel layout.

### Important distinction

There are therefore three layers:

```text
wire/SysEx payload
    -> nibble unpacking in C++
    -> byte arrays in MeterParams
    -> normalized raw/8.0 in Swift
    -> 8-step LED renderer
```

So the 12-byte `track` group documented above is the **post-decoding MeterParams representation**, not necessarily 12 literal meter bytes on the wire.

### Current static evidence

The decoder contains:

- a 12-iteration loop that splits each source byte into high/low nibbles;
- another 12-entry meter-processing loop;
- 2-entry handling for stereo groups;
- explicit comparison with the internal fader/meter mode;
- forwarding into the state buffers later exposed as track/bridge/master/signal meter groups.

This makes it likely that the wire format packs multiple 4-bit meter values into each byte to reduce bandwidth.

The exact SysEx header/command byte and complete payload-length formula are still being traced.
