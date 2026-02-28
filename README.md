# keenetic-maxprobe

Максимально «жадный» инструмент диагностики и исследования **KeeneticOS + Entware (OPKG)**.

Цели:
- собрать максимум технической информации (файлы конфигураций, хуки, сервисы, API/RCI‑доступ, процессы, сеть, маршрутизация);
- сформировать **архив‑слепок** для отладки и бэкапа (в т.ч. для будущего Telegram‑бота);
- выдать **очень подробный лог** и отдельный список мест с потенциально чувствительными данными.

По умолчанию: **FULL** (включая чувствительные данные). Инструмент **ничего не редактирует** — только читает и копирует.

## Быстрый старт (на роутере)

### Установка (one‑liner)

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/Stak646/keenetic-maxprobe/main/scripts/install.sh)"
```

или

```sh
sh -c "$(wget -qO- https://raw.githubusercontent.com/Stak646/keenetic-maxprobe/main/scripts/install.sh)"
```

### Инициализация (опционально)

```sh
keenetic-maxprobe --init
```

### Запуск (по умолчанию, авто‑профиль)

```sh
keenetic-maxprobe
```

### Максимально глубокий снимок

```sh
keenetic-maxprobe --profile forensic --mode full
```

### SAFE (минимизация секретов)

```sh
keenetic-maxprobe --mode safe
```

## Где смотреть результат

См. `docs/OUTPUT_FORMAT.md`.

## Документация

- RU: `docs/README_RU.md`
- EN: `docs/README_EN.md`
- Output format: `docs/OUTPUT_FORMAT.md`
- Security / sensitive data: `docs/SECURITY.md`
- Git cleanup: `docs/GIT_CLEANUP.md`

## Лицензия

MIT, см. `LICENSE`.
