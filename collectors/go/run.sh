#!/bin/sh
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-.}"

arch="$(uname -m 2>/dev/null || echo unknown)"
bin=""

case "$arch" in
  aarch64|arm64) bin="$HERE/inventory_linux_arm64" ;;
  armv7l|armv6l|arm*) bin="$HERE/inventory_linux_arm" ;;
  mipsel*|mipsle*) bin="$HERE/inventory_linux_mipsle" ;;
  mips*) bin="$HERE/inventory_linux_mips" ;;
  x86_64|amd64) bin="$HERE/inventory_linux_amd64" ;;
esac

if [ -n "$bin" ] && [ -x "$bin" ]; then
  exec "$bin" --work "$WORK"
fi

if command -v go >/dev/null 2>&1; then
  cd "$HERE"
  go build -o /tmp/kmp_go_inventory inventory.go
  exec /tmp/kmp_go_inventory --work "$WORK"
fi

echo "No prebuilt binary for arch=$arch and go not installed" >&2
exit 1
