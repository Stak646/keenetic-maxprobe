#!/usr/bin/env python3
# keenetic-maxprobe analyzer / helpers
# Version: 0.5.1
#
# Dependency-free (stdlib only). Safe to run on Entware Python.

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VERSION = "0.5.1"


def utc_now() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def read_text(path: Path, max_bytes: int = 2_000_000) -> str:
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            data = data[:max_bytes] + b"\n...<truncated>...\n"
        return data.decode("utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except Exception as e:
        return f"<error reading {path}: {e}>"


def sha256_file(path: Path, max_bytes: int = 10_000_000) -> str:
    h = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 256)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    h.update(b"<truncated>")
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def parse_http_probe(lines: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for ln in lines.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split("\t")
        if len(parts) < 6:
            parts = re.split(r"\s+", ln)
        if len(parts) < 6:
            continue
        ts, host, port, path, code, note = parts[:6]
        out.append({"ts": ts, "host": host, "port": port, "path": path, "code": code, "note": note})
    return out


def summarize_http_probe(items: List[Dict[str, str]]) -> Dict[str, Any]:
    by_port: Dict[str, Dict[str, Dict[str, int]]] = {}
    for it in items:
        p = it["port"]
        path = it["path"]
        code = it["code"]
        by_port.setdefault(p, {}).setdefault(path, {}).setdefault(code, 0)
        by_port[p][path][code] += 1

    highlights: List[str] = []
    for p, paths in sorted(by_port.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        for path, codes in paths.items():
            if any(c != "000" for c in codes.keys()):
                prio = ["200", "301", "302", "307", "308", "401", "403", "405", "404"]
                best = None
                for c in prio:
                    if c in codes:
                        best = c
                        break
                if best is None:
                    best = sorted(codes.keys())[0]
                highlights.append(f"порт {p} {path} → {best} (hosts: {sum(codes.values())})")
    return {"by_port": by_port, "highlights": highlights}


# ---- Hooks knowledge (best-effort) ----
HOOK_KNOWLEDGE_RU: Dict[str, str] = {
    "wan.d": "WAN up/down (старт/стоп интернет‑соединения)",
    "ifipchanged.d": "изменение IPv4 адреса на интерфейсе",
    "ifip6changed.d": "изменение IPv6 адреса на интерфейсе",
    "iflayerchanged.d": "изменение состояния/уровня интерфейса (KeeneticOS 4.x+)",
    "ifstatechanged.d": "устаревшее событие состояния интерфейса (KeeneticOS < 4.0)",
    "netfilter.d": "перезапись/перегенерация таблиц netfilter (firewall reload)",
    "usb.d": "подключение/отключение USB устройства",
    "fs.d": "монтирование/размонтирование файловых систем",
    "button.d": "нажатие кнопок устройства",
    "time.d": "изменение системного времени",
    "schedule.d": "запуск задач планировщика",
    "neighbour.d": "изменение списка соседей (best-effort)",
    "user.d": "события пользователя/доступа к управлению (best-effort)",
    "sms.d": "приход SMS (если есть модем)",
    # VPN-related (packages may add their own)
    "openvpn-client-connect.d": "OpenVPN client connect",
    "openvpn-client-disconnect.d": "OpenVPN client disconnect",
    "openvpn-server-connect.d": "OpenVPN server connect",
    "openvpn-server-disconnect.d": "OpenVPN server disconnect",
}

NDMC_MAP_RU: List[Tuple[str, str]] = [
    ("show version", "версия прошивки/платформа"),
    ("show system", "состояние системы и аптайм"),
    ("show interface", "интерфейсы, линк, адреса"),
    ("show ip route", "маршрутизация"),
    ("show ip policy", "политики/маршрутизация по правилам"),
    ("show log", "системный лог (KeeneticOS)"),
    ("show running-config", "актуальная конфигурация (очень полезно для бэкапа)"),
]


def enumerate_hook_dirs(fs_root: Path) -> List[Dict[str, Any]]:
    """
    Enumerate hook directories under /opt/etc/ndm, /etc/ndm, /storage/etc/ndm
    mirrored as fs/opt/etc/ndm, fs/etc/ndm, fs/storage/etc/ndm.

    We also include one nested level (e.g., fs/opt/etc/ndm/ndm/*.d) because some
    packages may create subtrees.
    """
    bases = [
        fs_root / "opt" / "etc" / "ndm",
        fs_root / "etc" / "ndm",
        fs_root / "storage" / "etc" / "ndm",
    ]
    found: List[Path] = []
    for base in bases:
        if not base.exists():
            continue
        # direct
        found.extend([p for p in base.glob("*.d") if p.is_dir()])
        # one nested level
        found.extend([p for p in base.glob("*/*.d") if p.is_dir()])

    # dedupe
    uniq: Dict[str, Path] = {str(p): p for p in found}
    dirs = [uniq[k] for k in sorted(uniq.keys())]

    out: List[Dict[str, Any]] = []
    for d in dirs:
        rel = d.relative_to(fs_root)
        scripts: List[Dict[str, Any]] = []
        try:
            for f in sorted(d.iterdir()):
                if not f.is_file():
                    continue
                scripts.append(
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "executable": os.access(f, os.X_OK),
                        "sha256": sha256_file(f, max_bytes=2_000_000),
                    }
                )
        except Exception:
            pass

        name = d.name
        out.append(
            {
                "rel": str(rel),
                "name": name,
                "hint_ru": HOOK_KNOWLEDGE_RU.get(name, ""),
                "scripts": scripts,
            }
        )
    return out


def load_services(work: Path) -> List[Dict[str, Any]]:
    # Prefer normalized services.json if present
    p = work / "entware" / "services.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return []
    return []


def ndmc_snippet(work: Path, name: str, max_lines: int = 40) -> str:
    p = work / "ndm" / name
    if not p.exists():
        return ""
    txt = read_text(p, max_bytes=200_000)
    lines = txt.splitlines()
    return "\n".join(lines[:max_lines]).strip()


def generate_report_ru(work: Path) -> str:
    meta = work / "meta" / "profile_selected.json"
    profile: Dict[str, Any] = {}
    if meta.exists():
        try:
            profile = json.loads(meta.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            profile = {}

    http_items = parse_http_probe(read_text(work / "net" / "http_probe.txt"))
    http_sum = summarize_http_probe(http_items) if http_items else {"highlights": []}

    hooks = enumerate_hook_dirs(work / "fs")
    services = load_services(work)

    lines: List[str] = []
    lines.append("# Отчёт keenetic-maxprobe")
    lines.append("")
    lines.append(f"- Сформировано: {utc_now()}")
    if profile:
        lines.append(f"- Профиль: `{profile.get('profile')}` | режим: `{profile.get('mode')}`")
        lines.append(
            f"- Архитектура: `{profile.get('arch')}` | CPU cores: `{profile.get('cores')}` | RAM: `{profile.get('mem_total_kb')} KB`"
        )
        lim = profile.get("limits") or {}
        if lim:
            lines.append(f"- Лимиты: CPU {lim.get('max_cpu_pct')}% | RAM {lim.get('max_mem_pct')}% (best‑effort)")
    lines.append("")

    # NDM / version
    ver = ndmc_snippet(work, "ndmc_show_version.txt", 60)
    if ver:
        lines.append("## KeeneticOS (ndmc) — версия/платформа (snippet)")
        lines.append("")
        lines.append("```")
        lines.append(ver)
        lines.append("```")
        lines.append("")

    # API/RCI visibility
    lines.append("## Управление / API / RCI — что видно по HTTP probe")
    if http_sum["highlights"]:
        lines.append("")
        lines.append("Найденные ответы (кратко):")
        for h in http_sum["highlights"][:60]:
            lines.append(f"- {h}")
        lines.append("")
        lines.append("Подсказки интерпретации кодов:")
        lines.append("- `401/403` часто означает, что endpoint существует, но требуется аутентификация.")
        lines.append("- `200/30x` означает, что веб‑интерфейс/прокси жив и отвечает.")
    else:
        lines.append("")
        lines.append("HTTP probe не дал ответов (возможные причины: нет `curl`, порты закрыты, доступ только по LAN IP, или сервисы отключены).")

    lines.append("")
    lines.append("Рекомендованные проверки (ручные):")
    lines.append("```sh")
    lines.append("curl -k -I http://127.0.0.1:79/rci/show/system")
    lines.append("# Если HTTP Proxy/RCI включён и есть логин/пароль администратора:")
    lines.append("# curl --digest -u admin:PASS http://ROUTER_IP/rci/show/system")
    lines.append("```")
    lines.append("")

    # Hooks
    lines.append("## Event‑хуки OPKG (/opt/etc/ndm/*.d)")
    if hooks:
        lines.append("")
        lines.append("Найдены директории хуков (фактические):")
        for h in hooks:
            hint = h.get("hint_ru") or "событие (нет описания в базе)"
            lines.append(f"- `{h['rel']}` — {hint}")
            scripts = h.get("scripts") or []
            if scripts:
                names = ", ".join(s["name"] for s in scripts[:12])
                more = "" if len(scripts) <= 12 else f" … (+{len(scripts)-12})"
                lines.append(f"  - scripts: {names}{more}")
            else:
                lines.append("  - scripts: (empty)")
    else:
        lines.append("")
        lines.append("В зеркале `fs/` не найдено `*/etc/ndm/*.d` (либо OPKG не установлен, либо каталоги пустые).")

    lines.append("")
    lines.append("### Важные ограничения хуков (чтобы не «убить» роутер)")
    lines.append("")
    lines.append("- Хуки запускаются через `ndm` и имеют ограничение по времени выполнения (обычно ~24 секунды).")
    lines.append("- Вызовы могут быть **очередью** — следующий скрипт стартует только когда закончится предыдущий.")
    lines.append("- Поэтому в хуках: только запись события в файл/очередь, а сетевые запросы (Telegram) — в отдельном daemon.")
    lines.append("")

    lines.append("### Схема Telegram‑уведомлений (рекомендация)")
    lines.append("")
    lines.append("1) Hook → пишет событие в `/opt/var/spool/kmp/events.ndjson` (1 строка JSON на событие).")
    lines.append("2) Entware‑daemon `kmp-tg` читает spool, делает rate‑limit и отправляет в Telegram.")
    lines.append("3) Отдельный `entwarectl restart kmp-tg` умеет перезапускать отправщик.")
    lines.append("")

    # Services
    lines.append("## Entware‑службы (/opt/etc/init.d)")
    if services:
        lines.append("")
        lines.append(f"Найдено init‑скриптов: {len(services)}")
        for svc in services[:40]:
            lines.append(f"- `{svc.get('script')}` (exec={svc.get('executable')}, size={svc.get('size')})")
        if len(services) > 40:
            lines.append(f"... (+{len(services)-40})")
    else:
        lines.append("")
        lines.append("Список сервисов не найден (`entware/services.json` отсутствует).")

    lines.append("")
    lines.append("Единый слой управления: `entwarectl list/start/stop/restart/status`.")
    lines.append("")

    # KeeneticOS command map
    lines.append("## Карта команд KeeneticOS (ndmc / RCI)")
    lines.append("")
    lines.append("Высоко‑полезные команды для диагностики/бота:")
    for cmd, desc in NDMC_MAP_RU:
        lines.append(f"- `ndmc -c '{cmd}'` — {desc}")
        lines.append(f"  - (если RCI включён) `GET /rci/{cmd.replace(' ', '/')}`")
    lines.append("")

    lines.append("## Что обычно присылают для анализа")
    lines.append("")
    lines.append("- `analysis/REPORT_RU.md`")
    lines.append("- `analysis/SENSITIVE_LOCATIONS.md` (чтобы понять, что замаскировать)")
    lines.append("- `meta/run.log` и `meta/errors.log`")
    lines.append("")
    lines.append("> Если отчёт кажется «пустым», проверьте `meta/errors.log` — там будет причина пропусков (нет бинарника, ошибка команды, таймаут).")

    return "\n".join(lines) + "\n"


def generate_report_en(work: Path) -> str:
    meta = work / "meta" / "profile_selected.json"
    profile: Dict[str, Any] = {}
    if meta.exists():
        try:
            profile = json.loads(meta.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            profile = {}

    http_items = parse_http_probe(read_text(work / "net" / "http_probe.txt"))
    http_sum = summarize_http_probe(http_items) if http_items else {"highlights": []}

    hooks = enumerate_hook_dirs(work / "fs")
    services = load_services(work)

    lines: List[str] = []
    lines.append("# keenetic-maxprobe report")
    lines.append("")
    lines.append(f"- Generated: {utc_now()}")
    if profile:
        lines.append(f"- Profile: `{profile.get('profile')}` | mode: `{profile.get('mode')}`")
        lines.append(f"- Arch: `{profile.get('arch')}` | cores: `{profile.get('cores')}` | RAM: `{profile.get('mem_total_kb')} KB`")
    lines.append("")

    ver = ndmc_snippet(work, "ndmc_show_version.txt", 60)
    if ver:
        lines.append("## KeeneticOS (ndmc) — version/platform (snippet)")
        lines.append("")
        lines.append("```")
        lines.append(ver)
        lines.append("```")
        lines.append("")

    lines.append("## Management / API / RCI visibility (HTTP probe)")
    if http_sum["highlights"]:
        lines.append("")
        lines.append("Highlights:")
        for h in http_sum["highlights"][:60]:
            lines.append(f"- {h}")
        lines.append("")
        lines.append("Interpretation:")
        lines.append("- `401/403` often means the endpoint exists but requires authentication.")
        lines.append("- `200/30x` means the web UI/proxy is alive.")
    else:
        lines.append("")
        lines.append("No HTTP probe responses (possible: no curl, ports closed, only LAN IP allowed, services disabled).")

    lines.append("")
    lines.append("Manual checks:")
    lines.append("```sh")
    lines.append("curl -k -I http://127.0.0.1:79/rci/show/system")
    lines.append("# If enabled and you have admin credentials:")
    lines.append("# curl --digest -u admin:PASS http://ROUTER_IP/rci/show/system")
    lines.append("```")
    lines.append("")

    lines.append("## OPKG event hooks (/opt/etc/ndm/*.d)")
    if hooks:
        lines.append("")
        lines.append("Detected hook directories:")
        for h in hooks:
            hint = h.get("hint_ru") or "event"
            lines.append(f"- `{h['rel']}` — {hint}")
            scripts = h.get("scripts") or []
            if scripts:
                names = ", ".join(s["name"] for s in scripts[:12])
                more = "" if len(scripts) <= 12 else f" … (+{len(scripts)-12})"
                lines.append(f"  - scripts: {names}{more}")
    else:
        lines.append("")
        lines.append("No `*/etc/ndm/*.d` was found in the `fs/` mirror (OPKG missing or empty).")

    lines.append("")
    lines.append("### Hook constraints (so you don’t kill the router)")
    lines.append("")
    lines.append("- Hooks are executed by `ndm` and have a runtime limit (typically ~24 seconds).")
    lines.append("- Hooks may be queued (next hook starts only after the previous one finishes).")
    lines.append("- Keep hooks fast: write to a spool, send Telegram from a separate daemon.")
    lines.append("")

    lines.append("## Telegram notifications (recommended scheme)")
    lines.append("")
    lines.append("1) Hook → append event to `/opt/var/spool/kmp/events.ndjson` (one JSON line per event).")
    lines.append("2) Entware daemon `kmp-tg` reads spool, rate-limits, sends Telegram messages.")
    lines.append("3) Manage it via `entwarectl restart kmp-tg`.")
    lines.append("")

    lines.append("## Entware services (/opt/etc/init.d)")
    if services:
        lines.append("")
        lines.append(f"Init scripts found: {len(services)}")
        for svc in services[:40]:
            lines.append(f"- `{svc.get('script')}` (exec={svc.get('executable')}, size={svc.get('size')})")
        if len(services) > 40:
            lines.append(f"... (+{len(services)-40})")
    else:
        lines.append("")
        lines.append("No services inventory found (`entware/services.json` missing).")

    lines.append("")
    lines.append("Unified control: `entwarectl list/start/stop/restart/status`.")
    lines.append("")

    lines.append("## KeeneticOS command map (ndmc / RCI)")
    lines.append("")
    for cmd, desc in NDMC_MAP_RU:
        lines.append(f"- `ndmc -c '{cmd}'` — {desc}")
        lines.append(f"  - (if RCI enabled) `GET /rci/{cmd.replace(' ', '/')}`")
    lines.append("")

    lines.append("## What to share for analysis")
    lines.append("")
    lines.append("- `analysis/REPORT_EN.md`")
    lines.append("- `analysis/SENSITIVE_LOCATIONS.md`")
    lines.append("- `meta/run.log` and `meta/errors.log`")

    return "\n".join(lines) + "\n"


def cmd_services_json(initd: Path) -> int:
    services: List[Dict[str, Any]] = []
    if not initd.exists():
        print("[]")
        return 0

    for p in sorted(initd.iterdir()):
        if not p.is_file():
            continue
        services.append(
            {
                "script": p.name,
                "path": str(p),
                "executable": os.access(p, os.X_OK),
                "size": p.stat().st_size,
                "sha256": sha256_file(p, max_bytes=2_000_000),
            }
        )

    json.dump(services, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_inventory(work: Path, stdout: bool) -> int:
    inv: Dict[str, Any] = {
        "tool": "keenetic-maxprobe",
        "analyzer_version": VERSION,
        "ts_utc": utc_now(),
        "work": str(work),
        "present": {
            "meta": (work / "meta").exists(),
            "fs": (work / "fs").exists(),
            "net": (work / "net").exists(),
            "ndm": (work / "ndm").exists(),
            "entware": (work / "entware").exists(),
        },
        "hooks": enumerate_hook_dirs(work / "fs"),
    }
    meta = work / "meta" / "profile_selected.json"
    if meta.exists():
        try:
            inv["profile"] = json.loads(meta.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass

    if stdout:
        json.dump(inv, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        (work / "analysis").mkdir(parents=True, exist_ok=True)
        (work / "analysis" / "inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def cmd_report(work: Path) -> int:
    analysis = work / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)

    ru = generate_report_ru(work)
    en = generate_report_en(work)

    (analysis / "REPORT_RU.md").write_text(ru, encoding="utf-8")
    (analysis / "REPORT_EN.md").write_text(en, encoding="utf-8")

    print(f"[+] Report generated: {analysis/'REPORT_RU.md'}")
    print(f"[+] Report generated: {analysis/'REPORT_EN.md'}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="analyze.py")
    ap.add_argument("--version", action="store_true", help="print version")
    ap.add_argument("--inventory", metavar="WORK", type=Path, help="generate inventory JSON")
    ap.add_argument("--stdout", action="store_true", help="print inventory to stdout")
    ap.add_argument("--services-json", metavar="INITD", type=Path, help="print services.json to stdout for /opt/etc/init.d")
    ap.add_argument("--report", metavar="WORK", type=Path, help="generate REPORT_RU.md and REPORT_EN.md into WORK/analysis")

    args = ap.parse_args(argv)

    if args.version:
        print(VERSION)
        return 0

    if args.services_json:
        return cmd_services_json(args.services_json)

    if args.inventory:
        return cmd_inventory(args.inventory, stdout=args.stdout)

    if args.report:
        return cmd_report(args.report)

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
