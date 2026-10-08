# recvCC dispatcher analysis

## Dispatcher

The decrypted app contains a concrete ARM64 receive dispatcher at `0x10001893C`.

Input validation:
- MIDI channel must be 0..15;
- CC must be 0..127.

Lookup:

```text
base = 0x10007AEA4
entry = base + CC*0xC0 + channel*0x0C
```

Entry:

```text
+0x0 target_id
+0x4 function_id
+0x8 aux
```

Function IDs 1..78 are dispatched through the halfword jump table at `0x100074D24`.

## Unhandled receive path

Default target: `0x100018CD8`

```text
WARNING: received unhandled CC (%d): 0x%02X, 0x%02X, 0x%02X
```

Directly-unhandled IDs in this build:

```text
33, 38, 41, 43, 44, 47, 48, 49, 50, 51,
55, 56, 57, 66, 68, 69
```

These table entries are transmit-side, reserved, or app-private rather than ordinary incoming state handlers.

## Function 77

Function 77 is now structurally resolved.

Its recvCC branch selects one of two bytes at:

```text
0x74F0
0x74F1
```

using the table `aux` field. The corresponding getter recombines them as:

```text
value14 = byte1 | (byte0 << 7)
```

Therefore function 77 is the two halves of one app-private **14-bit EFX auxiliary field**. The exact human-readable parameter name is not exposed by this app build.

## ProjectState

A bridge routine copies 39 bytes from state offset `0x7539` into Swift `ProjectState`.

| offset | field | function ID |
|---:|---|---:|
| 0 | recorderStatus | 46 |
| 1 | overdub | 52 |
| 2 | markStatus | 53 |
| 3 | markNumber | 54 |
| 17 | samplingRate | 58 |
| 18 | bitDepth | 59 |
| 19 | sdCardIcon | 60 |
| 20 | metronomeIcon | 61 |
| 21 | playmode | 62 |
| 22 | projectProtect | 63 |
| 37 | previousExists | 64 |
| 38 | nextExists | 65 |

Swift reflection metadata gives discriminator order:

```text
RecorderStatus:
0 stop
1 play
2 pause
3 recStandBy
4 recPause
5 recPlay

MarkStatus:
0 hide
1 atMark
2 notAtMark

PlayMode:
0 off
1 playOne
2 playAll
3 repeatOne
4 repeatAll
```

## Remaining app-private IDs

Processed but still without a trustworthy semantic label:
- function 45 at B7/CC87;
- function 67 at B9/CC89.

Transmit-only/unhandled entries that do not participate in the normal receive-state path include 55, 56, 57 and 68.
