#!/usr/bin/env python3
"""keenetic-maxprobe analyzer (Python)

- --inventory <workdir> [--stdout]
  Produces JSON inventory (used by bots / automation).

- --report <workdir>
  Generates analysis/REPORT_RU.md and analysis/REPORT_EN.md (+ INDEX files).

Designed to be robust: missing files are OK.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


VERSION = "0.6.0"


def read_text(path: Path, limit: int = 2_000_000) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    if len(data) > limit:
        data = data[:limit]
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return data.decode(errors="replace")


def read_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except Exception:
        return None


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def safe_get(d: Any, *keys: str, default: Any = "") -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def parse_tsv(path: Path) -> List[List[str]]:
    rows: List[List[str]] = []
    for line in read_text(path).splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        rows.append(line.split("\t"))
    return rows


def detect_hooks(fs_dir: Path) -> List[Path]:
    """Find ndm hook directories inside fs/ mirror."""
    hook_dirs: List[Path] = []
    candidates = [
        fs_dir / "etc" / "ndm",
        fs_dir / "opt" / "etc" / "ndm",
        fs_dir / "storage" / "etc" / "ndm",
    ]
    for c in candidates:
        if c.is_dir():
            hook_dirs.append(c)

    # also look for *.d style hook folders under those trees
    # (keep it bounded)
    for root in candidates:
        if not root.is_dir():
            continue
        count = 0
        for p in root.rglob("*.d"):
            if p.is_dir():
                hook_dirs.append(p)
                count += 1
                if count > 200:
                    break
    # dedupe
    seen = set()
    out: List[Path] = []
    for p in hook_dirs:
        rp = str(p)
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out


def list_hook_scripts(hook_dir: Path, limit: int = 500) -> List[Path]:
    scripts: List[Path] = []
    try:
        for p in sorted(hook_dir.iterdir()):
            if p.is_file():
                scripts.append(p)
                if len(scripts) >= limit:
                    break
    except Exception:
        return []
    return scripts


def load_services(workdir: Path) -> List[Dict[str, Any]]:
    j = read_json(workdir / "entware" / "services.json")
    if isinstance(j, list):
        out: List[Dict[str, Any]] = []
        for item in j:
            if isinstance(item, dict):
                out.append(item)
        return out
    return []


def summarize_http_probe(rows: List[List[str]], max_rows: int = 80) -> Dict[str, Any]:
    """Return summary: endpoints that exist and per-port stats."""
    exist: List[Dict[str, str]] = []
    rci_ok: List[Dict[str, str]] = []
    per_port: Dict[str, Dict[str, int]] = {}

    for r in rows:
        # ts host port scheme path code note
        if len(r) < 7:
            continue
        _, host, port, scheme, path, code, note = r[:7]
        per_port.setdefault(port, {"ok": 0, "auth": 0, "forbidden": 0, "other": 0, "no": 0})
        if code == "000":
            per_port[port]["no"] += 1
            continue
        if code.startswith("2") or code.startswith("3"):
            per_port[port]["ok"] += 1
        elif code == "401":
            per_port[port]["auth"] += 1
        elif code == "403":
            per_port[port]["forbidden"] += 1
        else:
            per_port[port]["other"] += 1

        if code in {"200", "301", "302", "307", "308", "401", "403"}:
            exist.append({"host": host, "port": port, "scheme": scheme, "path": path, "code": code, "note": note})
            if path.startswith("/rci/") and code in {"200", "401", "403"}:
                rci_ok.append({"host": host, "port": port, "scheme": scheme, "path": path, "code": code, "note": note})

    # cap
    exist = exist[:max_rows]
    rci_ok = rci_ok[:max_rows]
    return {"exists": exist, "rci_candidates": rci_ok, "per_port": per_port}


def load_profile(workdir: Path) -> Dict[str, Any]:
    prof = read_json(workdir / "meta" / "profile_selected.json")
    return prof if isinstance(prof, dict) else {}


def load_errors(workdir: Path, limit_lines: int = 200) -> List[str]:
    p = workdir / "meta" / "errors.log"
    if not p.exists():
        return []
    lines = read_text(p).splitlines()
    return lines[-limit_lines:]


def load_listen_ports(workdir: Path) -> List[Dict[str, str]]:
    p = workdir / "net" / "listen_ports.tsv"
    rows = parse_tsv(p)
    out: List[Dict[str, str]] = []
    for r in rows:
        if len(r) < 5:
            continue
        proto, ip, port, state, src = r[:5]
        out.append({"proto": proto, "ip": ip, "port": port, "state": state, "source": src})
    return out


def load_web_manifest(workdir: Path) -> List[Dict[str, str]]:
    p = workdir / "web" / "probe.tsv"
    rows = parse_tsv(p)
    out: List[Dict[str, str]] = []
    for r in rows:
        # ts host port scheme path code bytes
        if len(r) < 7:
            continue
        ts, host, port, scheme, path, code, size = r[:7]
        out.append({"ts": ts, "host": host, "port": port, "scheme": scheme, "path": path, "code": code, "bytes": size})
    return out


def build_inventory(workdir: Path) -> Dict[str, Any]:
    prof = load_profile(workdir)
    services = load_services(workdir)
    listen = load_listen_ports(workdir)

    http_rows = parse_tsv(workdir / "net" / "http_probe.tsv")
    http_summary = summarize_http_probe(http_rows)

    web_manifest = load_web_manifest(workdir)

    inv: Dict[str, Any] = {
        "tool": {"name": "keenetic-maxprobe", "version": VERSION},
        "profile": prof,
        "entware": {"services": services},
        "network": {"listen": listen, "http_probe": http_summary},
        "web": {"manifest": web_manifest[:200]},
        "errors_tail": load_errors(workdir, limit_lines=200),
    }
    return inv


def md_escape(s: str) -> str:
    return s.replace("<", "&lt;").replace(">", "&gt;")


def report_ru(workdir: Path, inv: Dict[str, Any]) -> str:
    prof = inv.get("profile", {})
    dev = safe_get(prof, "device_model", default="") or ""
    arch = safe_get(prof, "arch", default="?")
    cores = safe_get(prof, "cores", default="?")
    mem_kb = safe_get(prof, "mem_total_kb", default=0)
    mode = safe_get(prof, "mode", default="?")
    profile = safe_get(prof, "profile", default="?")
    jobs = safe_get(prof, "jobs", default="?")
    limits = safe_get(prof, "limits", default={}) or {}
    max_cpu = limits.get("max_cpu_pct", "?")
    max_mem = limits.get("max_mem_pct", "?")

    mem_mb = ""
    try:
        mem_mb = f"{int(mem_kb) // 1024} MB"
    except Exception:
        mem_mb = ""

    services = inv.get("entware", {}).get("services", [])
    listen = inv.get("network", {}).get("listen", [])
    http = inv.get("network", {}).get("http_probe", {})
    rci = http.get("rci_candidates", []) if isinstance(http, dict) else []
    web = inv.get("web", {}).get("manifest", [])

    err_tail = inv.get("errors_tail", [])

    lines: List[str] = []
    lines.append("# Отчёт keenetic-maxprobe (RU)")
    lines.append("")
    lines.append("## 1) Сводка")
    lines.append("")
    lines.append(f"- Режим: **{mode}**")
    lines.append(f"- Профиль: **{profile}**")
    if dev:
        lines.append(f"- Устройство: **{md_escape(dev)}**")
    lines.append(f"- Архитектура: `{arch}`, cores={cores}, RAM~{mem_mb}")
    lines.append(f"- Параллельность collectors: `{jobs}`")
    lines.append(f"- Лимиты: CPU<={max_cpu}%, RAM<={max_mem}%")
    lines.append("")
    lines.append("## 2) Где смотреть главное")
    lines.append("")
    lines.append("- `meta/run.log` — основной лог выполнения")
    lines.append("- `meta/errors.log` — ошибки/варнинги")
    lines.append("- `analysis/SENSITIVE_LOCATIONS.md` — карта чувствительных мест")
    lines.append("- `fs/` — зеркало конфигов (самое важное для восстановления)")
    lines.append("- `ndm/` — `ndmc` снимки KeeneticOS")
    lines.append("- `net/` + `web/` — порты/эндпойнты и web‑поверхности")
    lines.append("")
    lines.append("## 3) Слушающие порты (best‑effort)")
    lines.append("")
    if listen:
        for item in listen[:60]:
            lines.append(f"- {item.get('proto','')} {item.get('ip','')}:{item.get('port','')} ({item.get('source','')})")
        if len(listen) > 60:
            lines.append(f"- ... ещё {len(listen)-60}")
    else:
        lines.append("_Нет данных (ss/netstat не доступны, или /proc parsing не сработал)._")
    lines.append("")
    lines.append("## 4) HTTP/RCI probe — что реально отвечает")
    lines.append("")
    if rci:
        lines.append("### RCI кандидаты (существуют / требуют auth / отвечают)")
        lines.append("")
        for e in rci[:40]:
            lines.append(f"- {e['host']}:{e['port']} {e['scheme']} {e['path']} → {e['code']} ({e['note']})")
        if len(rci) > 40:
            lines.append(f"- ... ещё {len(rci)-40}")
    else:
        lines.append("_RCI endpoints не обнаружены по probe. Проверьте `net/http_probe.tsv` вручную._")
    lines.append("")
    if web:
        lines.append("### Web probe (расширенный)")
        lines.append("")
        # show interesting ones: 200/401/403
        interesting = [w for w in web if w.get("code") in {"200", "301", "302", "401", "403"}]
        for w in interesting[:60]:
            lines.append(f"- {w.get('host')}:{w.get('port')} {w.get('scheme')} {w.get('path')} → {w.get('code')} ({w.get('bytes')} bytes)")
        if len(interesting) > 60:
            lines.append(f"- ... ещё {len(interesting)-60}")
        lines.append("")
        lines.append("Фрагменты ответов лежат в `web/<host>_<port>_<scheme>/*.headers|*.body`.")
        lines.append("")
    lines.append("## 5) Entware: службы и init.d")
    lines.append("")
    if services:
        enabled = [s for s in services if s.get("executable") in (1, True, "1")]
        disabled = [s for s in services if s.get("executable") in (0, False, "0")]
        lines.append(f"- Всего init.d скриптов: **{len(services)}** (enabled={len(enabled)}, disabled={len(disabled)})")
        lines.append("")
        lines.append("Примеры (первые 30):")
        for s in services[:30]:
            ex = "on" if s.get("executable") in (1, True, "1") else "off"
            lines.append(f"- `{s.get('script','')}` exec={ex} sha256={s.get('sha256','')}")
        lines.append("")
        lines.append("Управление: `entwarectl list|status|restart|enable|disable <service>`.")
    else:
        lines.append("_services.json не найден (возможно, нет Entware или /opt/etc/init.d отсутствует)._")
    lines.append("")
    lines.append("## 6) Хуки ndm (события KeeneticOS / OPKG)")
    lines.append("")
    hooks = detect_hooks(workdir / "fs")
    if hooks:
        for d in hooks[:30]:
            rel = str(d).replace(str(workdir) + os.sep, "")
            lines.append(f"- `{rel}`")
        if len(hooks) > 30:
            lines.append(f"- ... ещё {len(hooks)-30}")
        lines.append("")
        lines.append("Подсказка: эти директории важны для реализации уведомлений/автоматизаций (например, Telegram‑бот).")
    else:
        lines.append("_Директории хуков не найдены в `fs/`._")
    lines.append("")
    lines.append("## 7) Чувствительные данные")
    lines.append("")
    lines.append("- Смотрите `analysis/SENSITIVE_LOCATIONS.md` и `analysis/REDACTION_GUIDE_RU.md`.")
    lines.append("- В `full/extream` архив может содержать секреты. Перед отправкой — редактируйте.")
    lines.append("")
    if err_tail:
        lines.append("## 8) Ошибки/варнинги (tail)")
        lines.append("")
        lines.append("```")
        for ln in err_tail[-80:]:
            lines.append(ln)
        lines.append("```")
        lines.append("")
    lines.append("## 9) Что можно реализовать дальше (идеи)")
    lines.append("")
    lines.append("- Авто‑построение карты RCI/HTTP endpoints по найденным портам (с категоризацией).")
    lines.append("- Генерация готового skeleton OPKG‑пакета для Telegram‑daemon + hook‑скрипты.")
    lines.append("- Авто‑валидатор конфигов и список «подозрительных» настроек (NAT/Firewall/VPN).")
    lines.append("")
    return "\n".join(lines) + "\n"


def report_en(workdir: Path, inv: Dict[str, Any]) -> str:
    prof = inv.get("profile", {})
    dev = safe_get(prof, "device_model", default="") or ""
    arch = safe_get(prof, "arch", default="?")
    cores = safe_get(prof, "cores", default="?")
    mem_kb = safe_get(prof, "mem_total_kb", default=0)
    mode = safe_get(prof, "mode", default="?")
    profile = safe_get(prof, "profile", default="?")
    jobs = safe_get(prof, "jobs", default="?")
    limits = safe_get(prof, "limits", default={}) or {}
    max_cpu = limits.get("max_cpu_pct", "?")
    max_mem = limits.get("max_mem_pct", "?")

    mem_mb = ""
    try:
        mem_mb = f"{int(mem_kb) // 1024} MB"
    except Exception:
        mem_mb = ""

    services = inv.get("entware", {}).get("services", [])
    listen = inv.get("network", {}).get("listen", [])
    http = inv.get("network", {}).get("http_probe", {})
    rci = http.get("rci_candidates", []) if isinstance(http, dict) else []
    web = inv.get("web", {}).get("manifest", [])
    err_tail = inv.get("errors_tail", [])

    lines: List[str] = []
    lines.append("# keenetic-maxprobe report (EN)")
    lines.append("")
    lines.append("## 1) Summary")
    lines.append("")
    lines.append(f"- Mode: **{mode}**")
    lines.append(f"- Profile: **{profile}**")
    if dev:
        lines.append(f"- Device: **{md_escape(dev)}**")
    lines.append(f"- Arch: `{arch}`, cores={cores}, RAM~{mem_mb}")
    lines.append(f"- Collector parallel jobs: `{jobs}`")
    lines.append(f"- Limits: CPU<={max_cpu}%, RAM<={max_mem}%")
    lines.append("")
    lines.append("## 2) Where to look first")
    lines.append("")
    lines.append("- `meta/run.log` — main execution log")
    lines.append("- `meta/errors.log` — errors/warnings")
    lines.append("- `analysis/SENSITIVE_LOCATIONS.md` — sensitive map")
    lines.append("- `fs/` — filesystem mirror (most important)")
    lines.append("- `ndm/` — `ndmc` snapshots (KeeneticOS)")
    lines.append("- `net/` + `web/` — ports/endpoints + web surface")
    lines.append("")
    lines.append("## 3) Listening ports (best-effort)")
    lines.append("")
    if listen:
        for item in listen[:60]:
            lines.append(f"- {item.get('proto','')} {item.get('ip','')}:{item.get('port','')} ({item.get('source','')})")
        if len(listen) > 60:
            lines.append(f"- ... +{len(listen)-60} more")
    else:
        lines.append("_No data (ss/netstat missing, or /proc parsing failed)._")
    lines.append("")
    lines.append("## 4) HTTP/RCI probe — what responds")
    lines.append("")
    if rci:
        lines.append("### RCI candidates (exist / require auth / respond)")
        lines.append("")
        for e in rci[:40]:
            lines.append(f"- {e['host']}:{e['port']} {e['scheme']} {e['path']} → {e['code']} ({e['note']})")
        if len(rci) > 40:
            lines.append(f"- ... +{len(rci)-40} more")
    else:
        lines.append("_No RCI endpoints found by probe. Check `net/http_probe.tsv` manually._")
    lines.append("")
    if web:
        lines.append("### Web probe (extended)")
        lines.append("")
        interesting = [w for w in web if w.get("code") in {"200", "301", "302", "401", "403"}]
        for w in interesting[:60]:
            lines.append(f"- {w.get('host')}:{w.get('port')} {w.get('scheme')} {w.get('path')} → {w.get('code')} ({w.get('bytes')} bytes)")
        if len(interesting) > 60:
            lines.append(f"- ... +{len(interesting)-60} more")
        lines.append("")
        lines.append("Response samples are stored in `web/<host>_<port>_<scheme>/*.headers|*.body`.")
        lines.append("")
    lines.append("## 5) Entware services (init.d)")
    lines.append("")
    if services:
        enabled = [s for s in services if s.get("executable") in (1, True, "1")]
        disabled = [s for s in services if s.get("executable") in (0, False, "0")]
        lines.append(f"- Total init.d scripts: **{len(services)}** (enabled={len(enabled)}, disabled={len(disabled)})")
        lines.append("")
        lines.append("Examples (first 30):")
        for s in services[:30]:
            ex = "on" if s.get("executable") in (1, True, "1") else "off"
            lines.append(f"- `{s.get('script','')}` exec={ex} sha256={s.get('sha256','')}")
        lines.append("")
        lines.append("Control via: `entwarectl list|status|restart|enable|disable <service>`.")
    else:
        lines.append("_services.json not found (Entware missing or /opt/etc/init.d absent)._")
    lines.append("")
    lines.append("## 6) ndm hooks (KeeneticOS / OPKG events)")
    lines.append("")
    hooks = detect_hooks(workdir / "fs")
    if hooks:
        for d in hooks[:30]:
            rel = str(d).replace(str(workdir) + os.sep, "")
            lines.append(f"- `{rel}`")
        if len(hooks) > 30:
            lines.append(f"- ... +{len(hooks)-30} more")
        lines.append("")
        lines.append("Hint: these directories matter for event-driven automation (e.g. Telegram notifications).")
    else:
        lines.append("_No hook directories found in `fs/`._")
    lines.append("")
    lines.append("## 7) Sensitive data")
    lines.append("")
    lines.append("- See `analysis/SENSITIVE_LOCATIONS.md` and `analysis/REDACTION_GUIDE_EN.md`.")
    lines.append("- In `full/extream` the archive may contain secrets. Redact before sharing.")
    lines.append("")
    if err_tail:
        lines.append("## 8) Errors/warnings (tail)")
        lines.append("")
        lines.append("```")
        for ln in err_tail[-80:]:
            lines.append(ln)
        lines.append("```")
        lines.append("")
    lines.append("## 9) Next steps / ideas")
    lines.append("")
    lines.append("- Auto-map RCI/HTTP endpoints per port (categorized).")
    lines.append("- Generate an OPKG package skeleton for a Telegram daemon + hook scripts.")
    lines.append("- Config validator and 'suspicious settings' report (NAT/Firewall/VPN).")
    lines.append("")
    return "\n".join(lines) + "\n"


def index_ru() -> str:
    return """# Индекс (RU)

