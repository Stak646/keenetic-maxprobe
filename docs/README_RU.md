# keenetic-maxprobe — документация (RU)

## Что это

`keenetic-maxprobe` — скрипт, который **без настроек** собирает максимально подробную диагностику с KeeneticOS и Entware (OPKG) прямо на роутере:

- системная информация Linux/ядро/память/диски/монтирования;
- сетевое состояние (ip/маршруты/правила/соседи/порты);
- firewall/NAT дампы (`iptables-save`, `ip6tables-save`);
- KeeneticOS данные через `ndmc`:
  - `show version`, `show system`, `show interface`, `show ip route`, `show ip policy`;
  - конфиги `running-config` и `startup-config` (в **санитизированном** виде);
  - `show log`;
  - `components list`, `show service`, `show users`, `help`;
- Entware/OPKG:
  - `opkg list-installed`, `opkg status`;
  - дерево `/opt/etc`, список init-скриптов `/opt/etc/init.d`, наличие логов `/opt/var/log`;
- «хуки»/интеграции OPKG↔Keenetic (скрипты событий) — всё из `/opt/etc/ndm/*`;
- проба локальных веб-эндпойнтов управления (**без логина/пароля**) на типовых портах:
  - `/auth`, `/rci/`, `/ci/startup-config.txt`, `/ci/self-test.txt`.

На выходе создаётся папка с файлами и **архив `.tar.gz`**, который удобно передавать для анализа.

## Важно про безопасность

- Скрипт **не пытается взламывать** роутер и не делает действий, меняющих конфигурацию.
- Скрипт **по умолчанию редактирует (redact) секреты**: пароли, ключи, токены, приватные ключи.
- Всё равно рекомендуется **пробежать глазами** по архиву перед тем, как отправлять кому-либо.

## Требования

- Включён SSH/доступ к CLI.
- Установлен OPKG/Entware (обычно это компонент KeeneticOS «OPKG»).
- Желательно (но не обязательно): доступ в Интернет с роутера для установки зависимостей через `opkg`.

## Установка и запуск

### Вариант 1: One‑liner (после того как вы зальёте репозиторий на GitHub)

```sh
sh -c "$(wget -qO- https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```

или

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```

Инсталлятор:
1) попробует поставить зависимости через `opkg`;
2) установит `/opt/bin/keenetic-maxprobe`;
3) запустит сбор и выведет путь к архиву.

### Вариант 2: ручной запуск

1) Скопируйте `scripts/keenetic-maxprobe.sh` на роутер, например в `/opt/bin/keenetic-maxprobe`.
2) Сделайте исполняемым:

```sh
chmod +x /opt/bin/keenetic-maxprobe
```

3) Запустите:

```sh
/opt/bin/keenetic-maxprobe
```

## Где лежит результат

Скрипт выбирает базовую директорию автоматически (приоритетно что-то из `/opt/var/tmp`, `/opt/tmp`, затем `/tmp`).

Результат:
- Папка вида: `keenetic-maxprobe-<hostname>-<timestamp>/`
- Архив: `keenetic-maxprobe-<hostname>-<timestamp>.tar.gz`
- Рядом (если доступен `sha256sum`): `.sha256`

## Как предоставить лог для дальнейших действий

Минимально полезный набор:
- сам архив `...tar.gz`
- или (если архив большой) хотя бы:
  - `SUMMARY.txt`
  - `ndm/show_version.txt`
  - `ndm/show_system.txt`
  - `ndm/show_running-config.txt`
  - `ndm/show_log.txt`
  - `entware/opkg_list_installed.txt`
  - `hooks/opt_etc_ndm_tree.txt`
  - `api/http_probe.txt`

## Типичные дальнейшие шаги (для Telegram‑бота)

После анализа лога обычно можно:
- сформировать карту команд `ndmc`/CLI для нужных функций;
- выделить «событийные хуки» в `/opt/etc/ndm/*` и использовать их для нотификаций в Telegram;
- собрать список служб Entware и унифицировать управление ими (start/stop/restart/status);
- определить какие веб‑эндпойнты реально активны (`/rci/`, `/auth`) и на каких портах.

