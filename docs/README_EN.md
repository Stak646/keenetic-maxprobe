# keenetic-maxprobe — documentation (EN)

## What it is

`keenetic-maxprobe` is a **zero-config** script that collects maximum diagnostics from KeeneticOS + Entware (OPKG) directly on the router:

- Linux/kernel/hardware/memory/disk/mount information;
- network state (ip/route/rules/neighbours/listening ports);
- firewall/NAT dumps (`iptables-save`, `ip6tables-save`);
- KeeneticOS data via `ndmc`:
  - `show version`, `show system`, `show interface`, `show ip route`, `show ip policy`;
  - `running-config` and `startup-config` (in **sanitized** form);
  - `show log`;
  - `components list`, `show service`, `show users`, `help`;
- Entware/OPKG:
  - `opkg list-installed`, `opkg status`;
  - `/opt/etc` tree, `/opt/etc/init.d` init scripts list, `/opt/var/log` presence;
- OPKG↔Keenetic integration hooks: everything under `/opt/etc/ndm/*`;
- local management HTTP endpoint probing (**no login**) on common ports:
  - `/auth`, `/rci/`, `/ci/startup-config.txt`, `/ci/self-test.txt`.

The result is a folder plus a `.tar.gz` bundle you can review/share.

## Security note

- The script is read-only (no config changes).
- By default, it **redacts secrets** (passwords/keys/tokens/private keys).
- Still, review the archive before sharing.

## Requirements

- SSH / CLI access enabled.
- Entware OPKG installed (KeeneticOS OPKG component).
- Internet access from router is recommended (for `opkg` installs), but not strictly required.

## Install & run

### Option 1: One-liner (after you push the repo to GitHub)

```sh
sh -c "$(wget -qO- https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```

or

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```

Installer steps:
1) installs dependencies via `opkg` (best-effort);
2) installs `/opt/bin/keenetic-maxprobe`;
3) runs the collector and prints the output archive path.

### Option 2: Manual

1) Copy `scripts/keenetic-maxprobe.sh` to router as `/opt/bin/keenetic-maxprobe`.
2) Make it executable:

```sh
chmod +x /opt/bin/keenetic-maxprobe
```

3) Run:

```sh
/opt/bin/keenetic-maxprobe
```

## Output location

The script auto-selects a base directory (prefers `/opt/var/tmp`, `/opt/tmp`, then `/tmp`).

You will get:
- Folder: `keenetic-maxprobe-<hostname>-<timestamp>/`
- Archive: `keenetic-maxprobe-<hostname>-<timestamp>.tar.gz`
- Optional checksum: `.sha256`

## What to share for next steps

Best is the full `...tar.gz`. If it’s too large, share at least:
- `SUMMARY.txt`
- `ndm/show_version.txt`
- `ndm/show_system.txt`
- `ndm/show_running-config.txt`
- `ndm/show_log.txt`
- `entware/opkg_list_installed.txt`
- `hooks/opt_etc_ndm_tree.txt`
- `api/http_probe.txt`

## Typical next steps (Telegram bot)

After reviewing the bundle you can usually:
- map `ndmc`/CLI commands to bot features;
- use `/opt/etc/ndm/*` event hooks to push Telegram notifications;
- unify Entware service control (start/stop/restart/status);
- confirm which HTTP endpoints exist and on which ports (`/auth`, `/rci/`).

