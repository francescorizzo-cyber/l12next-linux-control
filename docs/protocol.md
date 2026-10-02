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
OVERDUB_ALL_ARM  B9 57 03
PLAY              BA 57 03
STOP              BB 57 03
```

Sending these from Linux over the established BLE-MIDI ALSA connection successfully started and stopped recording.

## Transport targets still to reverse-engineer

The following transport controls are explicitly included in the reverse-engineering plan because they did not work through the previous USB control path:

- PLAY
- FF (fast forward)
- REW (rewind)

Their BLE-MIDI bytes are not yet known, so they are recorded in `tools/commands.json` with status `to_discover`. The interactive tester will not transmit them until capture analysis gives us candidate bytes and we deliberately mark those candidates as `experimental`.

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

- reverse-engineer PLAY, FF and REW over BLE-MIDI;
- map all 14 USB capture channels;
- build real-time RMS/peak meters;
- determine robust performance/silence thresholds;
- dynamically discover the BLE-MIDI ALSA destination;
- map mixer fader/control messages;
- verify read-back/state synchronization before automatic level changes.

## Reproducibility

Packet captures and proprietary application/firmware files are intentionally not required here. The repository documents the minimum observations needed to reproduce the tests.


## PLAY verified over USB ALSA

PLAY was successfully replayed through the L12next USB ALSA sequencer port using the MIDI bytes:

```
BA 57 03
```

On the tested Linux system the USB mixer control endpoint appeared as:

```
client 24: 'L12next'
    0 'L12next Mixer Control Port'
```

A minimal MIDI file containing the event can be sent with `aplaymidi`:

```bash
printf '\x4d\x54\x68\x64\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60\x4d\x54\x72\x6b\x00\x00\x00\x08\x00\xba\x57\x03\x00\xff\x2f\x00' > /tmp/play.mid
aplaymidi -p 24:0 /tmp/play.mid
```

This confirms that the USB control path can accept at least some transport commands.


## Scene controls verified over USB ALSA

Direct hardware testing corrected the earlier interpretation:

```
BD 56 03
```

Behavior: enters/activates scene operation mode; the SAVE / RECALL / DELETE indicators blink.

```
BA 56 03
```

Behavior: triggers RECALL for the currently selected scene.

The MIDI command that changes/selects the scene number itself is still to be identified.



## Scene 7 selection verified

```
B1 57 03
```

Behavior: selects scene 7. SAVE / RECALL / DELETE blink, indicating the selection is pending.

The selected scene is not activated until RECALL is sent separately:

```
BA 56 03
```

Therefore scene selection and scene recall are two distinct operations.


## Corrected transport / recording mapping

A direct USB ALSA hardware retest established:

```
B9 57 03  -> arms all channels in overdub/overburn mode
BA 57 03  -> PLAY SOUND
BB 57 03  -> STOP
```

The earlier interpretation of `B9 57 03` as REC was incorrect and is superseded by this hardware test.


## Scene SAVE verified

```
B9 56 03
```

Behavior: saves the currently selected scene. Verified by direct USB ALSA replay on hardware.


## Correction: BB 56 03

```
BB 56 03
```

Behavior: selects scene 1. It does **not** perform DELETE.

Scene DELETE remains unidentified.


## Correction: BD 56 03

Direct hardware retest confirmed:

```
BD 56 03 -> selects scene 3
```

The previous interpretation of this message as entering scene-operation mode was incorrect.


## Additional scene mapping confirmed

Direct USB ALSA tests confirmed:

```
BC 56 03 -> scene 2
BE 56 03 -> scene 4
BF 56 03 -> scene 5
B4 57 03 -> RESET
```


## Official MIDI table: scene 10 and delete

The L12next operation manual MIDI implementation table resolves the remaining scene controls:

```
BC 59 03 -> Scene 10 select
BD 59 03 -> Scene DELETE
```

The status bytes follow MIDI channel numbering (B0 = channel 1), and the tested button-press value is `03`.

The same official table identifies:

```
B9 57 03 -> RECORD BUTTON
BA 57 03 -> PLAY
BB 57 03 -> STOP
BC 57 03 -> REW
BD 57 03 -> FAST FORWARD
BE 57 03 -> OVERDUB MODE
```

On the tested hardware, B9 57 03 was observed while Overdub mode was active and appeared to arm channels; the official parameter name is RECORD BUTTON.


## CH1 fader mapping

The official MIDI implementation assigns channel faders to CC 60 (`0x3C`), with the MIDI channel selecting the L12next mixer channel.

A BLE/app capture of CH1 confirmed:

```
B0 3C vv
```

Observed settled values in the capture:

```
-inf dB   -> B0 3C 00
~ -20 dB  -> B0 3C 1D
~ -10 dB  -> B0 3C 35
0 dB      -> B0 3C 57
```

Intermediate values were transmitted continuously while dragging the fader, indicating absolute 7-bit MIDI values rather than relative increments.


## General channel fader pattern

Direct USB ALSA tests confirmed the per-channel fader pattern:

```
CH1  -> B0 3C vv
CH2  -> B1 3C vv
CH3  -> B2 3C vv
...
CH16 -> BF 3C vv
```

`0x3C` is the fader controller and `vv` is an absolute 7-bit position.

Verified reference points captured on CH1:

```
-inf dB   -> 00
~ -20 dB  -> 1D
~ -10 dB  -> 35
0 dB      -> 57
```

CH2 was also replay-tested successfully over the USB ALSA mixer control port, confirming that the MIDI status nibble selects the mixer channel.

### AutoFonic impact

AutoFonic already has gain/trim control logic. The newly confirmed fader mapping means the software can now control both gain/trim and per-channel fader levels. The next reverse-engineering priorities are mixer feedback/state synchronization, per-channel mute, monitor sends, and reliable physical REC/STOP state handling.
