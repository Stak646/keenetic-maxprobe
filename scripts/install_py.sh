#!/bin/sh
# Compatibility helper: ensure python3 and start Web UI.
set -eu

have() { command -v "$1" >/dev/null 2>&1; }
say() { printf '%s\n' "$*" >&2; }

if have opkg; then
  if ! have python3; then
    say "[*] Installing python3..."
    opkg update >/dev/null 2>&1 || true
    opkg install python3 >/dev/null 2>&1 || true
  fi
else
  say "[!] opkg not found; cannot install python3 automatically"
fi

if [ -x /opt/etc/init.d/S99keenetic-maxprobe-webui ]; then
  say "[*] Restart Web UI service..."
  /opt/etc/init.d/S99keenetic-maxprobe-webui restart >/dev/null 2>&1 || true
else
  say "[i] init script not found; start manually:"
  say "    keenetic-maxprobe --web --web-bind 0.0.0.0 --web-port 8088"
fi

say "[+] Done."
