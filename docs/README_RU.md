# keenetic-maxprobe — документация (RU)

## Цель
Снять максимально полный «слепок» состояния **KeeneticOS + Entware**, включая:
- конфиги и файлы управления (hooks, init.d, cron),
- состояние сети/фаервола,
- список пакетов и файлы пакетов OPKG,
- NDM/CLI дампы через `ndmc` (если доступен),
- системные «снимки» `/proc`, `/sys` (в профиле `forensic`),
- инвентаризацию исполняемых файлов и интерпретаторов.

## Важно про чувствительные данные
По умолчанию режим `FULL`. Инструмент **не редактирует** файлы, чтобы сохранить точность бэкапа.

Чтобы пользователь мог вручную скрыть секреты перед отправкой, генерируется:
- `analysis/SENSITIVE_LOCATIONS.md` — список точных мест (путь + строка + тип) где встречаются секреты.

Если нужен автоматический редакт, используйте:
- `--mode safe`

## Профили
- `--profile forensic` (по умолчанию): максимум данных, включая расширенные дампы `/proc` и `opkg files` по всем пакетам.
- `--profile diagnostic`: более лёгкий, но всё равно полезный.

## Запуск
### Инициализация
```sh
keenetic-maxprobe --init
```
Спросит:
- очищать ли старые `keenetic-maxprobe-*` в папке вывода,
- очищать ли `/tmp` (опасно, по умолчанию нет).

### Запуск
```sh
keenetic-maxprobe
```

### Явно задать режим/профиль/коллекторы
```sh
keenetic-maxprobe --mode full --profile forensic --collectors all
keenetic-maxprobe --mode safe --profile diagnostic --collectors sh,python
```

## Где искать “точки управления”
- NDM hooks: `analysis/INDEX_HOOK_SCRIPTS.txt` и `fs/*/ndm/*`
- Entware init.d: `analysis/INDEX_INITD_SCRIPTS.txt` и `fs/opt/etc/init.d/*`
- OPKG файлы пакетов: `entware/opkg_files_all.txt`
- NDM дампы: `ndm/`
- Инвентарь исполняемых файлов: `sys/executables_inventory.tsv`

## Формат путей (самое важное)
В архиве есть папка `fs/`, которая **зеркалит абсолютные пути** исходной системы.

Пример:
- в архиве: `fs/opt/etc/ndm/netfilter.d/100-foo.sh`
- на роутере: `/opt/etc/ndm/netfilter.d/100-foo.sh`

См. `docs/OUTPUT_FORMAT.md`.
