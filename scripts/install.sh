#!/bin/sh
set -eu

PREFIX="/opt"
BIN="$PREFIX/bin"

echo "[+] Installing dependencies (best-effort)..."
if command -v opkg >/dev/null 2>&1; then
  opkg update || true
  opkg install coreutils-findutils coreutils-stat coreutils-sha256sum tar gzip curl wget ca-bundle || true
  opkg install python3 python3-light perl lua ruby node || true
  opkg install ip-full iptables nftables net-tools procps-ng || true
else
  echo "[!] opkg not found. Install Entware/OPKG first."
fi

echo "[+] Installing keenetic-maxprobe..."
mkdir -p "$BIN" "$PREFIX/share/keenetic-maxprobe" || true
cp -f "$(dirname "$0")/keenetic-maxprobe" "$BIN/keenetic-maxprobe"
chmod +x "$BIN/keenetic-maxprobe"

cp -f "$(dirname "$0")/../collectors/analyze.py" "$PREFIX/share/keenetic-maxprobe/analyze.py" 2>/dev/null || true
cp -f "$(dirname "$0")/entwarectl" "$BIN/entwarectl" 2>/dev/null || true
chmod +x "$BIN/entwarectl" 2>/dev/null || true

echo "[+] Installed: $BIN/keenetic-maxprobe"
echo "[+] Run: keenetic-maxprobe --init  (or just: keenetic-maxprobe)"
