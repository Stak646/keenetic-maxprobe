#!/usr/bin/env python3
"""
keenetic-maxprobe analyzer (Python)

- --inventory  [--stdout]
  Produces JSON inventory (used by bots / automation).
- --report
  Generates analysis/REPORT_RU.md and analysis/REPORT_EN.md (+ INDEX files).

Designed to be robust: missing/broken files are OK.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

VERSION = "0.6.2"


def read_bytes(path: Path, limit: int = 5_000_000) -> bytes:
    try:
        data = path.read_bytes()
    except Exception:
        return b""
    if len(data) > limit:
        data = data[:limit]
    # Some Keenetic strings include NUL terminators; drop them.
    return data.replace(b"\x00", b"")


def read_text(path: Path, limit: int = 5_000_000) -> str:
    data = read_bytes(path, limit=limit)
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return data.decode(errors="replace")


def read_json(path: Path) -> Any:
    raw = read_text(path)
    if not raw.strip():
        return None
    # Fix common broken escapes produced by buggy shell JSON generation: "\000"
    raw = raw.replace("\\000", "")
    try:
        return json.loads(raw)
    except Exception:
        return None


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_tsv(path: Path) -> List[List[str]]:
    rows: List[List[str]] = []
    for line in read_text(path).splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        rows.append(line.split("\t"))
    return rows


def detect_hooks(fs_dir: Path) -> List[Path]:
    hook_dirs: List[Path] = []
    candidates = [
        fs_dir / "etc" / "ndm",
        fs_dir / "opt" / "etc" / "ndm",
        fs_dir / "storage" / "etc" / "ndm",
    ]
    for c in candidates:
        if c.is_dir():
            hook_dirs.append(c)
    for root in candidates:
        if not root.is_dir():
            continue
        count = 0
        for p in root.rglob("*.d"):
            if p.is_dir():
                hook_dirs.append(p)
                count += 1
            if count > 500:
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


def summarize_http_probe(rows: List[List[str]], max_rows: int = 120) -> Dict[str, Any]:
    exist: List[Dict[str, str]] = []
    rci_ok: List[Dict[str, str]] = []
    per_port: Dict[str, Dict[str, int]] = {}
    for r in rows:
        if len(r) < 7:
            continue
        _, host, port, scheme, path, code, note = r[:7]
        per_port.setdefault(port, {"ok": 0, "auth": 0, "forbidden": 0, "other": 0, "no": 0})
        if code == "000":
            per_port[port]["no"] += 1
            continue
        if code.startswith(("2", "3")):
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
    return {"exists": exist[:max_rows], "rci_candidates": rci_ok[:max_rows], "per_port": per_port}


def build_inventory(workdir: Path) -> Dict[str, Any]:
    prof = read_json(workdir / "meta" / "profile_selected.json")
    prof = prof if isinstance(prof, dict) else {}

    services = read_json(workdir / "entware" / "services.json")
    services = services if isinstance(services, list) else []

    listen_rows = parse_tsv(workdir / "net" / "listen_ports.tsv")
    listen = []
    for r in listen_rows:
        if len(r) < 5:
            continue
        proto, ip, port, state, src = r[:5]
        listen.append({"proto": proto, "ip": ip, "port": port, "state": state, "source": src})

    http_rows = parse_tsv(workdir / "net" / "http_probe.tsv")
    http_summary = summarize_http_probe(http_rows)

    web_rows = parse_tsv(workdir / "web" / "probe.tsv")
    web = []
    for r in web_rows:
        if len(r) < 7:
            continue
        ts, host, port, scheme, path, code, size = r[:7]
        web.append({"ts": ts, "host": host, "port": port, "scheme": scheme, "path": path, "code": code, "bytes": size})

    inv: Dict[str, Any] = {
        "tool": {"name": "keenetic-maxprobe", "version": VERSION},
        "profile": prof,
        "entware": {"services": services},
        "network": {"listen": listen, "http_probe": http_summary},
        "web": {"manifest": web[:300]},
        "hooks": [str(p) for p in detect_hooks(workdir / "fs")][:200],
        "errors_tail": read_text(workdir / "meta" / "errors.log").splitlines()[-200:],
    }
    return inv


def report_ru(workdir: Path, inv: Dict[str, Any]) -> str:
    prof = inv.get("profile", {}) if isinstance(inv.get("profile"), dict) else {}
    dev = prof.get("device_model", "") or ""
    arch = prof.get("arch", "?")
    cores = prof.get("cores", "?")
    mem_kb = prof.get("mem_total_kb", 0)
    mode = prof.get("mode", "?")
    profile = prof.get("profile", "?")
    jobs = prof.get("jobs", "?")
    limits = prof.get("limits", {}) if isinstance(prof.get("limits"), dict) else {}
    max_cpu = limits.get("max_cpu_pct", "?")
    max_mem = limits.get("max_mem_pct", "?")

    try:
        mem_mb = f"{int(mem_kb) // 1024} MB"
    except Exception:
        mem_mb = ""

    listen = inv.get("network", {}).get("listen", []) if isinstance(inv.get("network"), dict) else []
    http = inv.get("network", {}).get("http_probe", {}) if isinstance(inv.get("network"), dict) else {}
    rci = http.get("rci_candidates", []) if isinstance(http, dict) else []

    lines: List[str] = []
    lines.append("# Отчёт keenetic-maxprobe (RU)")
    lines.append("")
    lines.append("## 1) Сводка")
    lines.append("")
    lines.append(f"- Режим: **{mode}**")
    lines.append(f"- Профиль: **{profile}**")
    if dev:
        lines.append(f"- Устройство: **{dev}**")
    lines.append(f"- Архитектура: `{arch}`, cores={cores}, RAM~{mem_mb}")
    lines.append(f"- Параллельность collectors: `{jobs}`")
    lines.append(f"- Лимиты: CPU<={max_cpu}%, RAM<={max_mem}%")
    lines.append("")
    lines.append("## 2) Где смотреть главное")
    lines.append("")
    lines.append("- `meta/run.log` — основной лог выполнения")
    lines.append("- `meta/errors.log` — ошибки/варнинги")
    lines.append("- `analysis/SENSITIVE_LOCATIONS.md` — карта чувствительных мест")
    lines.append("- `fs/` — зеркало конфигов (ключевое для восстановления)")
    lines.append("- `ndm/` — `ndmc` снимки KeeneticOS")
    lines.append("- `net/` + `web/` — порты/эндпойнты и web‑поверхности")
    lines.append("")
    lines.append("## 3) Слушающие порты")
    lines.append("")
    if listen:
        for item in listen[:80]:
            lines.append(f"- {item.get('proto','')} {item.get('ip','')}:{item.get('port','')} ({item.get('source','')})")
        if len(listen) > 80:
            lines.append(f"- ... ещё {len(listen)-80}")
    else:
        lines.append("_Нет данных (ss/netstat недоступны или parsing не сработал)._")
    lines.append("")
    lines.append("## 4) HTTP/RCI probe")
    lines.append("")
    if rci:
        lines.append("### RCI кандидаты")
        lines.append("")
        for e in rci[:60]:
            lines.append(f"- {e['host']}:{e['port']} {e['scheme']} {e['path']} → {e['code']} ({e['note']})")
    else:
        lines.append("_RCI endpoints не обнаружены по probe. Проверь `net/http_probe.tsv`._")
    lines.append("")
    lines.append("## 5) Хуки ndm")
    lines.append("")
    hooks = inv.get("hooks", [])
    if hooks:
        for h in hooks[:60]:
            lines.append(f"- `{h}`")
        if len(hooks) > 60:
            lines.append(f"- ... ещё {len(hooks)-60}")
    else:
        lines.append("_Директории хуков не найдены в `fs/`._")
    lines.append("")
    return "\n".join(lines)


def report_en(workdir: Path, inv: Dict[str, Any]) -> str:
    prof = inv.get("profile", {}) if isinstance(inv.get("profile"), dict) else {}
    dev = prof.get("device_model", "") or ""
    arch = prof.get("arch", "?")
    cores = prof.get("cores", "?")
    mem_kb = prof.get("mem_total_kb", 0)
    mode = prof.get("mode", "?")
    profile = prof.get("profile", "?")
    jobs = prof.get("jobs", "?")
    limits = prof.get("limits", {}) if isinstance(prof.get("limits"), dict) else {}
    max_cpu = limits.get("max_cpu_pct", "?")
    max_mem = limits.get("max_mem_pct", "?")

    try:
        mem_mb = f"{int(mem_kb) // 1024} MB"
    except Exception:
        mem_mb = ""

    lines: List[str] = []
    lines.append("# keenetic-maxprobe report (EN)")
    lines.append("")
    lines.append("## 1) Summary")
    lines.append("")
    lines.append(f"- Mode: **{mode}**")
    lines.append(f"- Profile: **{profile}**")
    if dev:
        lines.append(f"- Device: **{dev}**")
    lines.append(f"- Arch: `{arch}`, cores={cores}, RAM~{mem_mb}")
    lines.append(f"- Collector parallelism: `{jobs}`")
    lines.append(f"- Limits: CPU<={max_cpu}%, RAM<={max_mem}%")
    lines.append("")
    lines.append("## 2) Key places")
    lines.append("")
    lines.append("- `meta/run.log` — main execution log")
    lines.append("- `meta/errors.log` — errors/warnings")
    lines.append("- `analysis/SENSITIVE_LOCATIONS.md` — sensitive locations map")
    lines.append("- `fs/` — config mirror (restore/baseline)")
    lines.append("- `ndm/` — `ndmc` snapshots")
    lines.append("- `net/` + `web/` — ports/endpoints and web surfaces")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=".", help="path to extracted keenetic-maxprobe bundle directory")
    ap.add_argument("--inventory", action="store_true", help="print inventory JSON to stdout or file")
    ap.add_argument("--stdout", action="store_true", help="with --inventory: print to stdout")
    ap.add_argument("--report", action="store_true", help="write REPORT_RU/EN.md under analysis/")
    args = ap.parse_args()

    workdir = Path(args.workdir).resolve()
    inv = build_inventory(workdir)

    if args.inventory:
        if args.stdout:
            print(json.dumps(inv, ensure_ascii=False, indent=2))
        else:
            out = workdir / "analysis" / "inventory.json"
            write_text(out, json.dumps(inv, ensure_ascii=False, indent=2))

    if args.report:
        write_text(workdir / "analysis" / "REPORT_RU.md", report_ru(workdir, inv))
        write_text(workdir / "analysis" / "REPORT_EN.md", report_en(workdir, inv))


if __name__ == "__main__":
    main()
