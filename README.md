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


### Web UI
```sh
keenetic-maxprobe --web
```

По умолчанию Web UI слушает `127.0.0.1:8088`. Чтобы открыть из LAN:
```sh
keenetic-maxprobe --web --web-bind 0.0.0.0 --web-port 8088
```

### Важно про вывод (v0.7.0+)
Начиная с **v0.7.0** все файлы/архив создаются в **`/var/tmp`**, а `/var/tmp` исключён из копирования/исследования, чтобы исключить баги с самосканированием и «раздуванием» отчётов.


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
