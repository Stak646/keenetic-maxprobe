# keenetic-maxprobe

Скрипт для максимального сбора диагностических данных с роутеров **KeeneticOS** (и **Entware/OPKG**, если установлен) с упаковкой в архив `.tar.gz` и автоматическим формированием отчёта.

## Быстрый старт

Установка (Entware/OPKG):

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/Stak646/keenetic-maxprobe/main/scripts/install.sh)"
```

После установки доступны:

- `keenetic-maxprobe` — основной сборщик
- `entwarectl` — небольшой помощник по Entware (опционально)
- Web UI: поднимается сервисом после установки (см. ниже)

## Web UI

По умолчанию Web UI **автоматически выбирает свободный порт** (WEB_PORT=0). Узнать выбранный порт:

- `cat /opt/var/run/keenetic-maxprobe-webui.port`
- `cat /opt/var/run/keenetic-maxprobe-webui.url`


После установки инсталлер:

1) ставит `python3` (если возможно),
2) пишет конфиг `/opt/etc/keenetic-maxprobe.conf`,
3) ставит init-скрипт `/opt/etc/init.d/S99keenetic-maxprobe-webui`,
4) запускает Web UI.

Открывайте:

- `http://<IP_роутера>:<PORT>/?token=<TOKEN>`

Токен хранится в конфиге (`WEB_TOKEN`) и обязателен для API.

## Ключевые флаги

- `--mode full|safe|extream`
- `--profile auto|forensic|diagnostic|lite`
- `--collectors all|shonly|shpy|custom`
- `--outbase-policy auto|ram|entware`
- `--outbase <DIR>` — принудительно выбрать каталог вывода (если нужен USB/внутренняя память вместо RAM)
- `--web` — запустить Web UI вручную

## Важно про Entware (/opt) и хранилище

Entware всегда монтируется в `/opt`, но физически может быть:

- **USB флешка / HDD** (часто `/dev/sdX`)
- **внутренняя память** (часто `ubifs`, `ubi*`, `/storage*`)

`keenetic-maxprobe` сохраняет это в `meta/opkg_storage_hint.txt` и отражает в отчёте.

## Документация

- `docs/README_RU.md`
- `docs/README_EN.md`
- `docs/OUTPUT_FORMAT.md`
- `docs/SECURITY.md`

## Лицензия

MIT (см. `LICENSE`).
