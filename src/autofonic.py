#!/usr/bin/env python3
"""AutoFonic v0.1 - safe test controller for ZOOM LiveTrak L12next.

Verified transport commands:
  REC  = B9 57 03
  STOP = BB 57 03

Unverified mixer commands (master fader, scene recall, etc.) are deliberately
not sent until they have been captured and verified on the user's mixer.
"""
from __future__ import annotations
import argparse
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass

SAMPLE_RATE = 48_000
USB_CHANNELS = 14
INPUTS = {
    1: "Kick TG D71",
    2: "Snare TG D58",
    3: "Tom 1 TG D57",
    4: "Tom 2 TG D57",
    5: "Floor TG D58",
    6: "OH L TG I53",
    7: "OH R TG I53",
    8: "Chitarra SM57",
    9: "Basso",
}
REC = bytes((0xB9, 0x57, 0x03))
STOP = bytes((0xBB, 0x57, 0x03))

@dataclass
class State:
    mode: str = "STUDIO"
    automix: bool = False
    autorec: bool = False
    master_db: float = -20.0
    master_muted: bool = False

def discover_port() -> str | None:
    """Find an ALSA MIDI destination whose name contains L12next."""
    try:
        out = subprocess.check_output(["aconnect", "-l"], text=True, stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError):
        return None
    client = None
    for line in out.splitlines():
        m = re.match(r"client\s+(\d+):\s+'([^']+)'", line)
        if m:
            client = m.group(1) if "l12next" in m.group(2).lower() else None
            continue
        if client:
            p = re.match(r"\s*(\d+)\s+'([^']+)'", line)
            if p:
                return f"{client}:{p.group(1)}"
    return None

def send_raw(port: str, payload: bytes) -> None:
    fd, path = tempfile.mkstemp(prefix="autofonic-", suffix=".bin")
    try:
        os.write(fd, payload)
        os.close(fd)
        fd = -1
        subprocess.run(["aseqsend", "-p", port, "-s", path], check=True)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

def main() -> int:
    ap = argparse.ArgumentParser(description="AutoFonic v0.1 safe L12next controller")
    ap.add_argument("--port", help="ALSA MIDI port, e.g. 128:0; auto-detected if omitted")
    ap.add_argument("command", choices=["status", "rec", "stop", "panic", "studio", "live"])
    args = ap.parse_args()
    state = State()
    port = args.port or discover_port()

    if args.command == "status":
        print(f"Mode: {state.mode}")
        print(f"AUTO MIX: {'ON' if state.automix else 'OFF'} (safe default)")
        print(f"AUTOREC: {'ON' if state.autorec else 'OFF'}")
        print(f"MASTER target: {state.master_db:.1f} dB")
        print(f"MIDI: {port or 'L12next non rilevato'}")
        print(f"USB audio: {USB_CHANNELS} ch @ {SAMPLE_RATE} Hz")
        for ch, name in INPUTS.items():
            print(f"CH{ch}: {name}")
        return 0

    if args.command in ("studio", "live"):
        print(args.command.upper())
        print("Scene recall not sent: command still to be verified.")
        return 0

    if args.command == "panic":
        print("PANIC requested.")
        print("Master mute command not sent: it must be re-verified before live use.")
        return 2

    if not port:
        raise SystemExit("L12next MIDI port not found. Use --port CLIENT:PORT.")
    send_raw(port, REC if args.command == "rec" else STOP)
    print(f"{args.command.upper()} sent to {port}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
