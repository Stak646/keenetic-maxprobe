# keenetic-maxprobe — Documentation (EN)

## What is it?

`keenetic-maxprobe` is a **maximum‑coverage** diagnostic & research tool for **KeeneticOS + Entware (OPKG)**. It helps you:
- capture configs / hooks / services / API visibility for deep troubleshooting;
- build a reproducible “snapshot” for backup and bug hunting;
- prepare ground truth for a Telegram bot that controls the router and Entware apps.

Best‑effort design: if a command/binary is missing, the step is skipped but recorded in the report.

## Sensitive data warning

Default mode is `FULL`, which may include:
- passwords, tokens, private keys, certificates,
- PPPoE credentials, Wi‑Fi PSKs, etc.

The tool does **not** redact automatically, but:
- writes `analysis/SENSITIVE_LOCATIONS.md` with **exact locations** to hide before sharing;
- `--mode safe` attempts to reduce the most sensitive captures (still not a 100% guarantee).

Before sending an archive:
1) check `analysis/SENSITIVE_LOCATIONS.md`;
2) mask secrets;
3) optionally re-pack.

## Installation (one‑liner)

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/Stak646/keenetic-maxprobe/main/scripts/install.sh)"
```

After install:
- binary: `/opt/bin/keenetic-maxprobe`
- collectors: `/opt/share/keenetic-maxprobe/collectors`

## Usage

Default run:
```sh
keenetic-maxprobe
```

Init wizard (writes `/opt/etc/keenetic-maxprobe.conf`):
```sh
keenetic-maxprobe --init
```

Examples:
```sh
keenetic-maxprobe --profile forensic --mode full
keenetic-maxprobe --profile diagnostic --mode safe
keenetic-maxprobe --no-cleanup
```

## Profiles (including auto)

- `auto` — automatically selects a profile based on CPU/RAM.
- `diagnostic` — faster, lighter.
- `forensic` — maximum snapshot (recommended for deep bug hunting).

## Resource protection

Best‑effort throttling:
- lower priority for heavy tasks (`nice` where available),
- adaptive backoff if estimated CPU/RAM exceed limits:
  - CPU: ~85%
  - RAM: ~95%

If the router is already busy due to other processes, the tool will wait.

## Output

Archive name:
`keenetic-maxprobe-<HOST>-<UTC_TIMESTAMP>.tar.gz`

Structure is described in `docs/OUTPUT_FORMAT.md`.

## Telegram notifications (recommended approach)

Keenetic OPKG provides event hooks in `/opt/etc/ndm/*.d/` (WAN up/down, IP change, netfilter reload, etc.).
Recommended:
- hook scripts must be **fast** (avoid blocking / timeouts);
- write events to a queue, send Telegram messages from a separate Entware daemon.

The report enumerates detected hook directories and generates a proposed notification schema.

References:
- https://support.keenetic.com (OPKG component description)
- https://help.keenetic.com (HTTP Proxy / RCI)

## Entware services unified control

`scripts/entwarectl` is a tiny unified control layer for Entware init scripts:
- list services,
- start/stop/restart/status,
- logs (if available).

## What to share for analysis

Usually enough:
- `analysis/REPORT_EN.md`
- `analysis/SENSITIVE_LOCATIONS.md`
- `meta/run.log`
- `meta/errors.log`
