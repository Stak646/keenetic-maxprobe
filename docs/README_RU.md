# keenetic-maxprobe — документация (RU)

## Что делает инструмент

`keenetic-maxprobe` собирает “снимок” состояния системы для диагностики:

- системные данные (`/proc`, `df`, `mount`, `ps`, `dmesg`, …)
- конфиги KeeneticOS (`/etc`, `/storage/etc`, `/storage/system`)
- Entware/OPKG (если установлено): списки пакетов, конфиги, init.d
- сеть: ip/route/neigh, слушающие порты, HTTP/RCI probe
- (опционально) расширенный web-probe (в режиме `full/extream`)
- `ndmc show ...` (версия, системная инфа, интерфейсы, сервисы, маршруты)
- анализ и отчёт: `analysis/REPORT_RU.md`, `analysis/REPORT_EN.md`
- карты чувствительных мест/паттернов: `analysis/SENSITIVE_*`

## Режимы (mode)

- `safe` — best-effort удаление самых чувствительных файлов (например, `shadow`), но **не гарантия**.
- `full` — полноценный сбор (по умолчанию).
- `extream` — максимально глубокий сбор (deep mirror), может быть тяжёлым.

## Профили (profile)

- `auto` — выбирается по CPU/RAM
- `lite` — минимально (слабые роутеры)
- `diagnostic` — баланс
- `forensic` — глубже и больше данных

## Каталог вывода

Инструмент работает через workdir: `keenetic-maxprobe-*.work`, затем упаковывает в `keenetic-maxprobe-*.tar.gz`.

Выбор каталога задаётся:

- `OUTBASE_POLICY=auto|ram|entware`
- `--outbase <DIR>` для принудительного выбора

Почему это важно: `/var/tmp` обычно RAM (быстро, безопаснее для NAND), но может не хватить места; USB/внутренняя память через `/opt/var/tmp` может быть более вместительной.

## Web UI

Запуск вручную:

```sh
keenetic-maxprobe --web --web-bind 0.0.0.0 --web-port 8088
```

Открыть:

`http://<ip>:8088/?token=<TOKEN>`

Токен хранится в `/opt/etc/keenetic-maxprobe.conf` (`WEB_TOKEN`).

## Где искать проблемы

- `meta/run.log` — подробный лог
- `meta/errors.log` — ошибки/предупреждения
- `meta/commands.tsv` — какие команды выполнялись, rc, длительность
- `analysis/python_analyze_stderr.txt` — если python-анализ упал

