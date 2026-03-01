#!/bin/sh
# 10-ndm-hooks.sh — collect NDM hooks/configs (best-effort)
set -u

WORK="${WORK:-}"
[ -n "$WORK" ] || exit 0

out="$WORK/ndm/hooks"
mkdir -p "$out" 2>/dev/null || true

copy_dir() {
  src="$1"; dst="$2"
  [ -d "$src" ] || return 0
  mkdir -p "$dst" 2>/dev/null || true
  (cd "$src" 2>/dev/null && tar -cf - . 2>/dev/null) | (cd "$dst" 2>/dev/null && tar -xpf - 2>/dev/null) || true
}

copy_dir /etc/ndm "$out/etc_ndm"
copy_dir /opt/etc/ndm "$out/opt_etc_ndm"
copy_dir /storage/etc/ndm "$out/storage_etc_ndm"

# quick inventory
{
  echo "== /etc/ndm =="; ls -la /etc/ndm 2>/dev/null || true
  echo ""
  echo "== /opt/etc/ndm =="; ls -la /opt/etc/ndm 2>/dev/null || true
  echo ""
  echo "== /storage/etc/ndm =="; ls -la /storage/etc/ndm 2>/dev/null || true
} >"$out/list.txt" 2>/dev/null || true
