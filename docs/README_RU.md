# Документация (RU)

## Назначение

`keenetic-maxprobe` нужен для:
- поиска доступных интерфейсов управления KeeneticOS (CLI `ndmc` и web/RCI);
- инвентаризации Entware (opkg, init-скрипты, конфиги, логи);
- поиска реальных **event hook’ов** OPKG-компонента (`/opt/etc/ndm/*.d`, `/storage/etc/ndm/*.d`);
- формирования “карты” команд/состояний, которые лучше дергать из Telegram-бота.

## Запуск

После установки Entware:

```sh
/opt/bin/keenetic-maxprobe
```

На выходе — путь к архиву `...tar.gz`. Его и присылай для анализа.

## Формат вывода

- `ndm/` — результаты `ndmc`
- `entware/` — opkg + entware дерево + init.d
- `hooks/` — деревья hook’ов и дампы скриптов
- `fs/` — списки конфигов + метаданные + дампы (<=512KiB)
- `net/` — ip/route/rules, iptables/ipset, netstat
- `api/` — probe web/RCI эндпойнтов (без логина)
- `analysis/` — авто-отчёты + JSON

## Как из этого строится Telegram-бот (архитектура)

### 1) “Единый слой” управления KeeneticOS

**Рекомендовано:** бот работает на роутере и вызывает `ndmc`:
- не нужно хранить пароль администратора;
- стабильнее, чем разбирать web интерфейс.

Базовые polling-команды:
- `ndmc -c 'show system'`
- `ndmc -c 'show interface'`
- `ndmc -c 'show ip route'`
- `ndmc -c 'show ip policy'`
- `ndmc -c 'show log'` (по требованию)
- `ndmc -c 'components list'`

Команды для изменения состояния зависят от сборки — их лучше выбирать после анализа `ndm/help.txt`.

### 2) Управление Entware-службами

В Entware ключевая точка управления — `/opt/etc/init.d/*`.

Идея единого слоя:
- `list` → скан `S??*` в `/opt/etc/init.d`
- `start/stop/restart <svc>` → запуск init-скрипта
- `status <svc>` → `status` если поддерживается, иначе fallback на `ps`
- `logs` → хвост `/opt/var/log/*` + `ndmc show log`

Для удобства в репозитории есть helper `entwarectl`.

### 3) Event hooks и уведомления в Telegram

OPKG-компонент запускает скрипты в директориях вида `.../*.d` при событиях:
- `wan.d`, `ifstatechanged.d`, `ifipchanged.d`, `ifip6changed.d`
- `netfilter.d` (пересборка правил iptables)
- `usb.d`, `time.d`, `schedule.d`, `button.d`, и т.д.

**Правильная схема для уведомлений:**

1) Hook-скрипты НЕ должны напрямую отправлять в Telegram (там токены/сети/таймауты).
2) Hook-скрипт пишет событие в spool:
   - `/opt/var/spool/keenetic-events/<ts>-<event>.json`
3) Telegram-бот читает spool и отправляет.

События, которые почти всегда нужны:
- WAN up/down
- смена IPv4/IPv6 адреса
- netfilter refresh (firewall события)
- подключение USB
- изменения туннелей (OpkgTun и т.п.)

### 4) Web/RCI API (если включено)

`keenetic-maxprobe` делает probe `/auth` и `/rci/` на обнаруженных адресах/портах.

Если probe показывает `403 insufficient security level`, обычно это означает:
- нужен HTTPS (443) вместо HTTP (80), либо
- требуется аутентификация с правильным “уровнем безопасности” сессии.

Даже если RCI включён, для бота на роутере чаще проще использовать `ndmc`.

