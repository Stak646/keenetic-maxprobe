# keenetic-maxprobe — documentation (EN)

## Goal
Create a maximal snapshot of **KeeneticOS + Entware**:
- configs and control files (hooks, init.d, cron),
- network/firewall state,
- OPKG packages and `opkg files` mapping,
- NDM CLI dumps via `ndmc` (if available),
- `/proc` and `/sys` snapshots (in `forensic` profile),
- executable & interpreter inventory.

## Sensitive data
Default mode is `FULL` (no redaction).  
Instead we generate:
- `analysis/SENSITIVE_LOCATIONS.md` — exact locations (path + line + type) so you can manually hide secrets before sharing.

If you want automatic redaction:
- `--mode safe`

## Profiles
- `forensic` (default): maximum collection (incl. deep `/proc` and `opkg files` for all pkgs).
- `diagnostic`: lighter.

## Run
```sh
keenetic-maxprobe --init
keenetic-maxprobe
keenetic-maxprobe --mode safe --profile diagnostic --collectors sh,python
```

## Where to look for “control points”
- NDM hooks: `analysis/INDEX_HOOK_SCRIPTS.txt` and `fs/*/ndm/*`
- Entware init.d: `analysis/INDEX_INITD_SCRIPTS.txt` and `fs/opt/etc/init.d/*`
- OPKG file mapping: `entware/opkg_files_all.txt`
- NDM dumps: `ndm/`
- Executables inventory: `sys/executables_inventory.tsv`

## Path mapping
`fs/` mirrors absolute paths from the router:
`fs/opt/etc/ndm/...` => `/opt/etc/ndm/...`

See `docs/OUTPUT_FORMAT.md`.
