#!/bin/sh
# 20-logs.sh — collect logs (best-effort, small)
set -u

WORK="${WORK:-}"
[ -n "$WORK" ] || exit 0

out="$WORK/sys/logs"
mkdir -p "$out" 2>/dev/null || true

# Keenetic logread already collected by main script if available.
# Here we just mirror /var/log if it exists and is small.
if [ -d /var/log ]; then
  # do not copy huge dirs; only files < 2MB
  find /var/log -maxdepth 2 -type f -size -2048k 2>/dev/null | while IFS= read -r f; do
    bn="$(echo "$f" | sed 's#/#_#g')"
    cp -f "$f" "$out/$bn" 2>/dev/null || true
  done
fi
