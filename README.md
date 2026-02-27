# keenetic-maxprobe

**KeeneticOS + Entware (OPKG) "maximum" inventory / diagnostics collector**.

This repository contains a single tool that:
- inventories your Keenetic router (system, network, files, services);
- discovers Entware/OPKG integration hooks (`/opt/etc/ndm/*.d` and other hook-like dirs);
- collects KeeneticOS config (`running-config` / `startup-config`) and system log via `ndmc`;
- probes local web management endpoints (`/auth`, `/rci/`, `/ci/*`) without logging in;
- produces a **very detailed, structured log bundle** (`.tar.gz`) you can review/share.

> Security: the tool **redacts passwords/keys/tokens by default**.

## Quick start (one-liner)

After you push this repo to GitHub, run this on the router (SSH shell, root/admin):

```sh
sh -c "$(wget -qO- https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```

Alternative with curl:

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/<YOU>/<REPO>/main/scripts/install.sh)"
```

The installer will:
1) install dependencies via `opkg` (best-effort);
2) install `/opt/bin/keenetic-maxprobe`;
3) run it and print the path to the resulting archive.

## Documentation

- **Русский:** `docs/README_RU.md`
- **English:** `docs/README_EN.md`
- Output format: `docs/OUTPUT_FORMAT.md`
- Security notes: `docs/SECURITY.md`

## License

MIT — see `LICENSE`.
