#!/usr/bin/env python3
"""
Guided BLE reverse-engineering session for ZOOM LiveTrak L12next.

Capture is performed directly through Nordic nrfutil:
    nrfutil ble-sniffer sniff --port ... --follow ... --output-pcap-file ...

The script then:
1. guides the user through one ZOOM-app action at a time;
2. records precise timestamp markers for every requested action;
3. stops the Nordic capture cleanly;
4. uses tshark to extract ATT Write Request / Write Command packets;
5. correlates packets with each action window;
6. generates CSV + JSON reports and ranks candidate payloads.

This tool observes the official app. It does not brute-force or transmit
unknown commands to the mixer.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = ROOT / "tools" / "reverse_test_plan.json"
CAPTURE_ROOT = ROOT / "captures"
RAW_DIR = CAPTURE_ROOT / "raw"
EXTRACTED_DIR = CAPTURE_ROOT / "extracted"
REPORT_DIR = CAPTURE_ROOT / "reports"

DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_FOLLOW = "10:32:2C:BB:81:12"


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


def require_program(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required program not found: {name}")


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_plan(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tests = data.get("tests", [])
    if not isinstance(tests, list) or not tests:
        raise RuntimeError("Test plan contains no tests.")
    return tests


def ensure_dirs() -> None:
    for path in (RAW_DIR, EXTRACTED_DIR, REPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def start_capture(port: str, follow: str, capture_path: Path) -> subprocess.Popen:
    cmd = [
        "nrfutil",
        "ble-sniffer",
        "sniff",
        "--port",
        port,
        "--follow",
        follow,
        "--output-pcap-file",
        str(capture_path),
    ]

    print("Starting Nordic capture:")
    print("  " + " ".join(cmd))

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    time.sleep(2.0)

    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        detail = (stderr or stdout or "").strip()
        raise RuntimeError(f"Nordic capture failed to start: {detail}")

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
            proc.wait(timeout=3)


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
    print("Do not touch other app/mixer controls until the next prompt.")
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
            print("WARNING: this action may overwrite or delete scene data.")
            answer = input("Type YES to include this destructive test: ").strip()
            if answer != "YES":
                print("Skipped.")
                continue

        input("Press ENTER when ready for the countdown...")
        countdown(countdown_seconds)

        marker_time = time.time()
        print(">>> NOW <<<")
        print("Perform the requested action ONCE.")

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

        print(f"Waiting {after:.1f} seconds for BLE traffic...")
        time.sleep(after)
        print()

    return markers


def extract_att_writes(capture_path: Path) -> list[Packet]:
    display_filter = "btatt.opcode == 0x12 || btatt.opcode == 0x52"

    cmd = [
        "tshark",
        "-r",
        str(capture_path),
        "-Y",
        display_filter,
        "-T",
        "fields",
        "-E",
        "separator=\t",
        "-E",
        "occurrence=f",
        "-e",
        "frame.number",
        "-e",
        "frame.time_epoch",
        "-e",
        "btatt.handle",
        "-e",
        "btatt.opcode",
        "-e",
        "btatt.value",
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

        hits = [
            packet
            for packet in packets
            if lo <= packet.timestamp_epoch <= hi
        ]

        payload_counts = Counter(packet.value for packet in hits)

        report[marker.test_id] = {
            "marker": asdict(marker),
            "packet_count": len(hits),
            "writes": [asdict(packet) for packet in hits],
            "payload_counts": dict(payload_counts),
        }

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
                    "specificity": round(
                        1.0 - ((seen_in_tests - 1) / total_tests),
                        3,
                    ),
                }
            )

        candidates.sort(
            key=lambda item: (
                item["seen_in_test_windows"],
                -item["count_in_window"],
                item["value"],
            )
        )

        entry["candidates"] = candidates

    return report


def write_packets_csv(path: Path, packets: list[Packet]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "frame",
                "timestamp_epoch",
                "handle",
                "opcode",
                "value",
            ],
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
        description="Guided Nordic BLE capture and automatic L12next analysis"
    )

    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)

    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        help=f"Nordic serial port (default: {DEFAULT_PORT})",
    )

    parser.add_argument(
        "--follow",
        default=DEFAULT_FOLLOW,
        help=f"BLE address to follow (default: {DEFAULT_FOLLOW})",
    )

    parser.add_argument("--countdown", type=int, default=3)
    parser.add_argument("--window-before", type=float, default=0.75)
    parser.add_argument("--window-after", type=float, default=4.0)

    parser.add_argument(
        "--include-destructive",
        action="store_true",
        help="Allow SAVE/DELETE tests; each still requires typing YES.",
    )

    args = parser.parse_args()

    try:
        require_program("nrfutil")
        require_program("tshark")

        ensure_dirs()
        tests = load_plan(args.plan)

        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        capture_path = RAW_DIR / f"session_{stamp}.pcap"
        packet_csv_path = EXTRACTED_DIR / f"session_{stamp}_att_writes.csv"
        report_path = REPORT_DIR / f"session_{stamp}.json"
        marker_path = REPORT_DIR / f"session_{stamp}_markers.json"

        print(f"Nordic port : {args.port}")
        print(f"Follow BLE  : {args.follow}")
        print(f"Capture file: {capture_path}")
        print()

        print("IMPORTANT:")
        print("  1. Disconnect the ZOOM app from the mixer first if needed.")
        print("  2. Start this program.")
        print("  3. When Nordic capture is running, connect the ZOOM app.")
        print("  4. Then execute ONLY the requested action for each test.")
        print()

        input("Press ENTER to start Nordic capture...")

        capture_proc = start_capture(
            args.port,
            args.follow,
            capture_path,
        )

        try:
            print()
            print("Nordic capture is running.")
            print("Connect/verify the ZOOM app now.")
            input("When the app is connected and stable, press ENTER to begin tests...")

            markers = run_guided_tests(
                tests,
                countdown_seconds=args.countdown,
                before=args.window_before,
                after=args.window_after,
                include_destructive=args.include_destructive,
            )
        finally:
            print("Stopping Nordic capture...")
            stop_capture(capture_proc)

        marker_path.write_text(
            json.dumps(
                [asdict(marker) for marker in markers],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print("Extracting ATT writes with tshark...")
        packets = extract_att_writes(capture_path)

        write_packets_csv(packet_csv_path, packets)

        report = correlate(markers, packets)

        report_path.write_text(
            json.dumps(
                {
                    "session": {
                        "created": datetime.now().isoformat(timespec="seconds"),
                        "capture": str(capture_path),
                        "nrf_port": args.port,
                        "follow": args.follow,
                        "packet_count_att_writes": len(packets),
                    },
                    "tests": report,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print_summary(report)

        print()
        print("Saved:")
        print(f"  PCAP   : {capture_path}")
        print(f"  CSV    : {packet_csv_path}")
        print(f"  MARKERS: {marker_path}")
        print(f"  REPORT : {report_path}")
        print()
        print(
            "Candidate payloads are observations only. "
            "Validate plausible commands with protocol_tester.py "
            "before marking them confirmed."
        )

        return 0

    except (
        RuntimeError,
        OSError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
