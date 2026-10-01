#!/usr/bin/env python3
"""
Interactive protocol tester for ZOOM LiveTrak L12next.

The tool intentionally tests one command at a time and asks for confirmation
before sending anything. Confirmed and experimental commands are stored in
commands.json so the protocol map can grow without changing this script.

Requirements:
  - Linux with ALSA sequencer tools installed
  - aconnect
  - aseqsend
  - an established L12next BLE-MIDI connection
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMMANDS = ROOT / "tools" / "commands.json"
DEFAULT_LOG_DIR = ROOT / "logs"


def run_text(args: list[str]) -> str:
    try:
        result = subprocess.run(
            args,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError(f"Required command not found: {args[0]}")
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise RuntimeError(f"{' '.join(args)} failed: {detail}")


def discover_l12next_port() -> str:
    """
    Locate the ALSA sequencer port whose client/port name contains L12next.
    Returns e.g. '128:0'.
    """
    output = run_text(["aconnect", "-l"])

    current_client: str | None = None
    current_name = ""

    for raw_line in output.splitlines():
        line = raw_line.rstrip()

        match_client = re.match(r"^client\s+(\d+):\s+'([^']*)'", line)
        if match_client:
            current_client = match_client.group(1)
            current_name = match_client.group(2)
            continue

        match_port = re.match(r"^\s+(\d+)\s+'([^']*)'", line)
        if match_port and current_client is not None:
            port_num = match_port.group(1)
            port_name = match_port.group(2)
            combined = f"{current_name} {port_name}".lower()
            if "l12next" in combined:
                return f"{current_client}:{port_num}"

    raise RuntimeError(
        "L12next ALSA MIDI port not found. "
        "Connect the mixer via BLE-MIDI and check 'aconnect -l'."
    )


def load_commands(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    commands = data.get("commands", [])
    if not isinstance(commands, list):
        raise RuntimeError("Invalid commands.json: 'commands' must be a list")
    return commands


def parse_hex_bytes(value: str) -> bytes:
    compact = value.replace("0x", "").replace(",", " ").strip()
    try:
        result = bytes(int(part, 16) for part in compact.split())
    except ValueError as exc:
        raise RuntimeError(f"Invalid MIDI byte string: {value}") from exc

    if not result:
        raise RuntimeError("Empty MIDI command")
    return result


def send_command(port: str, payload: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix="l12next_", suffix=".bin") as tmp:
        tmp.write(payload)
        tmp.flush()
        try:
            subprocess.run(
                ["aseqsend", "-p", port, "-s", tmp.name],
                check=True,
            )
        except FileNotFoundError:
            raise RuntimeError("Required command not found: aseqsend")
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"aseqsend failed with exit code {exc.returncode}")


def create_log(log_dir: Path) -> tuple[Path, object, csv.DictWriter]:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = log_dir / f"protocol_test_{stamp}.csv"
    fh = path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        fh,
        fieldnames=[
            "timestamp",
            "name",
            "category",
            "bytes",
            "status",
            "result",
            "notes",
        ],
    )
    writer.writeheader()
    fh.flush()
    return path, fh, writer


def show_commands(commands: list[dict]) -> None:
    if not commands:
        print("No commands available.")
        return

    print()
    print("Available commands")
    print("-" * 72)
    for cmd in commands:
        print(
            f"{cmd.get('name', '?'):12} "
            f"{cmd.get('category', '?'):12} "
            f"{cmd.get('bytes', '?'):20} "
            f"{cmd.get('status', '?')}"
        )
    print()


def select_commands(
    all_commands: list[dict],
    experimental: bool,
    requested: str | None,
) -> list[dict]:
    allowed = {"confirmed"}
    if experimental:
        allowed.add("experimental")

    selected = [
        cmd for cmd in all_commands
        if str(cmd.get("status", "")).lower() in allowed
    ]

    if requested:
        requested_upper = requested.upper()
        selected = [
            cmd for cmd in selected
            if str(cmd.get("name", "")).upper() == requested_upper
        ]
        if not selected:
            raise RuntimeError(
                f"Command '{requested}' not found in the selected mode."
            )

    return selected


def ask_result() -> tuple[str, str]:
    while True:
        answer = input(
            "Observed result [y=OK, n=NO, u=uncertain, s=skip note]: "
        ).strip().lower()

        if answer in {"y", "yes"}:
            result = "OK"
            break
        if answer in {"n", "no"}:
            result = "NO"
            break
        if answer in {"u", "?"}:
            result = "UNCERTAIN"
            break
        if answer in {"s", ""}:
            result = "NOT_RECORDED"
            break

    notes = input("Notes (optional): ").strip()
    return result, notes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactive ZOOM L12next BLE-MIDI protocol tester"
    )
    parser.add_argument(
        "--commands",
        type=Path,
        default=DEFAULT_COMMANDS,
        help="Path to commands.json",
    )
    parser.add_argument(
        "--port",
        help="ALSA sequencer destination, e.g. 128:0. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--experimental",
        action="store_true",
        help="Include commands marked experimental.",
    )
    parser.add_argument(
        "--command",
        help="Test only one named command, e.g. REC.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List commands and exit.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory for CSV test logs.",
    )
    args = parser.parse_args()

    try:
        all_commands = load_commands(args.commands)
        commands = select_commands(
            all_commands,
            experimental=args.experimental,
            requested=args.command,
        )

        if args.list:
            show_commands(commands)
            return 0

        port = args.port or discover_l12next_port()
        print(f"L12next ALSA port: {port}")
        print(
            "Mode:",
            "CONFIRMED + EXPERIMENTAL" if args.experimental else "CONFIRMED ONLY",
        )
        show_commands(commands)

        if not commands:
            print("Nothing to test.")
            return 0

        log_path, log_fh, writer = create_log(args.log_dir)
        print(f"Log: {log_path}")
        print()
        print("Each command requires confirmation before transmission.")
        print("Type q at a confirmation prompt to stop.")
        print()

        try:
            for index, cmd in enumerate(commands, start=1):
                name = str(cmd.get("name", "?"))
                byte_string = str(cmd.get("bytes", ""))
                status = str(cmd.get("status", ""))
                category = str(cmd.get("category", ""))
                description = str(cmd.get("description", ""))

                print("=" * 72)
                print(f"TEST {index:02d} - {name}")
                if description:
                    print(description)
                print(f"Bytes : {byte_string}")
                print(f"Status: {status}")

                confirm = input("Press ENTER to send, or q to quit: ").strip().lower()
                if confirm == "q":
                    print("Test stopped by user.")
                    break

                payload = parse_hex_bytes(byte_string)
                sent_at = datetime.now()
                send_command(port, payload)
                print("Command sent.")

                result, notes = ask_result()
                writer.writerow(
                    {
                        "timestamp": sent_at.isoformat(timespec="seconds"),
                        "name": name,
                        "category": category,
                        "bytes": byte_string,
                        "status": status,
                        "result": result,
                        "notes": notes,
                    }
                )
                log_fh.flush()
                print()
        finally:
            log_fh.close()

        print(f"Results saved to: {log_path}")
        return 0

    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
