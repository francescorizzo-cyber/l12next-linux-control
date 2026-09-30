#!/usr/bin/env python3
"""Initial L12next USB-audio analyzer scaffold."""

SAMPLE_RATE = 48_000
CHANNELS = 14
SAMPLE_FORMAT = "S32_LE"

CHANNEL_NAMES = [f"CH{i}" for i in range(1, CHANNELS + 1)]

def main():
    print("L12next analyzer scaffold")
    print(f"{CHANNELS} channels @ {SAMPLE_RATE} Hz, {SAMPLE_FORMAT}")
    for index, name in enumerate(CHANNEL_NAMES, start=1):
        print(f"{index:02d}: {name}")

if __name__ == "__main__":
    main()
