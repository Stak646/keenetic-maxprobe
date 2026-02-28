# keenetic-maxprobe

Максимально «жадный» инструмент диагностики и исследования KeeneticOS + Entware (OPKG).

- **По умолчанию:** `FULL` (с чувствительными данными) — для локального бэкапа/восстановления.
- Профили:
  - `diagnostic` — быстрый и безопасный для повседневной диагностики.
  - `forensic` — максимально глубокий «слепок».
- Коллекторы (best‑effort): `sh` (core), `python`, `perl`, `lua`, `ruby`, `go` (если доступно), `node` (если доступно).

В режиме `FULL` инструмент **не редактирует** конфиги. Вместо этого он генерирует файл
`analysis/SENSITIVE_LOCATIONS.md`, где перечисляет **точные места** (пути/строки/типы секретов),
чтобы пользователь мог скрыть их перед отправкой архива.

## Быстрый старт (на роутере)

### Установка (one-liner)
```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```
или
```sh
sh -c "$(wget -qO- https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```

### Инициализация
```sh
keenetic-maxprobe --init
```

### Запуск по умолчанию
```sh
keenetic-maxprobe
```

### Максимально глубокий снимок
```sh
keenetic-maxprobe --profile forensic
```

### SAFE
```sh
keenetic-maxprobe --mode safe
```

См. `docs/OUTPUT_FORMAT.md`.
