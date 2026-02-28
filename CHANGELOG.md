# Changelog

## v0.5.1 (2026-02-28)

### Fixed
- **Critical**: removed non‑POSIX brace expansion in `mkdir -p "$WORK"/{...}` which created a literal directory `{analysis,meta,...}` and broke report creation.

### Added
- Auto debug artifacts: `meta/run.log`, `meta/errors.log`, `meta/timings.tsv`, `meta/metrics.tsv`.
- TTY progress animation (spinner + current phase + resource stats).
- Resource throttling (target max **85% CPU** and **95% RAM**; best‑effort, adaptive backoff).
- Device/architecture detection and strategy selection (`meta/profile_selected.json`).
- Better HTTP/RCI probe (ports 80/443/79, `/rci/*` paths, status codes).

### Changed
- Default profile is now `auto` (selects forensic/diagnostic/lite by hardware).

### Changed
- Archive compression is now **low CPU** by default (`gzip -1`, `nice`).
- Collectors are executed with best‑effort timeouts and resource backoff.

## v0.4.x
- Initial public versions (see repository history).
