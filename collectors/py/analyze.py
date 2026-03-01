#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""keenetic-maxprobe analyzer

This script is intentionally dependency-free (stdlib only).

Input: --workdir <path>
Output:
- analysis/REPORT_RU.md
- analysis/REPORT_EN.md
- analysis/summary.json (for Web UI)

The analyzer must NEVER crash the main probe. It should be best-effort.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def read_text(path: Path, *, max_bytes: int = 512_000) -> str:
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            data = data[:max_bytes]
        # try utf-8, fallback to latin-1
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("latin-1", errors="replace")
    except Exception:
        return ""


def read_first_line(path: Path) -> str:
    txt = read_text(path, max_bytes=4096)
    return (txt.splitlines() or [""])[0].strip()


def safe_json_loads(txt: str) -> Dict[str, Any]:
    try:
        return json.loads(txt)
    except Exception:
        return {}


def parse_listen_ports_tsv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    txt = read_text(path, max_bytes=512_000)
    for line in txt.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        rows.append(
            {
                "proto": parts[0].strip(),
                "ip": parts[1].strip(),
                "port": parts[2].strip(),
                "state": parts[3].strip(),
                "source": parts[4].strip(),
            }
        )
    return rows


def parse_http_probe(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    txt = read_text(path, max_bytes=1_000_000)
    for line in txt.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        rows.append(
            {
                "ts": parts[0],
                "host": parts[1],
                "port": parts[2],
                "scheme": parts[3],
                "path": parts[4],
                "code": parts[5],
                "note": parts[6],
            }
        )
    return rows


def count_lines(path: Path, *, max_lines: int = 20000) -> int:
    try:
        n = 0
        with path.open("rb") as f:
            for _ in f:
                n += 1
                if n >= max_lines:
                    break
        return n
    except Exception:
        return 0


def human_bytes(num: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(num)
    i = 0
    while x >= 1024 and i < len(units) - 1:
        x /= 1024.0
        i += 1
    if i == 0:
        return f"{int(x)} {units[i]}"
    return f"{x:.1f} {units[i]}"


def list_opkg_pkgs(workdir: Path) -> List[str]:
    p = workdir / "entware" / "opkg" / "list_installed.txt"
    if not p.exists():
        p = workdir / "entware" / "opkg_list_installed.txt"
    txt = read_text(p, max_bytes=2_000_000)
    pkgs: List[str] = []
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        # expected: "pkg - version"
        name = line.split()[0]
        if name and name not in pkgs:
            pkgs.append(name)
    return pkgs


def list_services(workdir: Path) -> List[Dict[str, Any]]:
    p = workdir / "entware" / "services.json"
    if not p.exists():
        return []
    return safe_json_loads(read_text(p, max_bytes=2_000_000)) or []


def extract_keenetic_version(workdir: Path) -> str:
    p = workdir / "ndm" / "ndmc_show_version.txt"
    txt = read_text(p, max_bytes=64_000)
    # best-effort: look for first line with digits
    for line in txt.splitlines():
        if re.search(r"\d+\.\d+", line):
            return line.strip()
    return (txt.splitlines() or [""])[0].strip()


def write_report_ru(dst: Path, ctx: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Отчёт keenetic-maxprobe (RU)")
    lines.append("")
    lines.append(f"**Версия инструмента:** {ctx.get('tool_version', '?')}")
    lines.append("")
    lines.append("## Контекст запуска")
    lines.append("")
    lines.append(f"- Hostname: {ctx.get('hostname', '?')}")
    lines.append(f"- Started (UTC): {ctx.get('started_utc', '?')}")
    lines.append(f"- Mode: {ctx.get('mode', '?')}")
    lines.append(f"- Profile: {ctx.get('profile', '?')}")
    lines.append(f"- OPKG (/opt): {ctx.get('opkg_storage_hint', '?')} (fs={ctx.get('opkg_fs_type','?')}, src={ctx.get('opkg_mount_source','?')})")
    lines.append(f"- Output base: {ctx.get('outbase', '?')}")
    lines.append("")
    if ctx.get("keenetic_version"):
        lines.append("## KeeneticOS")
        lines.append("")
        lines.append(f"- ndmc show version: {ctx.get('keenetic_version')}")
        lines.append("")
    lines.append("## Краткие итоги")
    lines.append("")
    lines.append(f"- Установленных opkg пакетов: **{ctx.get('opkg_pkg_count', 0)}**")
    lines.append(f"- init.d скриптов: **{ctx.get('services_count', 0)}**")
    lines.append(f"- Слушающих портов (по ss/netstat): **{ctx.get('listen_ports_count', 0)}**")
    if ctx.get("listen_ports_list"):
        lines.append(f"  - Порты: {', '.join(ctx['listen_ports_list'])}")
    lines.append(f"- HTTP probe записей: **{ctx.get('http_probe_count', 0)}**")
    lines.append("")
    if ctx.get("http_probe_ok"):
        lines.append("### Доступные HTTP/RCI эндпоинты (200/30x/401/403)")
        lines.append("")
        for item in ctx["http_probe_ok"][:25]:
            lines.append(f"- {item}")
        if len(ctx["http_probe_ok"]) > 25:
            lines.append(f"- … ещё {len(ctx['http_probe_ok']) - 25}")
        lines.append("")

    if ctx.get("warnings"):
        lines.append("## Предупреждения")
        lines.append("")
        for w in ctx["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## Где смотреть подробности")
    lines.append("")
    lines.append("- Главный лог: `meta/run.log`")
    lines.append("- Ошибки/варнинги: `meta/errors.log`")
    lines.append("- Команды: `meta/commands.tsv`")
    lines.append("")
    lines.append("## Безопасность")
    lines.append("")
    lines.append("Перед отправкой третьим лицам проверьте:")
    lines.append("- `analysis/SENSITIVE_LOCATIONS.md`")
    lines.append("- `analysis/SENSITIVE_PATTERNS.tsv`")
    lines.append("- `analysis/REDACTION_GUIDE_RU.md`")
    lines.append("")

    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report_en(dst: Path, ctx: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# keenetic-maxprobe report (EN)")
    lines.append("")
    lines.append(f"**Tool version:** {ctx.get('tool_version', '?')}")
    lines.append("")
    lines.append("## Run context")
    lines.append("")
    lines.append(f"- Hostname: {ctx.get('hostname', '?')}")
    lines.append(f"- Started (UTC): {ctx.get('started_utc', '?')}")
    lines.append(f"- Mode: {ctx.get('mode', '?')}")
    lines.append(f"- Profile: {ctx.get('profile', '?')}")
    lines.append(
        f"- OPKG (/opt): {ctx.get('opkg_storage_hint', '?')} (fs={ctx.get('opkg_fs_type','?')}, src={ctx.get('opkg_mount_source','?')})"
    )
    lines.append(f"- Output base: {ctx.get('outbase', '?')}")
    lines.append("")
    if ctx.get("keenetic_version"):
        lines.append("## KeeneticOS")
        lines.append("")
        lines.append(f"- ndmc show version: {ctx.get('keenetic_version')}")
        lines.append("")

    lines.append("## Highlights")
    lines.append("")
    lines.append(f"- Installed opkg packages: **{ctx.get('opkg_pkg_count', 0)}**")
    lines.append(f"- init.d scripts: **{ctx.get('services_count', 0)}**")
    lines.append(f"- Listening ports (ss/netstat): **{ctx.get('listen_ports_count', 0)}**")
    if ctx.get("listen_ports_list"):
        lines.append(f"  - Ports: {', '.join(ctx['listen_ports_list'])}")
    lines.append(f"- HTTP probe records: **{ctx.get('http_probe_count', 0)}**")
    lines.append("")

    if ctx.get("http_probe_ok"):
        lines.append("### Reachable HTTP/RCI endpoints (200/30x/401/403)")
        lines.append("")
        for item in ctx["http_probe_ok"][:25]:
            lines.append(f"- {item}")
        if len(ctx["http_probe_ok"]) > 25:
            lines.append(f"- … plus {len(ctx['http_probe_ok']) - 25} more")
        lines.append("")

    if ctx.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for w in ctx["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## Where to look")
    lines.append("")
    lines.append("- Main log: `meta/run.log`")
    lines.append("- Errors/Warns: `meta/errors.log`")
    lines.append("- Commands: `meta/commands.tsv`")
    lines.append("")

    lines.append("## Security")
    lines.append("")
    lines.append("Before sharing, review:")
    lines.append("- `analysis/SENSITIVE_LOCATIONS.md`")
    lines.append("- `analysis/SENSITIVE_PATTERNS.tsv`")
    lines.append("- `analysis/REDACTION_GUIDE_EN.md`")
    lines.append("")

    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    args = ap.parse_args()

    workdir = Path(args.workdir)
    analysis = workdir / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)

    ctx: Dict[str, Any] = {}

    # Meta
    ctx["tool_version"] = read_first_line(workdir / "meta" / "tool_version.txt")
    ctx["hostname"] = read_first_line(workdir / "meta" / "hostname.txt")
    ctx["started_utc"] = read_first_line(workdir / "meta" / "started_utc.txt")
    ctx["outbase"] = read_first_line(workdir / "meta" / "outbase.txt")

    ctx["opkg_storage_hint"] = read_first_line(workdir / "meta" / "opkg_storage_hint.txt")
    ctx["opkg_mount_source"] = read_first_line(workdir / "meta" / "opkg_mount_source.txt")
    ctx["opkg_fs_type"] = read_first_line(workdir / "meta" / "opkg_fs_type.txt")

    prof = safe_json_loads(read_text(workdir / "meta" / "profile_selected.json", max_bytes=64_000))
    ctx["mode"] = prof.get("mode") or ""
    ctx["profile"] = prof.get("profile") or ""

    # KeeneticOS version string
    ctx["keenetic_version"] = extract_keenetic_version(workdir)

    # OPKG
    pkgs = list_opkg_pkgs(workdir)
    ctx["opkg_pkg_count"] = len(pkgs)

    services = list_services(workdir)
    ctx["services_count"] = len(services)

    # Network
    listen_rows = parse_listen_ports_tsv(workdir / "net" / "listen_ports.tsv")
    ports = sorted({r["port"] for r in listen_rows if r.get("port")})
    ctx["listen_ports_count"] = len(ports)
    ctx["listen_ports_list"] = ports[:50]

    http_rows = parse_http_probe(workdir / "net" / "http_probe.tsv")
    ctx["http_probe_count"] = len(http_rows)
    ok = []
    for r in http_rows:
        code = (r.get("code") or "").strip()
        if code.startswith("200") or code.startswith("30") or code in {"401", "403"}:
            ok.append(f"{r.get('scheme','')}://{r.get('host','')}:{r.get('port','')}{r.get('path','')}")
    ctx["http_probe_ok"] = sorted(set(ok))

    # Errors
    err_lines = count_lines(workdir / "meta" / "errors.log")
    ctx["errors_count"] = err_lines

    warnings: List[str] = []
    if err_lines > 0:
        warnings.append(f"Errors/warnings logged: {err_lines} lines (see meta/errors.log)")

    outbase = ctx.get("outbase") or ""
    if outbase.startswith("/var/tmp"):
        warnings.append("Output base is /var/tmp (RAM). If archive fails due to space, set OUTBASE_POLICY=entware or --outbase.")

    if ctx.get("opkg_storage_hint") == "internal":
        warnings.append("OPKG (/opt) seems to be on internal storage. Consider RAM output to reduce NAND wear.")

    ctx["warnings"] = warnings

    # Write reports
    try:
        write_report_ru(analysis / "REPORT_RU.md", ctx)
    except Exception as e:
        (analysis / "python_analyze_error_ru.txt").write_text(str(e) + "\n", encoding="utf-8")

    try:
        write_report_en(analysis / "REPORT_EN.md", ctx)
    except Exception as e:
        (analysis / "python_analyze_error_en.txt").write_text(str(e) + "\n", encoding="utf-8")

    # summary.json
    try:
        (analysis / "summary.json").write_text(json.dumps(ctx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
