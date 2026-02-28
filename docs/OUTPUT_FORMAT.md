# Output format

The probe produces a single archive:

`keenetic-maxprobe-<HOST>-<UTC_TIMESTAMP>.tar.gz`

Inside the archive there is a folder (root of the tar) with these top-level directories:

## `meta/` — run metadata & debug logs

- `meta/run.log` — human-readable main log (phases, errors, what was skipped).
- `meta/errors.log` — condensed error list (command, exit code, file path).
- `meta/timings.tsv` — timings table: start/end/duration per step.
- `meta/metrics.tsv` — periodic CPU/RAM snapshot during the run.
- `meta/profile_selected.json` — detected device profile and chosen strategy.
- `meta/opkg_installed_before.txt` / `after.txt` / `added_by_probe.txt` — dependency tracking (what was installed temporarily).

## `analysis/` — generated reports

- `analysis/REPORT_RU.md` — main report (RU).
- `analysis/REPORT_EN.md` — main report (EN).
- `analysis/SENSITIVE_LOCATIONS.md` — exact locations of potential secrets to hide before sharing.

## `sys/` — runtime/system snapshots

OS/kernel/proc snapshots:
- `sys/proc/*` — selected `/proc` files (`cpuinfo`, `meminfo`, `loadavg`, `mounts`, `net/*`, etc).
- `sys/ps.txt`, `sys/top.txt` (if available), `sys/dmesg.txt`, `sys/df.txt`, `sys/mount.txt`, etc.

Collectors output:
- `sys/collectors/<collector>.txt` — outputs of optional language collectors (python/perl/lua/ruby/node/go).
- `sys/collectors/*.status` — why a collector was skipped.

## `ndm/` — KeeneticOS / ndmc / RCI snapshots

- `ndm/ndmc_*.txt` — outputs of selected `ndmc -c 'show ...'` commands.
- `ndm/rci_probe.txt` — HTTP probe results for `/rci/*` paths (status codes).

> If `ndmc` is not available, this directory may be partially empty.

## `entware/` — Entware / OPKG / services

- `entware/opkg/*` — `opkg` diagnostics: installed packages, config, feed info, files.
- `entware/init.d/` — listing of `/opt/etc/init.d` scripts and their metadata.
- `entware/services.json` — normalized inventory of services (for bot integration).

## `net/` — network probe

- `net/http_probe.txt` — HTTP status probes for common management ports/paths.
- `net/ss.txt` / `net/netstat.txt` — sockets list (best-effort).
- `net/ip_addr.txt`, `net/ip_route.txt` — IP addressing and routes (if `ip` exists).

## `fs/` — filesystem mirror (path-preserving)

This is the most important part for configs.

`fs/` mirrors selected config paths with the same absolute structure:

- original `/etc/...` -> `fs/etc/...`
- original `/opt/etc/...` -> `fs/opt/etc/...`
- original `/storage/etc/...` -> `fs/storage/etc/...`

So you can always understand where a copied file came from.

## `tmp/` — temporary debug artifacts

Only included if `--no-cleanup` was used (otherwise cleaned up).
