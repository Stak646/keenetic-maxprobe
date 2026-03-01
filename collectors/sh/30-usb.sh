#!/bin/sh
# 30-usb.sh — basic USB/storage diagnostics (best-effort)
set -u

WORK="${WORK:-}"
[ -n "$WORK" ] || exit 0

out="$WORK/sys/storage"
mkdir -p "$out" 2>/dev/null || true

command -v lsusb >/dev/null 2>&1 && lsusb 2>/dev/null >"$out/lsusb.txt" || true
[ -f /proc/partitions ] && cp -f /proc/partitions "$out/proc_partitions.txt" 2>/dev/null || true
[ -f /proc/scsi/scsi ] && cp -f /proc/scsi/scsi "$out/proc_scsi_scsi.txt" 2>/dev/null || true

command -v blkid >/dev/null 2>&1 && blkid 2>/dev/null >"$out/blkid.txt" || true
command -v df >/dev/null 2>&1 && df -h 2>/dev/null >"$out/df_h.txt" || true
