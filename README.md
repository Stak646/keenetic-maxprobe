# keenetic-maxprobe

**keenetic-maxprobe** — инструмент “без настроек”, который делает максимально подробный снимок состояния **KeeneticOS + Entware**:
- инвентаризация конфигов и структуры `/etc`, `/storage/etc`, `/opt/etc`, `/opt/var` (с ограничением размера файлов);
- обнаружение и дамп **OPKG/ndm event hook’ов** (`/opt/etc/ndm/*.d`, `/storage/etc/ndm/*.d`);
- сбор сетевого состояния (ip/route/rules/neigh, iptables/ipset, слушающие порты);
- сбор данных KeeneticOS через `ndmc` (если доступен): версия, system, интерфейсы, маршруты, политики, логи, компоненты, конфиги;
- проба **management API** эндпойнтов (`/auth`, `/rci/`, `/ci/self-test.txt`, ...) на **всех обнаруженных локальных IPv4** и популярных портах;
- генерация **отчёта** RU/EN в `analysis/REPORT_*.md`.

По умолчанию **секреты редактируются** (password/token/key/Authorization/private keys).

## Быстрый запуск (после публикации в GitHub)

```sh
sh -c "$(wget -qO- https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```

или

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```

> В `install.sh` есть placeholder `<YOU>/<REPO>` — замени на свой репозиторий, либо выставь env `KMP_RAW_BASE`.

## Запуск вручную

```sh
chmod +x bin/keenetic-maxprobe
./bin/keenetic-maxprobe
```

На роутере (Entware):
```sh
cp bin/keenetic-maxprobe /opt/bin/
cp bin/keenetic-maxprobe-analyze /opt/bin/
chmod +x /opt/bin/keenetic-maxprobe /opt/bin/keenetic-maxprobe-analyze
/opt/bin/keenetic-maxprobe
```

На выходе будет путь к архиву `...tar.gz`.

## Где смотреть результаты

- `SUMMARY.txt` — кратко
- `analysis/REPORT_RU.md` и `analysis/REPORT_EN.md` — вывод “что дальше делать”
- `api/http_probe.txt` — ответы по эндпойнтам (без логина)
- `hooks/*_tree.txt` — деревья hook’ов
- `ndm/*.txt` — вывод `ndmc`
- `entware/*.txt` — OPKG/Entware

## Security

Инструмент специально не снимает «голые» токены/пароли (они маскируются).
Если тебе нужно отключить редактирование — **не делай этого в логах, которые отправляешь третьим лицам**.

## License

MIT.
