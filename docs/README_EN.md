# keenetic-maxprobe — documentation (EN)

## 1) What it is

`keenetic-maxprobe` creates a **forensic-style snapshot archive** of a Keenetic router (KeeneticOS) and Entware:
- configs (KeeneticOS / Entware),
- real `ndm` hook directories (OPKG),
- Entware services (`/opt/etc/init.d`),
- networking state (IP/route/rules/listening ports),
- RCI/HTTP endpoint probing (local + interface addresses),
- system info (`/proc`, `ps`, `top`, `dmesg`, `mount`, `df`),
- very detailed tool logs.

The tool **does not modify router configuration** (read/copy only).  
Exception: it may temporarily install packages via `opkg` (if enabled), then remove them (best-effort).

## 2) Modes and profiles

### MODE (depth + security)
- `full` (default): maximum data, may include sensitive information.
- `safe`: tries to remove some high-risk files from the mirrored FS (best-effort), still generates a sensitive map.
- `extream`: maximum depth **without limiting sensitive data** (deeper mirroring + more probes/endpoints).

> Any mode generates `analysis/SENSITIVE_LOCATIONS.md` (sensitive map).

### PROFILE (how heavy)
- `auto` (recommended): selected automatically based on CPU/RAM/free space.
- `forensic`: deepest snapshot (bigger & slower).
- `diagnostic`: balanced.
- `lite`: minimal.

## 3) Resource limits (CPU/RAM)

Default best-effort limits:
- CPU <= **85%**
- RAM <= **95%**

CPU is computed from `/proc/stat` (0–100%).  
Parallelism is used only for independent collectors.

## 4) Install

### One-liner
```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/Stak646/keenetic-maxprobe/main/scripts/install.sh)"
```

Installed paths:
- `/opt/bin/keenetic-maxprobe`
- `/opt/bin/entwarectl`
- `/opt/share/keenetic-maxprobe/collectors/*`

## 5) Run

### Default (FULL, auto profile)
```sh
keenetic-maxprobe
```

### Extreme run
```sh
keenetic-maxprobe --mode extream
```

### SAFE
```sh
keenetic-maxprobe --mode safe
```

### UI language
```sh
keenetic-maxprobe --lang ru   # default
keenetic-maxprobe --lang en
```

### Collector parallelism
```sh
keenetic-maxprobe --jobs auto
keenetic-maxprobe --jobs 2
```

### Resource limits
```sh
keenetic-maxprobe --max-cpu 85 --max-mem 95
```

### Init wizard (optional)
```sh
keenetic-maxprobe --init
```
Wizard saves `/opt/etc/keenetic-maxprobe.conf`.

## 6) Reading the archive

See `docs/OUTPUT_FORMAT.md`.

Main idea: **filesystem mirror** is stored under `fs/`:
- `/etc/...` → `fs/etc/...`
- `/opt/etc/...` → `fs/opt/etc/...`
- `/storage/...` → `fs/storage/...`

This keeps original paths obvious, good for backup/diff/restore.

## 7) Sensitive data & redaction

Generated files:
- `analysis/SENSITIVE_LOCATIONS.md` — list of files/lines where secrets may exist (without values).
- `analysis/REDACTION_GUIDE_EN.md` — what to hide before sharing.

In `full/extream`, the archive may contain:
- VPN passwords/keys,
- Wi-Fi PSK,
- bot tokens,
- credentials in service configs, etc.

Before sharing:
1) review `analysis/SENSITIVE_LOCATIONS.md`
2) redact in `fs/...`
3) repack or encrypt the archive.

## 8) Web UIs & API

The tool attempts to:
- detect listening ports,
- probe HTTP/HTTPS responses,
- store headers and a small body sample,
- infer which endpoints exist (200/401/403/404).

Outputs:
- `net/listen_*` (ports)
- `net/http_probe.tsv` (quick RCI/HTTP probe)
- `web/` (extended probe in full/extream)

## 9) ndm hooks & Telegram notifications

KeeneticOS can trigger scripts from `*/etc/ndm/*.d` (many OPKG packages add hooks in `/opt/etc/ndm/...`).

Recommended Telegram notification pattern:
1) hook writes an event to a spool file (e.g. `/opt/var/spool/kmp/events.ndjson`)
2) an Entware daemon reads spool and sends messages (rate-limit)
3) manage daemon via `entwarectl`.

## 10) Entware service control

`entwarectl` provides unified control for `/opt/etc/init.d`:
```sh
entwarectl list
entwarectl status <service>
entwarectl restart <service>
entwarectl enable <service>   # chmod +x
entwarectl disable <service>  # chmod -x
```

## 11) Troubleshooting

- **Low space**: use `--outdir /opt/var/tmp` or USB, enable `--clean-tmp`.
- **opkg install fails**: best-effort, check `meta/errors.log`.
- **No python3**: you'll still get raw data; do manual analysis in `fs/`, `ndm/`, `net/`.



## Web UI

In **v0.7.0**, a lightweight Web UI was added to run probes and view live status:

- shows **phase/progress**, **CPU/RAM/loadavg**, tail of the log,
- lists produced archives and provides download links.

Start:

```sh
keenetic-maxprobe --web
```

Default bind: `127.0.0.1:8088` (local to the router).

To expose in LAN (be careful: reports may contain sensitive data):

```sh
keenetic-maxprobe --web --web-bind 0.0.0.0 --web-port 8088
```

If Web UI fails because Python3 is missing:

```sh
opkg update
opkg install python3
```

