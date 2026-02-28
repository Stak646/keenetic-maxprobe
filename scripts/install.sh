#!/bin/sh
set -eu

PREFIX="/opt"
BIN="$PREFIX/bin"
SHARE="$PREFIX/share/keenetic-maxprobe"
TMPBASE="${TMPDIR:-/tmp}"

REPO_OWNER="Stak646"
REPO_NAME="keenetic-maxprobe"
BRANCH="main"
TARBALL_URL="https://github.com/$REPO_OWNER/$REPO_NAME/archive/refs/heads/$BRANCH.tar.gz"

log() { printf '%s\n' "$*" >&2; }

have() { command -v "$1" >/dev/null 2>&1; }

ensure_downloader() {
  if have curl || have wget; then
    return 0
  fi

  if have opkg; then
    log "[i] No curl/wget. Trying to install a downloader via opkg (best-effort)..."
    opkg update || true
    opkg install ca-bundle curl || true
    if have curl; then return 0; fi
    opkg install ca-bundle wget-ssl || true
    if have wget; then return 0; fi
    opkg install wget-nossl || true
    if have wget; then return 0; fi
  fi

  log "[!] No curl/wget available and cannot install them."
  log "    Install Entware/OPKG first."
  exit 1
}

download() {
  url="$1"
  dst="$2"
  if have curl; then
    curl -fsSL "$url" -o "$dst"
    return 0
  fi
  wget -qO "$dst" "$url"
}

log "[+] Installing keenetic-maxprobe from $TARBALL_URL"
ensure_downloader

mkdir -p "$BIN" "$SHARE" 2>/dev/null || true
mkdir -p "$TMPBASE" 2>/dev/null || true

TMPDIR_LOCAL="$TMPBASE/keenetic-maxprobe-install.$$"
trap 'rm -rf "$TMPDIR_LOCAL" 2>/dev/null || true' EXIT INT TERM
mkdir -p "$TMPDIR_LOCAL"

TAR="$TMPDIR_LOCAL/src.tar.gz"
download "$TARBALL_URL" "$TAR"

tar -xzf "$TAR" -C "$TMPDIR_LOCAL"
SRC="$TMPDIR_LOCAL/$REPO_NAME-$BRANCH"

cp -f "$SRC/scripts/keenetic-maxprobe" "$BIN/keenetic-maxprobe"
chmod +x "$BIN/keenetic-maxprobe"

rm -rf "$SHARE/collectors" 2>/dev/null || true
mkdir -p "$SHARE"
cp -R "$SRC/collectors" "$SHARE/collectors" 2>/dev/null || true

# Install entwarectl helper too (optional)
cp -f "$SRC/scripts/entwarectl" "$BIN/entwarectl" 2>/dev/null || true
chmod +x "$BIN/entwarectl" 2>/dev/null || true

log "[+] Installed: $BIN/keenetic-maxprobe"
log "[+] Collectors: $SHARE/collectors"
log "[+] Next:"
log "    keenetic-maxprobe --init   # optional"
log "    keenetic-maxprobe          # run probe"
