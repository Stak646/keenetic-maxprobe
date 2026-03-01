#!/bin/sh
# keenetic-maxprobe installer (Entware/Keenetic)
set -eu

REPO="https://github.com/Stak646/keenetic-maxprobe"
TARBALL="${REPO}/archive/refs/heads/main.tar.gz"

say() { printf '%s\n' "$*" >&2; }
need() { command -v "$1" >/dev/null 2>&1; }
ensure_dir() { [ -d "$1" ] || mkdir -p "$1"; }

BIN="/opt/bin"
SHARE="/opt/share/keenetic-maxprobe"
TMP="/tmp/keenetic-maxprobe-install.$$"

cleanup() { rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

ensure_dir "$BIN"
ensure_dir "$SHARE"

say "[+] Installing keenetic-maxprobe from $TARBALL"

if need opkg; then
  opkg update >/dev/null 2>&1 || true
  need curl || opkg install curl >/dev/null 2>&1 || true
  need wget || opkg install wget-ssl >/dev/null 2>&1 || opkg install wget-nossl >/dev/null 2>&1 || true
  need tar  || opkg install tar >/dev/null 2>&1 || true
  need gzip || opkg install gzip >/dev/null 2>&1 || true
fi

ensure_dir "$TMP"
cd "$TMP"

if need curl; then
  curl -fsSL "$TARBALL" -o main.tar.gz
elif need wget; then
  wget -qO main.tar.gz "$TARBALL"
else
  say "[-] Need curl or wget"
  exit 1
fi

tar -xzf main.tar.gz
SRC_DIR="$(find . -maxdepth 1 -type d -name 'keenetic-maxprobe-*' | head -n 1)"
[ -n "$SRC_DIR" ] || { say "[-] Cannot find extracted source dir"; exit 1; }

cp -f "$SRC_DIR/bin/keenetic-maxprobe" "$BIN/keenetic-maxprobe"
chmod +x "$BIN/keenetic-maxprobe"

if [ -f "$SRC_DIR/scripts/entwarectl" ]; then
  cp -f "$SRC_DIR/scripts/entwarectl" "$BIN/entwarectl"
  chmod +x "$BIN/entwarectl"
  say "[+] Helper:   $BIN/entwarectl"
fi

rm -rf "$SHARE/collectors" 2>/dev/null || true
cp -a "$SRC_DIR/collectors" "$SHARE/collectors"

say "[+] Installed: $BIN/keenetic-maxprobe"
say "[+] Collectors: $SHARE/collectors"
say "[+] Run: keenetic-maxprobe (or keenetic-maxprobe --init)"
