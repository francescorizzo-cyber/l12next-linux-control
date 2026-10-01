# Capture workflow

`tools/reverse_capture.py` automates a guided reverse-engineering session.

It captures the BLE traffic while you use the official ZOOM app, places timestamp markers around each requested action, extracts ATT write traffic with tshark, and generates candidate payloads for every test window.

## Requirements

The Nordic nRF Sniffer must already be working and visible to Wireshark/tshark.

Check:

```bash
tshark -D
```

You should see an interface described as `nRF Sniffer for Bluetooth LE`.

## Run

```bash
python3 tools/reverse_capture.py
```

The default plan tests PLAY, STOP, FF, STOP, REW, STOP, and non-destructive scene actions.

SAVE and DELETE are skipped by default.

To explicitly allow destructive scene tests:

```bash
python3 tools/reverse_capture.py --include-destructive
```

Even in that mode, each destructive test requires typing `YES`.

## Output

Each session creates:

```
captures/raw/session_*.pcapng
captures/extracted/session_*_att_writes.csv
captures/reports/session_*_markers.json
captures/reports/session_*.json
```

The JSON report ranks payloads by how specific they are to each action window. These are candidates only, not confirmed commands.

Do not mark a candidate as confirmed until it is reproduced with the protocol tester and verified on the mixer.
