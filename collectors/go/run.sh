#!/bin/sh
# collectors/go/run.sh
# Version: 0.6.0
# Usage: sh run.sh <workdir>
# Prints inventory to stdout (builds binary if `go` is available).

set -eu

WORKDIR="${1:-.}"

# Prefer a temp directory with enough space
TMP="/tmp"
[ -d /opt/var/tmp ] && TMP="/opt/var/tmp"
[ -d /opt/tmp ] && TMP="/opt/tmp"

SRC_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BIN="$TMP/kmp_go_inventory.$$"

if command -v go >/dev/null 2>&1; then
  (cd "$SRC_DIR" && go build -o "$BIN" inventory.go >/dev/null 2>&1) || {
    echo "go collector: build failed" >&2
    exit 1
  }
  "$BIN" "$WORKDIR" 2>/dev/null || "$BIN" 2>/dev/null || true
  rm -f "$BIN" 2>/dev/null || true
  exit 0
fi

echo "go collector: go toolchain not found; skipped"
exit 0
