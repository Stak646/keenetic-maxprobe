# Формат результатов / Output format

## Корень архива
`keenetic-maxprobe-<HOST>-<UTC>.tar.gz`

Внутри:
- `analysis/` — отчёты, индексы, чувствительные места
- `meta/` — метаданные, версия, окружение, список установленных/удалённых пакетов
- `ndm/` — вывод `ndmc` (если доступен)
- `entware/` — OPKG, init.d, логи
- `net/` — сеть, firewall
- `sys/` — информация о системе, /proc, /sys, исполняемые файлы
- `fs/` — **зеркало файловой системы (конфиги/управляющие файлы)**

## Важное правило путей
Любой файл в `fs/` соответствует исходному абсолютному пути:

`fs/<ABS_PATH_WITHOUT_LEADING_SLASH>`

Пример:
- `fs/etc/crontab` -> `/etc/crontab`
- `fs/opt/etc/init.d/S80lighttpd` -> `/opt/etc/init.d/S80lighttpd`

## Индексы
- `analysis/INDEX_ALL_FILES.txt` — все файлы в fs
- `analysis/INDEX_CONFIG_FILES.txt` — конфиги и похожие файлы
- `analysis/INDEX_INTERACTION_FILES.txt` — “точки управления”
- `analysis/INDEX_HOOK_SCRIPTS.txt` — ndm hooks
- `analysis/INDEX_INITD_SCRIPTS.txt` — Entware init scripts

## Sensitive locations
`analysis/SENSITIVE_LOCATIONS.md` — куда смотреть, чтобы скрыть секреты перед отправкой.
