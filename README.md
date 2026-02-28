# keenetic-maxprobe

Максимально «жадный» инструмент диагностики и исследования **KeeneticOS + Entware (OPKG)**.

Цели:
- собрать максимум технической информации (файлы конфигов, хуки, сервисы, API/RCI, процессы, сеть, маршрутизация);
- сформировать **архив‑слепок** для отладки/бэкапа (в т.ч. для будущего Telegram‑бота);
- выдать **очень подробный лог** и отдельный список мест с потенциально чувствительными данными.

> По умолчанию: **FULL** (в архив попадают конфиги и потенциально секретные данные).  
> SAFE доступен отдельным флагом.

## Быстрый старт (на роутере)

### Установка (one‑liner)
```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/Stak646/keenetic-maxprobe/main/scripts/install.sh)"
```

Если нет `curl`:
```sh
sh -c "$(wget -qO- https://raw.githubusercontent.com/Stak646/keenetic-maxprobe/main/scripts/install.sh)"
```

### Запуск (авто‑профиль, FULL)
```sh
keenetic-maxprobe
```

### Мастер настройки (опционально)
```sh
keenetic-maxprobe --init
```

### Максимально глубокий снимок (без ограничений по чувствительным данным)
```sh
keenetic-maxprobe --mode extream
```

### SAFE (минимизация секретов в зеркале)
```sh
keenetic-maxprobe --mode safe
```

## Где смотреть результат
См. `docs/OUTPUT_FORMAT.md`.

## Документация
- RU: `docs/README_RU.md`
- EN: `docs/README_EN.md`
- Формат отчёта: `docs/OUTPUT_FORMAT.md`
- Security / sensitive: `docs/SECURITY.md`
- Git cleanup: `docs/GIT_CLEANUP.md`

## Лицензия
MIT, см. `LICENSE`.
