# L12next BLE-MIDI protocol notes

## Status

Experimental reverse engineering. These notes describe observed behaviour, not an official protocol specification.

## Test path

- ZOOM LiveTrak L12next
- ZOOM BTA-1
- Linux / Raspberry Pi
- ALSA MIDI
- BLE traffic captured while the official L12next control application operated the mixer

## BLE observation

A GATT characteristic observed during investigation was:

```
7772e5db-3868-4112-a1a9-f2669d106bf3
```

Notifications from this characteristic included mixer state and MIDI-like traffic.

## Feedback is not necessarily a command

Physical transport-button activity produced messages including:

```
B8 57 05
B8 57 00
```

Sending those values back did not reproduce remote transport operation.

A clean capture of official-app traffic revealed different commands. After separating the BLE-MIDI timestamp bytes, the experimentally verified commands are:

```
REC   B9 57 03
STOP  BB 57 03
```

Sending these from Linux over the established BLE-MIDI ALSA connection successfully started and stopped recording.

## Linux verification

Find the current ALSA sequencer client:

```bash
aconnect -l
```

Replace `128:0` below with the current L12next port.

### REC

```bash
printf '\xB9\x57\x03' > /tmp/rec.bin
aseqsend -p 128:0 -s /tmp/rec.bin
```

### STOP

```bash
printf '\xBB\x57\x03' > /tmp/stop.bin
aseqsend -p 128:0 -s /tmp/stop.bin
```

## USB audio interface

The ALSA hardware-parameter query reported:

```
CHANNELS: 14
RATE: 48000
FORMAT: S32_LE FLOAT_LE
SAMPLE_BITS: 32
FRAME_BITS: 448
```

Example capture test:

```bash
arecord -D hw:2,0 -f S32_LE -r 48000 -c 14 -d 10 /tmp/l12-test.wav
```

The ALSA card number is system-dependent and should eventually be discovered dynamically.

## Next investigations

- map all 14 USB capture channels;
- build real-time RMS/peak meters;
- determine robust performance/silence thresholds;
- dynamically discover the BLE-MIDI ALSA destination;
- map mixer fader/control messages;
- verify read-back/state synchronization before automatic level changes.

## Reproducibility

Packet captures and proprietary application/firmware files are intentionally not required here. The repository documents the minimum observations needed to reproduce the tests.
