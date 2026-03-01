#!/usr/bin/env python3
"""
keenetic-maxprobe analyzer (offline)

Input: WORKDIR produced by bin/keenetic-maxprobe
Output:
  - analysis/INVENTORY.json (machine readable)
  - analysis/REPORT_RU.md / analysis/REPORT_EN.md (human readable)

This analyzer is designed to be safe to run on the router itself (no external deps).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


VERSION = "0.7.1"


def read_text(path: Path, limit: int = 2_000_000) -> str:
    try:
        data = path.read_bytes()
        if len(data) > limit:
            data = data[:limit] + b"\n...<truncated>...\n"
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(read_text(path))
    except Exception:
        return None


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def md_escape(s: str) -> str:
    # minimal escape for Markdown tables/lists
    return s.replace("\r", "").replace("\t", " ").replace("|", "\\|")


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ["KiB", "MiB", "GiB", "TiB"]:
        n = n / 1024.0
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} PiB"


@dataclass
class HttpHit:
    host: str
    port: int
    scheme: str
    path: str
    code: int
    note: str
    bytes: Optional[int] = None


def parse_tsv_lines(text: str) -> List[List[str]]:
    rows: List[List[str]] = []
    for ln in text.splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        rows.append(ln.split("\t"))
    return rows


def parse_listen_ports_tsv(path: Path) -> List[Tuple[str, str, int]]:
    txt = read_text(path)
    out: List[Tuple[str, str, int]] = []
    for row in parse_tsv_lines(txt):
        # proto ip port state source
        if len(row) < 3:
            continue
        proto, ip, port_s = row[0], row[1], row[2]
        try:
            port = int(port_s)
        except Exception:
            continue
        out.append((proto, ip, port))
    # unique
    seen = set()
    uniq: List[Tuple[str, str, int]] = []
    for t in out:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq


def parse_http_probe(path: Path) -> List[HttpHit]:
    txt = read_text(path)
    hits: List[HttpHit] = []
    for row in parse_tsv_lines(txt):
        # ts host port scheme path code note
        if len(row) < 7:
            continue
        host = row[1]
        try:
            port = int(row[2])
        except Exception:
            continue
        scheme = row[3]
        pth = row[4]
        try:
            code = int(row[5])
        except Exception:
            code = 0
        note = row[6]
        hits.append(HttpHit(host=host, port=port, scheme=scheme, path=pth, code=code, note=note))
    return hits


def parse_web_probe(path: Path) -> List[HttpHit]:
    txt = read_text(path)
    hits: List[HttpHit] = []
    for row in parse_tsv_lines(txt):
        # ts host port scheme path code bytes
        if len(row) < 7:
            continue
        host = row[1]
        try:
            port = int(row[2])
        except Exception:
            continue
        scheme = row[3]
        pth = row[4]
        try:
            code = int(row[5])
        except Exception:
            code = 0
        try:
            b = int(row[6])
        except Exception:
            b = None
        hits.append(HttpHit(host=host, port=port, scheme=scheme, path=pth, code=code, note="", bytes=b))
    return hits


def detect_keeneticos_version(workdir: Path) -> str:
    # Best-effort from ndmc_show_version.txt
    p = workdir / "ndm" / "ndmc_show_version.txt"
    if p.exists():
        t = read_text(p, limit=30_000).strip()
        # shorten
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        return " ".join(lines[:2])[:200]
    return ""


def read_opkg_list(workdir: Path) -> List[str]:
    p = workdir / "entware" / "opkg_list_installed.txt"
    txt = read_text(p, limit=3_000_000)
    pkgs: List[str] = []
    for ln in txt.splitlines():
        parts = ln.split()
        if parts:
            pkgs.append(parts[0])
    return sorted(set(pkgs))


def read_services(workdir: Path) -> List[Dict[str, Any]]:
    p = workdir / "entware" / "services.json"
    data = read_json(p)
    if isinstance(data, list):
        out: List[Dict[str, Any]] = []
        for it in data:
            if isinstance(it, dict):
                out.append(it)
        return out
    return []


def list_ndm_hooks(workdir: Path) -> List[Dict[str, Any]]:
    """
    Scan mirrored filesystem (fs/) for /opt/etc/ndm and /storage/*/ndm and list hook-like scripts.
    """
    fs = workdir / "fs"
    roots = [
        fs / "opt" / "etc" / "ndm",
        fs / "storage" / "etc" / "ndm",
        fs / "etc" / "ndm",
    ]
    found: List[Dict[str, Any]] = []
    for r in roots:
        if not r.exists() or not r.is_dir():
            continue
        for p in sorted(r.rglob("*")):
            if p.is_dir():
                continue
            rel = str(p.relative_to(fs))
            # Focus on likely scripts
            if p.suffix in {".sh", ".rc", ".conf"} or p.name.endswith((".d",)):
                pass
            # Many hooks are plain files without suffix
            if p.stat().st_size > 0 and p.stat().st_size < 2_000_000:
                # classify by parent dir name
                parent = p.parent.name
                hint = ""
                if "hook" in rel:
                    hint = "hook"
                elif "event" in rel:
                    hint = "event"
                elif parent.endswith(".d"):
                    hint = parent
                found.append(
                    {
                        "path": rel,
                        "size": int(p.stat().st_size),
                        "hint": hint,
                    }
                )
    return found[:2000]  # safety cap


def extract_html_title(body_text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", body_text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    t = re.sub(r"\s+", " ", m.group(1)).strip()
    return t[:200]


def guess_web_titles(workdir: Path, web_hits: List[HttpHit]) -> Dict[str, str]:
    """
    Try to map hit -> page title from stored body samples.
    Keys are like: "http://host:port/path".
    """
    titles: Dict[str, str] = {}
    for h in web_hits:
        if h.code in (0, 000):
            continue
        # body path: web/{host}_{port}_{scheme}/{sanitized_path}.body
        port_dir = workdir / "web" / f"{h.host}_{h.port}_{h.scheme}"
        if not port_dir.exists():
            continue
        sp = sanitize_path(h.path)
        body = port_dir / f"{sp}.body"
        if not body.exists():
            continue
        title = extract_html_title(read_text(body, limit=300_000))
        if title:
            titles[f"{h.scheme}://{h.host}:{h.port}{h.path}"] = title
    return titles


def sanitize_path(path: str) -> str:
    # mirrors shell sanitize_path: "/rci/show/system" -> "rci_show_system"
    p = path.lstrip("/")
    p = re.sub(r"[^A-Za-z0-9._-]", "_", p)
    return p or "root"


def classify_api_endpoints(hits: List[HttpHit]) -> Dict[str, List[HttpHit]]:
    """
    Group endpoints by class (rci/ui/unknown) based on path and response codes.
    """
    groups: Dict[str, List[HttpHit]] = {"rci": [], "ui": [], "other": []}
    for h in hits:
        if h.code == 0 or h.code == 000:
            continue
        if h.path.startswith("/rci/"):
            groups["rci"].append(h)
        elif h.path in ("/", "/robots.txt") or h.path.endswith((".html", ".js", ".css")):
            groups["ui"].append(h)
        else:
            groups["other"].append(h)
    return groups


def build_inventory(workdir: Path) -> Dict[str, Any]:
    meta = read_json(workdir / "meta" / "profile_selected.json") or {}
    keen_ver = detect_keeneticos_version(workdir)
    if keen_ver and isinstance(meta, dict):
        meta.setdefault("keeneticos_version", keen_ver)

    ports = parse_listen_ports_tsv(workdir / "net" / "listen_ports.tsv") if (workdir / "net" / "listen_ports.tsv").exists() else []
    http_hits = parse_http_probe(workdir / "net" / "http_probe.tsv") if (workdir / "net" / "http_probe.tsv").exists() else []
    web_hits = parse_web_probe(workdir / "web" / "probe.tsv") if (workdir / "web" / "probe.tsv").exists() else []

    pkgs = read_opkg_list(workdir)
    services = read_services(workdir)
    hooks = list_ndm_hooks(workdir)
    titles = guess_web_titles(workdir, web_hits)

    inv: Dict[str, Any] = {
        "tool": {"name": "keenetic-maxprobe", "version": VERSION},
        "meta": meta,
        "keeneticos_version": keen_ver,
        "listen_ports": [{"proto": p[0], "ip": p[1], "port": p[2]} for p in ports],
        "http_probe": [h.__dict__ for h in http_hits],
        "web_probe": [h.__dict__ for h in web_hits],
        "web_titles": titles,
        "entware": {
            "opkg_installed_count": len(pkgs),
            "opkg_installed": pkgs[:2000],  # cap
            "init_services": services,
        },
        "ndm_hooks": hooks,
    }
    return inv


def md_hits_table(hits: List[HttpHit], titles: Optional[Dict[str, str]] = None, limit: int = 60) -> str:
    titles = titles or {}
    rows = hits[:limit]
    if not rows:
        return "_нет данных_"
    out = []
    out.append("| host | port | scheme | path | code | note | title |")
    out.append("|---|---:|---|---|---:|---|---|")
    for h in rows:
        key = f"{h.scheme}://{h.host}:{h.port}{h.path}"
        title = titles.get(key, "")
        out.append(
            f"| {md_escape(h.host)} | {h.port} | {md_escape(h.scheme)} | `{md_escape(h.path)}` | {h.code} | {md_escape(h.note)} | {md_escape(title)} |"
        )
    return "\n".join(out)


def md_list(items: Iterable[str], limit: int = 50) -> str:
    out = []
    for i, it in enumerate(items):
        if i >= limit:
            out.append(f"- … ({i - limit + 1} more)")
            break
        out.append(f"- {md_escape(it)}")
    return "\n".join(out) if out else "_нет данных_"


def make_report_ru(inv: Dict[str, Any]) -> str:
    meta = inv.get("meta", {}) or {}
    keen_ver = inv.get("keeneticos_version", "") or ""
    ports = inv.get("listen_ports", []) or []
    http_hits = [HttpHit(**h) for h in inv.get("http_probe", []) or [] if isinstance(h, dict)]
    web_hits = [HttpHit(**h) for h in inv.get("web_probe", []) or [] if isinstance(h, dict)]
    titles = inv.get("web_titles", {}) or {}
    hooks = inv.get("ndm_hooks", []) or []
    ent = inv.get("entware", {}) or {}
    pkgs = ent.get("opkg_installed", []) or []
    services = ent.get("init_services", []) or []

    groups = classify_api_endpoints(http_hits)

    # Determine discovered actionable endpoints: anything not 000 and note suggests auth/ok
    discovered = [h for h in http_hits if h.code and h.code != 0 and h.code != 000]
    discovered.sort(key=lambda x: (x.host, x.port, x.path))

    # Determine web surfaces (web_probe)
    web_ok = [h for h in web_hits if h.code and h.code != 0 and h.code != 000]
    web_ok.sort(key=lambda x: (x.host, x.port, x.scheme, x.path))

    lines: List[str] = []
    lines.append(f"# Отчёт keenetic-maxprobe (v{VERSION})")
    lines.append("")
    lines.append("## Сводка")
    lines.append("")
    lines.append(f"- Hostname: `{md_escape(str(meta.get('hostname','')))}'")
    lines.append(f"- Device model: `{md_escape(str(meta.get('device_model','')))}'")
    lines.append(f"- Arch: `{md_escape(str(meta.get('arch','')))}`, cores: `{meta.get('cores','')}`, mem_total_kb: `{meta.get('mem_total_kb','')}`")
    if keen_ver:
        lines.append(f"- KeeneticOS (hint): `{md_escape(keen_ver)}`")
    lines.append(f"- Mode: `{md_escape(str(meta.get('mode','')))}`, profile: `{md_escape(str(meta.get('profile','')))}`, collectors: `{md_escape(str(meta.get('collectors','')))}`")
    lines.append("")

    lines.append("## Открытые порты (по факту)")
    lines.append("")
    if ports:
        # show top unique ports
        uniq_ports = sorted({p["port"] for p in ports if isinstance(p, dict) and isinstance(p.get("port"), int)})
        lines.append(f"Портов обнаружено: **{len(uniq_ports)}**")
        lines.append("")
        lines.append(md_list([str(p) for p in uniq_ports], limit=60))
    else:
        lines.append("_нет данных_")
    lines.append("")

    lines.append("## Web поверхности и API эндпойнты")
    lines.append("")
    lines.append("### RCI / HTTP probe (обнаружено)")
    lines.append("")
    if discovered:
        # prioritize rci hits
        rci_hits = groups["rci"]
        ui_hits = groups["ui"]
        other_hits = groups["other"]
        if rci_hits:
            lines.append("**RCI-подобные пути:**")
            lines.append("")
            lines.append(md_hits_table(sorted(rci_hits, key=lambda x: (x.host, x.port, x.path)), titles=None, limit=60))
            lines.append("")
        if other_hits:
            lines.append("**Прочие пути:**")
            lines.append("")
            lines.append(md_hits_table(sorted(other_hits, key=lambda x: (x.host, x.port, x.path)), titles=None, limit=40))
            lines.append("")
        if ui_hits:
            lines.append("**UI/корень:**")
            lines.append("")
            lines.append(md_hits_table(sorted(ui_hits, key=lambda x: (x.host, x.port, x.path)), titles=None, limit=20))
            lines.append("")
    else:
        lines.append("_HTTP probe не нашёл отвечающих эндпойнтов (или curl отсутствует)._")
        lines.append("")

    lines.append("### Web probe (заголовки + sample тела)")
    lines.append("")
    if web_ok:
        lines.append(md_hits_table(web_ok, titles=titles, limit=80))
    else:
        lines.append("_нет данных_")
    lines.append("")

    lines.append("## Entware: сервисы и единый слой управления")
    lines.append("")
    lines.append(f"- Установленных пакетов (по opkg list-installed): **{ent.get('opkg_installed_count', 0)}**")
    lines.append("")
    if services:
        lines.append("### Найдены init.d скрипты (/opt/etc/init.d)")
        lines.append("")
        lines.append("| script | executable | sha256 |")
        lines.append("|---|---:|---|")
        for s in services[:80]:
            lines.append(
                f"| `{md_escape(str(s.get('script','')) )}` | {1 if s.get('executable') else 0} | `{md_escape(str(s.get('sha256','')) )}` |"
            )
        if len(services) > 80:
            lines.append(f"\n_… ещё {len(services)-80} скриптов_")
        lines.append("")
        lines.append("### Предложение: единый слой управления Entware-службами")
        lines.append("")
        lines.append("У большинства Entware‑служб стандартный интерфейс:")
        lines.append("")
        lines.append("```sh")
        lines.append("/opt/etc/init.d/<service> start|stop|restart|status")
        lines.append("```")
        lines.append("")
        lines.append("Для Telegram‑бота удобно сделать «обёртку» (например `entwarectl`) и белый список разрешённых сервисов.")
    else:
        lines.append("_init.d скрипты не найдены (или /opt не смонтирован)._")
    lines.append("")

    lines.append("## NDM hooks: реальные хуки и уведомления Telegram")
    lines.append("")
    if hooks:
        lines.append(f"Найдено файлов/скриптов в ndm‑директориях (cap): **{len(hooks)}**")
        lines.append("")
        # show top 40
        lines.append("| path | size | hint |")
        lines.append("|---|---:|---|")
        for it in hooks[:40]:
            lines.append(f"| `{md_escape(str(it.get('path','')) )}` | {it.get('size',0)} | {md_escape(str(it.get('hint','')))} |")
        if len(hooks) > 40:
            lines.append(f"\n_… ещё {len(hooks)-40} файлов_")
        lines.append("")
        lines.append("### Предложение схемы уведомлений")
        lines.append("")
        lines.append("1) Выбираем события (WAN up/down, VPN up/down, DHCP lease, Wi‑Fi clients, firewall blocks).")
        lines.append("2) В соответствующих hook/event скриптах добавляем вызов «нотификатора» (shell script), который:")
        lines.append("   - формирует короткое сообщение,")
        lines.append("   - отправляет его в Telegram через Bot API (HTTPS).")
        lines.append("")
        lines.append("Мини‑шаблон уведомления (псевдо‑код):")
        lines.append("```sh")
        lines.append('MSG="WAN is down on $(hostname) at $(date -u)"')
        lines.append('curl -sS -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \\')
        lines.append('  -d "chat_id=$CHAT_ID" -d "text=$MSG" >/dev/null')
        lines.append("```")
        lines.append("")
        lines.append("Важно: храните TOKEN/CHAT_ID не в hook-скриптах, а в отдельном защищённом файле (и редактируйте перед шарингом архива).")
    else:
        lines.append("_Хуки NDM не обнаружены (в зеркале fs не найден /opt/etc/ndm и аналоги)._")
    lines.append("")

    lines.append("## «Карта» команд/состояний KeeneticOS для бота")
    lines.append("")
    lines.append("### Рекомендуемый приоритет интерфейсов управления")
    lines.append("")
    lines.append("- **ndmc**: надёжно для чтения состояния и системных команд (`show version`, `show system`, `show interface`, `show log`, `show running-config`).")
    lines.append("- **RCI HTTP**: удобно для бота, если Web UI/RCI доступен (часто требует авторизацию).")
    lines.append("")
    lines.append("### Что уже можно автоматизировать (по данным архива)")
    lines.append("")
    if groups["rci"]:
        # unique rci paths
        rci_paths = sorted({h.path for h in groups["rci"]})
        lines.append("Обнаружены RCI‑пути:")
        lines.append("")
        lines.append(md_list([f"`{p}`" for p in rci_paths], limit=30))
        lines.append("")
    else:
        lines.append("- RCI пути не подтверждены ответом (возможно закрыты/за auth/не на этих портах).")
        lines.append("")

    lines.append("Минимальный набор команд для «health check»:")
    lines.append("")
    lines.append("```sh")
    lines.append("ndmc -c 'show version'")
    lines.append("ndmc -c 'show system'")
    lines.append("ndmc -c 'show interface'")
    lines.append("ndmc -c 'show log'")
    lines.append("```")
    lines.append("")

    lines.append("## Следующие улучшения, которые стоит добавить в maxprobe/бот")
    lines.append("")
    lines.append("- Сделать отдельный **inventory JSON** для бота: порты, RCI пути, init.d сервисы, hook‑скрипты.")
    lines.append("- Добавить «проверку авторизации» для RCI (401/403) и тест Basic/Digest (только локально).")
    lines.append("- Для web‑морды: парсить `Server`/`WWW-Authenticate` заголовки, чтобы понять стек (nginx/lighttpd/uhttpd).")
    lines.append("- Для Entware: собрать `ps`→сопоставить процесс↔порт↔init.d скрипт.")
    lines.append("")
    return "\n".join(lines) + "\n"


def make_report_en(inv: Dict[str, Any]) -> str:
    meta = inv.get("meta", {}) or {}
    keen_ver = inv.get("keeneticos_version", "") or ""
    ports = inv.get("listen_ports", []) or []
    http_hits = [HttpHit(**h) for h in inv.get("http_probe", []) or [] if isinstance(h, dict)]
    web_hits = [HttpHit(**h) for h in inv.get("web_probe", []) or [] if isinstance(h, dict)]
    titles = inv.get("web_titles", {}) or {}
    hooks = inv.get("ndm_hooks", []) or []
    ent = inv.get("entware", {}) or {}
    services = ent.get("init_services", []) or []

    groups = classify_api_endpoints(http_hits)
    discovered = [h for h in http_hits if h.code and h.code != 0 and h.code != 000]
    discovered.sort(key=lambda x: (x.host, x.port, x.path))
    web_ok = [h for h in web_hits if h.code and h.code != 0 and h.code != 000]
    web_ok.sort(key=lambda x: (x.host, x.port, x.scheme, x.path))

    lines: List[str] = []
    lines.append(f"# keenetic-maxprobe report (v{VERSION})")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Hostname: `{md_escape(str(meta.get('hostname','')))}'")
    lines.append(f"- Device model: `{md_escape(str(meta.get('device_model','')))}'")
    lines.append(f"- Arch: `{md_escape(str(meta.get('arch','')))}', cores: `{meta.get('cores','')}`, mem_total_kb: `{meta.get('mem_total_kb','')}`")
    if keen_ver:
        lines.append(f"- KeeneticOS (hint): `{md_escape(keen_ver)}`")
    lines.append(f"- Mode: `{md_escape(str(meta.get('mode','')))}`, profile: `{md_escape(str(meta.get('profile','')))}`, collectors: `{md_escape(str(meta.get('collectors','')))}`")
    lines.append("")

    lines.append("## Listening ports (observed)")
    lines.append("")
    if ports:
        uniq_ports = sorted({p["port"] for p in ports if isinstance(p, dict) and isinstance(p.get("port"), int)})
        lines.append(f"Unique ports: **{len(uniq_ports)}**")
        lines.append("")
        lines.append(md_list([str(p) for p in uniq_ports], limit=60))
    else:
        lines.append("_no data_")
    lines.append("")

    lines.append("## Web surfaces and API endpoints")
    lines.append("")
    lines.append("### RCI / HTTP probe (discovered)")
    lines.append("")
    if discovered:
        rci_hits = groups["rci"]
        other_hits = groups["other"]
        if rci_hits:
            lines.append("**RCI-like paths:**")
            lines.append("")
            lines.append(md_hits_table(sorted(rci_hits, key=lambda x: (x.host, x.port, x.path)), titles=None, limit=60))
            lines.append("")
        if other_hits:
            lines.append("**Other paths:**")
            lines.append("")
            lines.append(md_hits_table(sorted(other_hits, key=lambda x: (x.host, x.port, x.path)), titles=None, limit=40))
            lines.append("")
    else:
        lines.append("_HTTP probe found no responding endpoints (or curl is missing)._")
        lines.append("")

    lines.append("### Web probe (headers + body sample)")
    lines.append("")
    if web_ok:
        lines.append(md_hits_table(web_ok, titles=titles, limit=80))
    else:
        lines.append("_no data_")
    lines.append("")

    lines.append("## Entware: services and unified control layer")
    lines.append("")
    lines.append(f"- Installed packages (opkg list-installed): **{ent.get('opkg_installed_count', 0)}**")
    lines.append("")
    if services:
        lines.append("### init.d scripts found (/opt/etc/init.d)")
        lines.append("")
        lines.append("| script | executable | sha256 |")
        lines.append("|---|---:|---|")
        for s in services[:80]:
            lines.append(
                f"| `{md_escape(str(s.get('script','')) )}` | {1 if s.get('executable') else 0} | `{md_escape(str(s.get('sha256','')) )}` |"
            )
        if len(services) > 80:
            lines.append(f"\n_… {len(services)-80} more scripts_")
        lines.append("")
        lines.append("Suggested unified interface:")
        lines.append("")
        lines.append("```sh")
        lines.append("/opt/etc/init.d/<service> start|stop|restart|status")
        lines.append("```")
    else:
        lines.append("_no init.d scripts found_")
    lines.append("")

    lines.append("## NDM hooks and Telegram notifications")
    lines.append("")
    if hooks:
        lines.append(f"Files/scripts detected in NDM hook dirs (cap): **{len(hooks)}**")
        lines.append("")
        lines.append("| path | size | hint |")
        lines.append("|---|---:|---|")
        for it in hooks[:40]:
            lines.append(f"| `{md_escape(str(it.get('path','')) )}` | {it.get('size',0)} | {md_escape(str(it.get('hint','')))} |")
        if len(hooks) > 40:
            lines.append(f"\n_… {len(hooks)-40} more files_")
        lines.append("")
        lines.append("Telegram notification flow suggestion:")
        lines.append("```sh")
        lines.append('MSG="WAN is down on $(hostname) at $(date -u)"')
        lines.append('curl -sS -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \\')
        lines.append('  -d "chat_id=$CHAT_ID" -d "text=$MSG" >/dev/null')
        lines.append("```")
    else:
        lines.append("_no hooks detected_")
    lines.append("")

    lines.append("## KeeneticOS command/state map for a bot")
    lines.append("")
    lines.append("- Prefer **ndmc** for state snapshots and reliable reads.")
    lines.append("- Prefer **RCI HTTP** for bot-friendly calls when exposed (often needs auth).")
    lines.append("")
    lines.append("Minimal health-check commands:")
    lines.append("```sh")
    lines.append("ndmc -c 'show version'")
    lines.append("ndmc -c 'show system'")
    lines.append("ndmc -c 'show interface'")
    lines.append("ndmc -c 'show log'")
    lines.append("```")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--inventory", action="store_true", help="print JSON inventory")
    ap.add_argument("--report", action="store_true", help="generate reports into analysis/")
    ap.add_argument("--stdout", action="store_true", help="print inventory to stdout (instead of writing a file)")
    args = ap.parse_args()

    workdir = Path(args.workdir).resolve()
    if not workdir.exists():
        raise SystemExit(f"workdir not found: {workdir}")

    inv = build_inventory(workdir)

    if args.inventory:
        if args.stdout:
            print(json.dumps(inv, indent=2, sort_keys=True))
        else:
            write_json(workdir / "analysis" / "INVENTORY.json", inv)
        return 0

    if args.report:
        write_json(workdir / "analysis" / "INVENTORY.json", inv)
        write_text(workdir / "analysis" / "REPORT_RU.md", make_report_ru(inv))
        write_text(workdir / "analysis" / "REPORT_EN.md", make_report_en(inv))
        return 0

    # default: generate report
    write_json(workdir / "analysis" / "INVENTORY.json", inv)
    write_text(workdir / "analysis" / "REPORT_RU.md", make_report_ru(inv))
    write_text(workdir / "analysis" / "REPORT_EN.md", make_report_en(inv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
