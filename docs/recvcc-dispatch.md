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

The entry fields are:
```text
+0x0 target_id
+0x4 function_id
+0x8 aux
```

Function IDs 1..78 are dispatched through a halfword jump table at `0x100074D24`.

## Unhandled receive path

Default target: `0x100018CD8`

Diagnostic:
```text
WARNING: received unhandled CC (%d): 0x%02X, 0x%02X, 0x%02X
```

Function IDs that land directly there in this build:

```text
33, 38, 41, 43, 44, 47, 48, 49, 50, 51,
55, 56, 57, 66, 68, 69
```

This proves the table is broader than the receive-state implementation: some entries are transmit-side, reserved, or app-private.

## ProjectState

A bridge routine copies 39 bytes from state offset `0x7539` and maps them into Swift `ProjectState`.

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

Swift reflection strings confirm the field names and expose enum case names for recorder status, mark status and play mode.

## Still unresolved

Processed but not yet semantically proven:
- function 45 at B7/CC87;
- function 67 at B9/CC89;
- function 77 at B8/B9 CC94.

Transmit-only/unhandled entries still requiring send-side tracing:
- 55, 56, 57, 68.
