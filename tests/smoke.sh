#!/bin/sh
set -eu

BIN="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)/bin/keenetic-maxprobe"

# Smoke test (for dev/container): should produce an archive in /var/tmp and not crash.
"$BIN" --profile lite --mode safe --collectors shonly --no-spinner --yes --no-install >/dev/null 2>&1

# Verify output directory policy
ls /var/tmp/keenetic-maxprobe-*.tar.gz >/dev/null 2>&1 || {
  echo "[FAIL] No archive found in /var/tmp" >&2
  exit 1
}

echo "[OK] smoke"
