#!/bin/sh
# Compatibility wrapper (legacy name): maxprobe.sh
# Prefer local repo copy, fallback to installed binary.
set -u
DIR="$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd 2>/dev/null || echo "")"
if [ -n "$DIR" ] && [ -x "$DIR/bin/keenetic-maxprobe" ]; then
  exec "$DIR/bin/keenetic-maxprobe" "$@"
fi
exec keenetic-maxprobe "$@"
