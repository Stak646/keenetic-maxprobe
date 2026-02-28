# keenetic-maxprobe

Максимально «жадный» инструмент диагностики и исследования **KeeneticOS + Entware (OPKG)**.

- **По умолчанию:** `FULL` (с чувствительными данными) — подходит для локального бэкапа/восстановления.
- Профили:
  - `diagnostic` — быстрее, меньше шума.
  - `forensic` — максимально глубокий слепок (по умолчанию).
- Режимы:
  - `full` — ничего не редактирует, но генерирует `analysis/SENSITIVE_LOCATIONS.md` (где искать секреты).
  - `safe` — дополнительно делает редактированные копии части текстовых файлов.
- Коллекторы (best-effort): `sh` (core) + `python` + `perl` + `lua` + `ruby` + `node` + `go` (если доступно/установлено).

См. документацию:
- RU: `docs/README_RU.md`
- EN: `docs/README_EN.md`
- Формат архива: `docs/OUTPUT_FORMAT.md`
- Безопасность: `docs/SECURITY.md`
- Как удалить лишнее из Git/истории: `docs/GIT_CLEANUP.md`

## Быстрый старт (на роутере)

### Установка (one-liner)
```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/Stak646/keenetic-maxprobe/main/scripts/install.sh)"
```
или
```sh
sh -c "$(wget -qO- https://raw.githubusercontent.com/Stak646/keenetic-maxprobe/main/scripts/install.sh)"
```

### Инициализация (спросит про очистку OUTDIR и /tmp)
```sh
keenetic-maxprobe --init
```

### Запуск (по умолчанию)
```sh
keenetic-maxprobe
```

### SAFE (если архив нужно кому-то отправить)
```sh
keenetic-maxprobe --mode safe
```
