# Security / Sensitive data

## TL;DR
- `full` and `extream` modes may include **passwords, tokens, private keys**.
- Always review `analysis/SENSITIVE_LOCATIONS.md` before sharing an archive.

## What the tool does
- Creates a filesystem mirror under `fs/` (configs, hook scripts, logs).
- Generates `analysis/SENSITIVE_LOCATIONS.md`:
  - lists files + line numbers where secrets may exist
  - does **NOT** print secret values (only location hints)

## Recommended workflow before sharing
1) Extract the archive locally.
2) Open `analysis/SENSITIVE_LOCATIONS.md` and `analysis/REDACTION_GUIDE_*.md`.
3) Redact sensitive lines/files inside `fs/...`.
4) Repack (or encrypt) the archive.

## SAFE mode
`--mode safe` tries to delete a few high-risk files from the mirrored FS (best-effort), e.g.:
- `/etc/shadow`, `/etc/gshadow`,
- some Entware `shadow/passwd` files,
- obvious key files.

SAFE is not a guarantee: always review the sensitive map.

## EXTREAM mode
`--mode extream` is intended for deep diagnostics and research.
It increases coverage and probes, and does not attempt to “protect” sensitive data.

