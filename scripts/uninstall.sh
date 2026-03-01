#!/bin/sh
set -eu

PROG="keenetic-maxprobe"

say() { printf '%s\n' "$*" >&2; }

BIN="/opt/bin/keenetic-maxprobe"
HELPER="/opt/bin/entwarectl"
SHARE="/opt/share/${PROG}"
INIT="/opt/etc/init.d/S99keenetic-maxprobe-webui"
CFG="/opt/etc/${PROG}.conf"

if [ -x "$INIT" ]; then
  say "[*] Stop Web UI service..."
  "$INIT" stop >/dev/null 2>&1 || true
fi

say "[*] Remove binaries..."
rm -f "$BIN" "$HELPER" 2>/dev/null || true

say "[*] Remove share dir..."
rm -rf "$SHARE" 2>/dev/null || true

say "[*] Remove init script..."
rm -f "$INIT" 2>/dev/null || true

say ""
say "[+] Uninstalled files."
say "[i] Config kept at: $CFG"
say "    (remove it manually if you want)"
