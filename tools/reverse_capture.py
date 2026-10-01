#!/usr/bin/env python3
"""
Guided BLE reverse-engineering session for ZOOM LiveTrak L12next.

What it does:
1. finds the nRF Sniffer interface exposed by tshark;
2. starts a full .pcapng capture;
3. guides the user through one ZOOM-app action at a time;
4. records a timestamp marker for each requested action;
5. stops capture cleanly;
6. runs tshark over the capture and extracts ATT Write Request / Write Command packets;
7. correlates writes with each action window;
8. generates CSV + JSON reports and highlights candidate payloads.

This tool does NOT brute-force unknown mixer commands and does NOT send
experimental commands to the mixer. It observes the official app only.

Requirements:
    tshark
    nRF Sniffer for Bluetooth LE extcap visible in: tshark -D
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = ROOT / "tools" / "reverse_test_plan.json"
CAPTURE_ROOT = ROOT / "captures"
RAW_DIR = CAPTURE_ROOT / "raw"
EXTRACTED_DIR = CAPTURE_ROOT / "extracted"
REPORT_DIR = CAPTURE_ROOT / "reports"


@dataclass
class Marker:
    test_id: str
    label: str
    category: str
    timestamp_epoch: float
    window_before: float
    window_after: float


@dataclass
class Packet:
    frame: str
    timestamp_epoch: float
    handle: str
    opcode: str
    value: str


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def require_program(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(
            f"Required program '{name}' not found. "
            f"Install Wireshark/tshark first."
        )


def list_interfaces() -> str:
    result = run(["tshark", "-D"])
    return result.stdout


def detect_nrf_interface(explicit: str | None) -> str:
    if explicit:
        return explicit

    output = list_interfaces()
    candidates: list[tuple[str, str]] = []

    for line in output.splitlines():
        # Typical examples:
        # 7. /dev/ttyACM0 (nRF Sniffer for Bluetooth LE)
        # 7. nrf_sniffer_ble (nRF Sniffer for Bluetooth LE)
        m = re.match(r"^\s*(\d+)\.\s+(.+?)(?:\s+\((.*)\))?\s*$", line)
        if not m:
            continue
        idx, iface, desc = m.group(1), m.group(2).strip(), (m.group(3) or "")
        hay = f"{iface} {desc}".lower()
        if "nrf" in hay and "sniffer" in hay:
            candidates.append((idx, iface))

    if not candidates:
        raise RuntimeError(
            "nRF Sniffer interface not found in 'tshark -D'.\n"
            "Run 'tshark -D' manually and verify that the Nordic sniffer appears."
        )

    # Prefer a device path if present, otherwise first matching extcap entry.
    for idx, iface in candidates:
        if "/dev/tty" in iface:
            return iface
    return candidates[0][1]


def load_plan(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tests = data.get("tests", [])
    if not isinstance(tests, list) or not tests:
        raise RuntimeError("Test plan contains no tests.")
    return tests


def ensure_dirs() -> None:
    for path in (RAW_DIR, EXTRACTED_DIR, REPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def start_capture(interface: str, capture_path: Path) -> subprocess.Popen:
    # -q keeps terminal output quiet. Capture remains unfiltered so that we
    # preserve evidence for later re-analysis.
    cmd = ["tshark", "-q", "-i", interface, "-w", str(capture_path)]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(2.0)
    if proc.poll() is not None:
        stderr = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"tshark capture failed to start: {stderr.strip()}")
    return proc


def stop_capture(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return

    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def countdown(seconds: int) -> None:
    for n in range(seconds, 0, -1):
        print(f"  {n}...")
        time.sleep(1)


def run_guided_tests(
    tests: list[dict],
    *,
    countdown_seconds: int,
    before: float,
    after: float,
    include_destructive: bool,
) -> list[Marker]:
    markers: list[Marker] = []

    print()
    print("GUIDED APP TEST")
    print("=" * 72)
    print("Keep the ZOOM app connected to the mixer.")
    print("Perform ONLY the requested action after NOW.")
    print("Do not touch other mixer/app controls until the next prompt.")
    print()

    for index, test in enumerate(tests, start=1):
        destructive = bool(test.get("destructive", False))

        if destructive and not include_destructive:
            print(
                f"[SKIP] {test.get('label')} is destructive. "
                "Use --include-destructive to enable it."
            )
            continue

        print("=" * 72)
        print(f"TEST {index:02d} - {test.get('label', test.get('id'))}")
        print(test.get("instruction", ""))

        if destructive:
            print("WARNING: this action may overwrite or delete mixer data.")
            answer = input("Type YES to include this destructive test: ").strip()
            if answer != "YES":
                print("Skipped.")
                continue

        input("Press ENTER when you are ready for the countdown...")
        countdown(countdown_seconds)
        marker_time = time.time()
        print(">>> NOW <<<")
        print("Perform the requested action ONCE.")
        print(f"Waiting {after:.1f} seconds for BLE traffic...")
        markers.append(
            Marker(
                test_id=str(test.get("id", "")),
                label=str(test.get("label", "")),
                category=str(test.get("category", "")),
                timestamp_epoch=marker_time,
                window_before=before,
                window_after=after,
            )
        )
        time.sleep(after)
        print()

    return markers


def extract_att_writes(capture_path: Path) -> list[Packet]:
    display_filter = "btatt.opcode == 0x12 || btatt.opcode == 0x52"
    fields = [
        "-e", "frame.number",
        "-e", "frame.time_epoch",
        "-e", "btatt.handle",
        "-e", "btatt.opcode",
        "-e", "btatt.value",
    ]
    cmd = [
        "tshark",
        "-r", str(capture_path),
        "-Y", display_filter,
        "-T", "fields",
        "-E", "separator=\t",
        "-E", "occurrence=f",
        *fields,
    ]
    result = run(cmd)

    packets: list[Packet] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue

        frame, epoch, handle, opcode, value = parts[:5]
        if not epoch or not value:
            continue

        try:
            ts = float(epoch)
        except ValueError:
            continue

        packets.append(
            Packet(
                frame=frame,
                timestamp_epoch=ts,
                handle=handle,
                opcode=opcode,
                value=value.replace(":", "").lower(),
            )
        )

    return packets


def correlate(markers: list[Marker], packets: list[Packet]) -> dict:
    report: dict[str, dict] = {}

    for marker in markers:
        lo = marker.timestamp_epoch - marker.window_before
        hi = marker.timestamp_epoch + marker.window_after
        hits = [p for p in packets if lo <= p.timestamp_epoch <= hi]

        payload_counts = Counter(p.value for p in hits)
        report[marker.test_id] = {
            "marker": asdict(marker),
            "packet_count": len(hits),
            "writes": [asdict(p) for p in hits],
            "payload_counts": dict(payload_counts),
        }

    # Compare payloads across tests. Payloads appearing in many unrelated
    # windows are likely background/synchronization traffic.
    prevalence: Counter[str] = Counter()
    for entry in report.values():
        for payload in set(entry["payload_counts"].keys()):
            prevalence[payload] += 1

    total_tests = max(len(report), 1)

    for entry in report.values():
        candidates = []
        for payload, count in entry["payload_counts"].items():
            seen_in_tests = prevalence[payload]
            candidates.append(
                {
                    "value": payload,
                    "count_in_window": count,
                    "seen_in_test_windows": seen_in_tests,
                    "specificity": round(1.0 - ((seen_in_tests - 1) / total_tests), 3),
                }
            )

        candidates.sort(
            key=lambda x: (
                x["seen_in_test_windows"],
                -x["count_in_window"],
                x["value"],
            )
        )
        entry["candidates"] = candidates

    return report


def write_packets_csv(path: Path, packets: list[Packet]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["frame", "timestamp_epoch", "handle", "opcode", "value"],
        )
        writer.writeheader()
        for packet in packets:
            writer.writerow(asdict(packet))


def print_summary(report: dict) -> None:
    print()
    print("AUTOMATIC ANALYSIS")
    print("=" * 72)

    for test_id, entry in report.items():
        marker = entry["marker"]
        print(f"{marker['label']} ({test_id})")
        print(f"  ATT writes in window: {entry['packet_count']}")

        candidates = entry.get("candidates", [])
        if not candidates:
            print("  No ATT write candidate found.")
            continue

        for candidate in candidates[:8]:
            print(
                "  "
                f"{candidate['value']}  "
                f"count={candidate['count_in_window']}  "
                f"windows={candidate['seen_in_test_windows']}  "
                f"specificity={candidate['specificity']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Guided nRF/Wireshark capture and automatic L12next BLE analysis"
    )
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument(
        "--interface",
        help="tshark capture interface. Auto-detected from 'tshark -D' if omitted.",
    )
    parser.add_argument("--countdown", type=int, default=3)
    parser.add_argument("--window-before", type=float, default=0.75)
    parser.add_argument("--window-after", type=float, default=4.0)
    parser.add_argument(
        "--include-destructive",
        action="store_true",
        help="Allow SAVE/DELETE tests. Each still requires typing YES.",
    )
    parser.add_argument(
        "--list-interfaces",
        action="store_true",
        help="Print tshark interfaces and exit.",
    )
    args = parser.parse_args()

    try:
        require_program("tshark")

        if args.list_interfaces:
            print(list_interfaces())
            return 0

        ensure_dirs()
        tests = load_plan(args.plan)
        interface = detect_nrf_interface(args.interface)

        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        capture_path = RAW_DIR / f"session_{stamp}.pcapng"
        packet_csv_path = EXTRACTED_DIR / f"session_{stamp}_att_writes.csv"
        report_path = REPORT_DIR / f"session_{stamp}.json"
        marker_path = REPORT_DIR / f"session_{stamp}_markers.json"

        print(f"nRF capture interface: {interface}")
        print(f"Capture file: {capture_path}")
        print()
        input(
            "Make sure the sniffer is following the L12next connection, "
            "then press ENTER to start..."
        )

        capture_proc = start_capture(interface, capture_path)
        try:
            markers = run_guided_tests(
                tests,
                countdown_seconds=args.countdown,
                before=args.window_before,
                after=args.window_after,
                include_destructive=args.include_destructive,
            )
        finally:
            print("Stopping capture...")
            stop_capture(capture_proc)

        marker_path.write_text(
            json.dumps([asdict(m) for m in markers], indent=2) + "\n",
            encoding="utf-8",
        )

        print("Extracting ATT writes...")
        packets = extract_att_writes(capture_path)
        write_packets_csv(packet_csv_path, packets)

        report = correlate(markers, packets)
        report_path.write_text(
            json.dumps(
                {
                    "session": {
                        "created": datetime.now().isoformat(timespec="seconds"),
                        "capture": str(capture_path),
                        "interface": interface,
                        "packet_count_att_writes": len(packets),
                    },
                    "tests": report,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        print_summary(report)

        print()
        print("Saved:")
        print(f"  PCAPNG : {capture_path}")
        print(f"  CSV    : {packet_csv_path}")
        print(f"  MARKERS: {marker_path}")
        print(f"  REPORT : {report_path}")
        print()
        print(
            "Next step: inspect the most test-specific candidate payloads, "
            "then add only plausible candidates to tools/commands.json "
            "as status=experimental before transmission tests."
        )
        return 0

    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
