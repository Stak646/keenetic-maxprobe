# Documentation (EN)

## Purpose

`keenetic-maxprobe` is meant to:
- discover available KeeneticOS management interfaces (local CLI `ndmc`, and web/RCI if enabled);
- inventory Entware (opkg, init scripts, configs, logs);
- find real OPKG component **event hooks** (`/opt/etc/ndm/*.d`, `/storage/etc/ndm/*.d`);
- build a practical “command/state map” for a Telegram bot.

## Run

With Entware installed:

```sh
/opt/bin/keenetic-maxprobe
```

It prints the path to the resulting `...tar.gz` bundle.

## Output layout

- `ndm/` — `ndmc` outputs
- `entware/` — opkg + Entware tree + init.d
- `hooks/` — hook trees and dumped scripts
- `fs/` — config lists + metadata + (<=512KiB) file dumps
- `net/` — ip/route/rules, iptables/ipset, netstat
- `api/` — web/RCI endpoint probe (no auth)
- `analysis/` — RU/EN reports + JSON summary

## Telegram bot architecture (recommended)

### 1) Single KeeneticOS control layer

**Recommended:** run the bot on the router and use `ndmc`:
- no need to store the admin password;
- more stable than scraping web UI.

Suggested polling commands:
- `ndmc -c 'show system'`
- `ndmc -c 'show interface'`
- `ndmc -c 'show ip route'`
- `ndmc -c 'show ip policy'`
- `ndmc -c 'show log'` (as needed)
- `ndmc -c 'components list'`

Mutating commands depend on your firmware build — use `ndm/help.txt` from the bundle to build a safe, supported list.

### 2) Unified Entware service management

Entware services are typically controlled via `/opt/etc/init.d/*`.

A practical unified API:
- `list` → scan `S??*` scripts
- `start/stop/restart <svc>` → call init script
- `status <svc>` → use `status` if supported, otherwise `ps` fallback
- `logs` → tail `/opt/var/log/*` + `ndmc show log`

This repo includes a tiny helper `entwarectl`.

### 3) Event hooks & Telegram notifications

OPKG component fires scripts in `.../*.d` hook directories:
- `wan.d`, `ifstatechanged.d`, `ifipchanged.d`, `ifip6changed.d`
- `netfilter.d` (iptables refresh)
- `usb.d`, `time.d`, `schedule.d`, `button.d`, etc.

**Best practice notification flow:**
1) Hook scripts should NOT talk directly to Telegram (tokens/network/timeouts).
2) Hook scripts write JSON events to a spool directory:
   - `/opt/var/spool/keenetic-events/<ts>-<event>.json`
3) Telegram bot consumes the spool and sends messages.

### 4) Web/RCI API (optional)

The probe hits `/auth` and `/rci/` on discovered addresses/ports.

If you see `403 insufficient security level`, it commonly means:
- HTTPS (443) is required instead of HTTP (80), and/or
- authentication is required with proper session security.

Even if RCI is available, `ndmc` is usually the best backend for an on-router bot.

