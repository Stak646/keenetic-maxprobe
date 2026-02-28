# Output format

Архив `keenetic-maxprobe-<HOST>-<UTC>.tar.gz` содержит:

## fs/
Копии файлов, путь совпадает с исходным абсолютным путём.
Пример: `fs/opt/etc/...` соответствует `/opt/etc/...`.

## ndm/
Дампы `ndmc` (если доступно).

## entware/
OPKG (installed/status), список файлов пакетов, init.d, логи.

## net/
Сеть/порты/маршруты/sysctl/firewall (iptables/nft), probe HTTP/HTTPS.

## analysis/
Отчёты RU/EN, индексы, `SENSITIVE_LOCATIONS.md`.

## meta/
`files_manifest.tsv` (sha256/права/mtime/размер/путь), версии, окружение.
