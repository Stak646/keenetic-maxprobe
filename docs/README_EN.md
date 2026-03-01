# keenetic-maxprobe — docs (EN)

`keenetic-maxprobe` collects a diagnostic snapshot from **KeeneticOS** routers (and **Entware/OPKG** if present), packs it into a `.tar.gz` archive and generates reports:

- `analysis/REPORT_RU.md`
- `analysis/REPORT_EN.md`

## Modes

- `safe` — best-effort redaction of most sensitive files (not a guarantee)
- `full` — default
- `extream` — deeper mirrors, heavier run

## Output base

Use:

- `OUTBASE_POLICY=auto|ram|entware`
- `--outbase <DIR>` to force output location (RAM vs Entware storage)

## Web UI

```sh
keenetic-maxprobe --web --web-bind 0.0.0.0 --web-port 8088
```

Open:

`http://<ip>:8088/?token=<TOKEN>`

Token is stored in `/opt/etc/keenetic-maxprobe.conf` (`WEB_TOKEN`).

