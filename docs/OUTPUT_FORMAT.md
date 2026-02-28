# Output format / Формат архива

This document is bilingual (RU/EN).  
Документ двуязычный (RU/EN).

---

## 1) Название архива / Archive naming

Архив создаётся в выходной директории (`OUTDIR` или авто‑выбор):

- `keenetic-maxprobe-<hostname>-<pid>-<UTC>.tar.gz`
- `keenetic-maxprobe-<hostname>-<pid>-<UTC>.tar.gz.sha256`

---

## 2) Структура каталогов / Directory layout

Top-level inside the archive / Внутри архива:

- `meta/` — tool metadata + logs (важнейшее)
- `analysis/` — reports + sensitive maps
- `fs/` — filesystem mirror (configs etc.)
- `ndm/` — `ndmc` command outputs (KeeneticOS)
- `entware/` — Entware / OPKG inventory
- `net/` — networking snapshots + quick probes
- `web/` — extended web UI / HTTP surface probe (full/extream)
- `sys/` — system snapshots (`/proc`, `ps`, `top`, `dmesg`, mounts, df)
- `tmp/` — internal helper files (may be empty after cleanup)

---

## 3) fs/ — как читать зеркало файловой системы / how to read FS mirror

`fs/` сохраняет ОРИГИНАЛЬНЫЕ пути.

Примеры:
- оригинальный `/etc/passwd` → `fs/etc/passwd`
- оригинальный `/opt/etc/init.d/S80nginx` → `fs/opt/etc/init.d/S80nginx`
- оригинальный `/storage/etc/ndm/wan.d/10-hook` → `fs/storage/etc/ndm/wan.d/10-hook`

Это ключевой принцип: **по пути в `fs/` всегда понятно, где файл лежал на роутере**.

---

## 4) meta/ — логи и метрики / logs & metrics

- `meta/run.log` — основной лог выполнения (шаги + команды)
- `meta/errors.log` — ошибки/варнинги (с timestamps)
- `meta/profile_selected.json` — выбранные профиль/режим/лимиты/архитектура
- `meta/metrics.tsv` — CPU/RAM метрики по времени (если включено)
- `meta/phase.txt` — последняя фаза (для анимации)

Если инструмент «вроде завис» — первым делом смотрите `meta/run.log`.

---

## 5) analysis/ — отчёт и работа с чувствительными / report & redaction

- `analysis/REPORT_RU.md` — основной отчёт (RU)
- `analysis/REPORT_EN.md` — основной отчёт (EN)
- `analysis/SENSITIVE_LOCATIONS.md` — карта мест, где могут быть секреты (без значений)
- `analysis/REDACTION_GUIDE_RU.md` — как скрывать данные (RU)
- `analysis/REDACTION_GUIDE_EN.md` — how to redact (EN)

---

## 6) net/ и web/ — API endpoints / RCI / web UIs

- `net/http_probe.tsv` — быстрый probe (коды ответов) по `/`, `/rci/...` и т.п.
- `net/listen_*` — список слушающих портов (best-effort)
- `web/` — расширенный сбор: заголовки и небольшие фрагменты ответов по найденным портам.

Подсказка:
- `200/30x` → endpoint реально отвечает
- `401/403` → endpoint существует, но требует аутентификацию
- `000` → нет соединения/не тот протокол/порт закрыт/привязка только к localhost

---

## 7) ndm/ — KeeneticOS (ndmc)

Содержит результаты `ndmc -c 'show ...'`:
- `ndmc_show_version.txt`
- `ndmc_show_system.txt`
- `ndmc_show_interface.txt`
- `ndmc_show_running_config.txt` (в forensic/extream)
- и т.п.

Это база для «карты» состояний и команд для будущего Telegram‑бота.

---

## 8) entware/ — OPKG + init.d

- `entware/opkg/*` — версия opkg, список пакетов, status
- `entware/init.d/*` — список init скриптов
- `entware/services.json` — нормализованный список Entware‑служб (для бота)

---

## 9) sys/ — системные снимки

- `sys/proc/*` — ключевые файлы `/proc`
- `sys/ps.txt`, `sys/top.txt`
- `sys/dmesg.txt`
- `sys/mount.txt`, `sys/df.txt`

---

