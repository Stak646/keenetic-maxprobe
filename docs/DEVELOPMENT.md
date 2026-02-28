# Development / Разработка и расширение

Документ двуязычный: RU + EN.

---

## RU: Концепция collectors

*Collector* — это опциональный модуль на любом языке (Python, Lua, Node, Perl, Ruby, Go…).

Цели дизайна:
- **best-effort**: отсутствие интерпретатора не должно ломать весь инструмент
- **низкая связность**: collector печатает в stdout, основной скрипт сохраняет в `sys/collectors/`
- **безопасная параллельность**: collectors можно запускать параллельно (job pool), но с лимитами CPU/RAM

### Куда класть collectors
Все «не-shell» модули должны лежать в:
- `collectors/py/`
- `collectors/lua/`
- `collectors/node/`
- `collectors/perl/`
- `collectors/ruby/`
- `collectors/go/`

### Рекомендованный контракт
- вход: `collector <workdir>` (workdir можно не использовать, но полезно)
- выход: текст/JSON в stdout (caller перенаправляет в файл)

### Идеи, что можно сделать дальше
- **Endpoint mapper (Python/Go)**: построить полную карту HTTP/RCI endpoints по найденным портам + кодам 200/401/403.
- **Hook graph (Python)**: граф хуков `ndm` и файлов/сервисов, которые они затрагивают.
- **Service analyzer (Python/Ruby)**: анализ init.d, выявление портов/конфигов/логов, автогенерация документации.
- **Diff tool (Go)**: сравнение 2 архивов и отчёт «что изменилось».
- **Web UI fingerprint (Node)**: распознавание web‑морды по заголовкам/контенту (nginx/lighttpd/uhttpd/etc).

---

## EN: Collector concept

A *collector* is an optional module written in any language (Python, Lua, Node, Perl, Ruby, Go…).

Design goals:
- **best-effort**: missing runtimes must not break the whole tool
- **low coupling**: collectors print to stdout, the main script stores results in `sys/collectors/`
- **safe parallelism**: collectors can run in parallel (job pool) while respecting CPU/RAM limits

### Where to put collectors
All non-shell modules must live under:
- `collectors/py/`
- `collectors/lua/`
- `collectors/node/`
- `collectors/perl/`
- `collectors/ruby/`
- `collectors/go/`

### Recommended contract
- input: `collector <workdir>`
- output: write text/JSON to stdout (caller redirects to a file)

### Future ideas
- **Endpoint mapper (Python/Go)**: build a full HTTP/RCI endpoint map based on ports & 200/401/403 responses.
- **Hook graph (Python)**: dependency graph of `ndm` hooks and touched files/services.
- **Service analyzer (Python/Ruby)**: parse init scripts, detect daemons, ports, configs, logs, and auto-generate docs.
- **Diff tool (Go)**: compare two archives and produce a delta report.
- **Web UI fingerprint (Node)**: detect web UI stack from headers/body (nginx/lighttpd/uhttpd/etc).

