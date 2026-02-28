#!/bin/sh
# One-shot installer/runner for Keenetic Entware
# Usage (one-liner):
#   sh -c "$(wget -qO- https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"

set -u
PATH="/opt/bin:/opt/sbin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

echo "[install] keenetic-maxprobe"

if [ ! -d /opt ]; then
  echo "[install] ERROR: /opt not found. Install Entware/OPKG first." >&2
  exit 2
fi

if command -v opkg >/dev/null 2>&1; then
  echo "[install] opkg update (best-effort)"
  opkg update >/dev/null 2>&1 || true

  echo "[install] installing deps (best-effort)"
  # Keep minimal + common tooling. Ignore failures.
  opkg install coreutils findutils grep sed tar gzip curl ca-bundle ip-full iptables ipset procps-ng python3 >/dev/null 2>&1 || true
else
  echo "[install] WARNING: opkg not found; skipping deps"
fi

# Download binaries from GitHub raw (no git required)
# If this script is executed from a cloned repo, prefer local files.
TMPDIR="$(mktemp -d 2>/dev/null || echo /tmp/keenetic-maxprobe-install.$$)"
cleanup() { rm -rf "$TMPDIR" 2>/dev/null || true; }
trap cleanup EXIT

fetch() {
  url="$1"; out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$out"
  else
    wget -qO "$out" "$url"
  fi
}

# Detect whether we're running from inside the repo (has ../bin)
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd 2>/dev/null || echo "")"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." 2>/dev/null && pwd 2>/dev/null || echo "")"

install_from_local() {
  [ -x "$REPO_ROOT/bin/keenetic-maxprobe" ] || return 1
  mkdir -p /opt/bin 2>/dev/null || true
  cp -f "$REPO_ROOT/bin/keenetic-maxprobe" /opt/bin/keenetic-maxprobe
  cp -f "$REPO_ROOT/bin/keenetic-maxprobe-analyze" /opt/bin/keenetic-maxprobe-analyze 2>/dev/null || true
  cp -f "$REPO_ROOT/bin/entwarectl" /opt/bin/entwarectl 2>/dev/null || true
  chmod +x /opt/bin/keenetic-maxprobe /opt/bin/keenetic-maxprobe-analyze /opt/bin/entwarectl 2>/dev/null || true
  return 0
}

if install_from_local; then
  echo "[install] installed from local repo"
else
  # Remote install requires these env vars or editing in your fork:
  : "${KMP_RAW_BASE:=https://raw.githubusercontent.com/<YOU>/<REPO>/main}"
  echo "[install] fetching from $KMP_RAW_BASE"
  mkdir -p /opt/bin 2>/dev/null || true
  fetch "$KMP_RAW_BASE/bin/keenetic-maxprobe" "$TMPDIR/keenetic-maxprobe"
  fetch "$KMP_RAW_BASE/bin/keenetic-maxprobe-analyze" "$TMPDIR/keenetic-maxprobe-analyze"
  fetch "$KMP_RAW_BASE/bin/entwarectl" "$TMPDIR/entwarectl"
  cp -f "$TMPDIR/keenetic-maxprobe" /opt/bin/keenetic-maxprobe
  cp -f "$TMPDIR/keenetic-maxprobe-analyze" /opt/bin/keenetic-maxprobe-analyze 2>/dev/null || true
  cp -f "$TMPDIR/entwarectl" /opt/bin/entwarectl 2>/dev/null || true
  chmod +x /opt/bin/keenetic-maxprobe /opt/bin/keenetic-maxprobe-analyze /opt/bin/entwarectl 2>/dev/null || true
fi

echo "[install] running probe..."
ARCHIVE="$(/opt/bin/keenetic-maxprobe 2>/dev/null | tail -n 1)"
echo "[install] done: $ARCHIVE"
echo "$ARCHIVE"
