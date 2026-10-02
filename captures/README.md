# Capture workflow

`tools/reverse_capture.py` automates a guided L12next reverse-engineering session.

The current version captures directly with Nordic `nrfutil ble-sniffer sniff`, which is the method verified to stay running with the user's nRF52840 sniffer setup. Wireshark/tshark is then used only for offline packet analysis.

## Requirements

Verify both programs:

```bash
nrfutil --version
tshark --version
```

The default sniffer port is:

```
/dev/ttyACM0
```

The default L12next BLE address currently configured is:

```
10:32:2C:BB:81:12
```

Both can be overridden from the command line.

## Run

Recommended sequence:

1. disconnect the ZOOM app from the mixer if necessary;
2. launch the script;
3. let the script start the Nordic sniffer;
4. reconnect the ZOOM app;
5. wait until the app is stable;
6. start the guided tests;
7. perform exactly one requested action after each `NOW` message.

Start:

```bash
python3 tools/reverse_capture.py
```

Custom serial port:

```bash
python3 tools/reverse_capture.py --port /dev/ttyACM0
```

Custom mixer address:

```bash
python3 tools/reverse_capture.py --follow 10:32:2C:BB:81:12
```

The default plan covers PLAY, STOP, FF, REW and non-destructive scene operations.

SAVE and DELETE tests are skipped by default.

To enable them:

```bash
python3 tools/reverse_capture.py --include-destructive
```

Each destructive test still requires manually typing `YES`.

## Output

Each session creates:

```
captures/raw/session_*.pcap
captures/extracted/session_*_att_writes.csv
captures/reports/session_*_markers.json
captures/reports/session_*.json
```

The JSON report ranks ATT-write payloads by how specific they are to each action window.

These payloads are candidates only. Confirm candidates on the mixer with `tools/protocol_tester.py` before marking them as verified protocol commands.
