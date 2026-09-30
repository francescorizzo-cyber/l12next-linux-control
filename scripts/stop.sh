#!/bin/sh
set -eu
PORT="${1:-128:0}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
printf '\xBB\x57\x03' > "$TMP"
aseqsend -p "$PORT" -s "$TMP"
