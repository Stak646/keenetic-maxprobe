#!/bin/sh
set -eu

PROG="keenetic-maxprobe"
REPO="Stak646/keenetic-maxprobe"
BRANCH="main"

say() { printf '%s\n' "$*" >&2; }

have() { command -v "$1" >/dev/null 2>&1; }

need() {
  have "$1" || { say "[!] Missing required command: $1"; exit 1; }
}

# Best-effort download helper
fetch() {
  url="$1"
  out="$2"

  if have curl; then
    curl -fSL "$url" -o "$out"
    return 0
  fi
  if have wget; then
    wget -O "$out" "$url"
    return 0
  fi
  say "[!] Need curl or wget"
  exit 1
}

# Pick router LAN IP (best-effort)
guess_ip() {
  if have ip; then
    # Keenetic LAN bridge is usually br0
    ip -4 addr show br0 2>/dev/null | awk '/inet /{sub(/\/.*/,"",$2); if($2 !~ /^127\./){print $2; exit}}' && return 0
    # fallback: first non-loopback
    ip -4 addr 2>/dev/null | awk '/inet / && $2 !~ /^127\./ {sub(/\/.*/,"",$2); print $2; exit}' || true
  fi
}

need tar
need sh

TMP="/tmp/${PROG}.$$"
mkdir -p "$TMP"
trap 'rm -rf "$TMP" 2>/dev/null || true' EXIT INT TERM

ARCHIVE_URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"
ARCHIVE="$TMP/src.tar.gz"

say "[*] Download: $ARCHIVE_URL"
fetch "$ARCHIVE_URL" "$ARCHIVE"

say "[*] Extract..."
tar -xzf "$ARCHIVE" -C "$TMP"

SRC_DIR="$(find "$TMP" -maxdepth 1 -type d -name "${PROG}-*" | head -n 1)"
[ -n "$SRC_DIR" ] || { say "[!] Failed to locate extracted dir"; exit 1; }

# Install paths (Entware/OPKG)
BIN_DIR="/opt/bin"
SHARE_DIR="/opt/share/${PROG}"
COLLECTORS_DST="${SHARE_DIR}/collectors"
DOCS_DST="${SHARE_DIR}/docs"
INITD_DIR="/opt/etc/init.d"
CFG="/opt/etc/${PROG}.conf"

mkdir -p "$BIN_DIR" "$COLLECTORS_DST" "$DOCS_DST" "$INITD_DIR"

say "[*] Install: $BIN_DIR/keenetic-maxprobe"
cp -f "$SRC_DIR/bin/keenetic-maxprobe" "$BIN_DIR/keenetic-maxprobe"
chmod +x "$BIN_DIR/keenetic-maxprobe"

# Optional helper
if [ -f "$SRC_DIR/scripts/entwarectl" ]; then
  say "[*] Install: $BIN_DIR/entwarectl"
  cp -f "$SRC_DIR/scripts/entwarectl" "$BIN_DIR/entwarectl"
  chmod +x "$BIN_DIR/entwarectl" || true
fi

say "[*] Install collectors -> $COLLECTORS_DST"
rm -rf "$COLLECTORS_DST"/*
cp -a "$SRC_DIR/collectors/." "$COLLECTORS_DST/"

say "[*] Install docs -> $DOCS_DST"
rm -rf "$DOCS_DST"/*
cp -a "$SRC_DIR/docs/." "$DOCS_DST/"

# Init script for Web UI
if [ -f "$SRC_DIR/scripts/init.d/S99keenetic-maxprobe-webui" ]; then
  say "[*] Install init script -> $INITD_DIR/S99keenetic-maxprobe-webui"
  cp -f "$SRC_DIR/scripts/init.d/S99keenetic-maxprobe-webui" "$INITD_DIR/S99keenetic-maxprobe-webui"
  chmod +x "$INITD_DIR/S99keenetic-maxprobe-webui" || true
fi

# Create config if missing
if [ ! -f "$CFG" ]; then
  say "[*] Create config: $CFG"
  cat >"$CFG" <<'EOF_CFG'
# keenetic-maxprobe config

# UI language: ru|en
LANG_UI="ru"

# default run parameters
PROFILE="auto"
MODE="full"
COLLECTORS="all"
CUSTOM_COLLECTORS=""

# output base selection: auto|ram|entware
OUTBASE_POLICY="auto"
OUTBASE_OVERRIDE=""

# web ui
WEB_BIND="0.0.0.0"
WEB_PORT="0"
WEB_TOKEN=""
EOF_CFG
fi

# Ensure python3 for Web UI (best-effort)
if have opkg; then
  if ! have python3; then
    say "[*] Installing python3 (for Web UI)..."
    opkg update >/dev/null 2>&1 || true
    opkg install python3 >/dev/null 2>&1 || true
  fi
fi

# Start Web UI service now (best-effort)
if [ -x "$INITD_DIR/S99keenetic-maxprobe-webui" ]; then
  say "[*] Starting Web UI service..."
  "$INITD_DIR/S99keenetic-maxprobe-webui" restart >/dev/null 2>&1 || true
fi

# Show Web UI URL (best-effort)
IP="$(guess_ip || true)"
[ -n "$IP" ] || IP="<router-ip>"

say ""
say "[+] Installed."
say "[+] Run CLI: keenetic-maxprobe"

UF="/opt/var/run/keenetic-maxprobe-webui.url"
PF="/opt/var/run/keenetic-maxprobe-webui.port"

# wait a little for state files (auto-port)
i=0
while [ $i -lt 10 ]; do
  [ -s "$UF" ] && break
  sleep 1
  i=$((i+1))
done

URL="$(cat "$UF" 2>/dev/null || true)"
if [ -n "$URL" ]; then
  URL="${URL%
}"
  say "[+] Web UI: $URL"
else
  PORT="$(cat "$PF" 2>/dev/null || true)"
  [ -n "$PORT" ] || PORT="<PORT>"
  say "[+] Web UI: http://${IP}:${PORT}/"
fi

say "[i] If you forgot the URL: cat /opt/var/run/keenetic-maxprobe-webui.url"
say ""
say "[+] Installed."
say "[+] Run CLI: keenetic-maxprobe"
PORT="$(awk -F= '/^WEB_PORT=/{gsub(/"/,"",$2); print $2}' "$CFG" 2>/dev/null || true)"
if [ "${PORT:-0}" = "0" ] 2>/dev/null; then
  PF="/opt/var/run/keenetic-maxprobe-webui.port"
  i=0
  while [ $i -lt 10 ]; do
    [ -s "$PF" ] && break
    sleep 1
    i=$((i+1))
  done
  PORT="$(cat "$PF" 2>/dev/null || true)"
fi
[ -n "${PORT:-}" ] || PORT="<PORT>"
say "[+] Web UI: http://${IP}:${PORT}/?token=${TOKEN:-<TOKEN>}"
say "[i] If you forgot the URL: cat /opt/var/run/keenetic-maxprobe-webui.url"
say ""