- `analysis/REPORT_RU.md` — основной отчёт
- `analysis/SENSITIVE_LOCATIONS.md` — карта чувствительных мест
- `fs/` — зеркало файловой системы (configs)
- `ndm/` — снимки ndmc (KeeneticOS)
- `entware/` — OPKG + init.d + services.json
- `net/` — сеть + http probe
- `web/` — расширенный web probe (если включен)
- `meta/` — run/errors logs + metrics

"""


def index_en() -> str:
    return """# Index (EN)

- `analysis/REPORT_EN.md` — main report
- `analysis/SENSITIVE_LOCATIONS.md` — sensitive map
- `fs/` — filesystem mirror (configs)
- `ndm/` — ndmc snapshots (KeeneticOS)
- `entware/` — OPKG + init.d + services.json
- `net/` — network + http probe
- `web/` — extended web probe (if enabled)
- `meta/` — run/errors logs + metrics

"""


def cmd_inventory(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir)
    inv = build_inventory(workdir)
    if args.stdout:
        print(json.dumps(inv, ensure_ascii=False, indent=2))
    else:
        out = workdir / "sys" / "collectors" / "python_inventory.json"
        write_text(out, json.dumps(inv, ensure_ascii=False, indent=2) + "\n")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir)
    inv = build_inventory(workdir)

    # reports
    write_text(workdir / "analysis" / "REPORT_RU.md", report_ru(workdir, inv))
    write_text(workdir / "analysis" / "REPORT_EN.md", report_en(workdir, inv))
    # index
    write_text(workdir / "analysis" / "INDEX_RU.md", index_ru())
    write_text(workdir / "analysis" / "INDEX_EN.md", index_en())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="analyze.py")
    ap.add_argument("--inventory", dest="inventory", action="store_true", help="build JSON inventory")
    ap.add_argument("--report", dest="report", action="store_true", help="generate markdown reports")
    ap.add_argument("--workdir", dest="workdir", default="", help="work directory")
    ap.add_argument("--stdout", dest="stdout", action="store_true", help="for --inventory: print JSON to stdout")

    args = ap.parse_args()

    # back-compat: allow positional workdir in our toolchain, but keep strict enough
    if not args.workdir:
        # allow last arg in older call styles, but only if it looks like a path
        pass

    if args.inventory and args.workdir:
        return cmd_inventory(args)
    if args.report and args.workdir:
        return cmd_report(args)

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
