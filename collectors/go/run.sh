#!/bin/sh
set -eu

OUT_FILE="${1:-}"
WORKDIR="${2:-/tmp}"
if [ -z "$OUT_FILE" ]; then
  echo "usage: run.sh <out_file> [workdir]" >&2
  exit 2
fi

if ! command -v go >/dev/null 2>&1; then
  echo "go not found" >"$OUT_FILE"
  exit 0
fi

mkdir -p "$WORKDIR" 2>/dev/null || true
BIN="$WORKDIR/kmprobe_go_inventory.$(date +%s).bin"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
go build -o "$BIN" "$SRC_DIR/inventory.go" >/dev/null 2>&1 || {
  echo "go build failed" >"$OUT_FILE"
  exit 0
}
"$BIN" "$OUT_FILE" >/dev/null 2>&1 || true
rm -f "$BIN" 2>/dev/null || true
