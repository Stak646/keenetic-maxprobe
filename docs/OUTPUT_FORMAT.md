# Output format

Архив содержит workdir-структуру:

- `meta/` — метаданные и логи
  - `tool_version.txt`
  - `started_utc.txt`
  - `profile_selected.json`
  - `run.log`
  - `errors.log`
  - `commands.tsv`
  - `metrics.tsv`, `metrics_current.tsv`
  - `opkg_storage_hint.txt`, `opkg_mount_source.txt`, `opkg_fs_type.txt`
- `sys/` — системные команды и `/proc`
- `fs/` — зеркала конфигов и (опционально) deep mirror
- `entware/` — инвентарь opkg и init.d
- `net/` — сеть, слушающие порты, HTTP probe
- `web/` — (full/extream) тела/хедеры web-ответов
- `ndm/` — выводы `ndmc show ...`
- `analysis/` — отчёты и гайды
  - `REPORT_RU.md`, `REPORT_EN.md`
  - `SENSITIVE_LOCATIONS.md`
  - `SENSITIVE_PATTERNS.tsv`
  - `REDACTION_GUIDE_RU.md`, `REDACTION_GUIDE_EN.md`
  - (если python-анализатор) `summary.json`

