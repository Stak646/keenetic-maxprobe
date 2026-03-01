# Changelog

## 0.8.0

- Исправлено критичное: **отчёт снова гарантированно генерируется** (`analysis/REPORT_RU.md`, `analysis/REPORT_EN.md`).
- Синхронизированы интерфейсы shell ↔ python:
  - `collectors/py/analyze.py` принимает `--workdir`, пишет отчёты/summary.
- Переписан Web UI (HTML/CSS/JS) — доступность, понятные параметры, запуск с разными аргументами.
- Улучшено определение, где находится Entware (/opt): USB vs internal → `meta/opkg_storage_hint.txt`.
- Детальный лог команд: `meta/commands.tsv`.
- Метрики CPU/RAM/Load: `meta/metrics.tsv`, `meta/metrics_current.tsv`.
- Политика каталога вывода: `OUTBASE_POLICY=auto|ram|entware`, поддержка `--outbase`.

## 0.7.0

- Первичная Web UI (добавлена ранее).
- Переезд вывода в `/var/tmp` (исторически).

