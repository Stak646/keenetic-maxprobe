#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""keenetic-maxprobe Web UI server (stdlib-only).

Features:
- Start/stop probe runs with parameters
- Status/progress/log tail
- List & download archives (.tar.gz + .sha256)
- Optional token-based auth for API endpoints

Security note:
- Static UI is public, but API requires token.
- If you bind to 0.0.0.0 the UI becomes available to the whole LAN. Token is required.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DEFAULTS: Dict[str, Any] = {
    "LANG_UI": "ru",
    "PROFILE": "auto",
    "MODE": "full",
    "COLLECTORS": "all",
    "CUSTOM_COLLECTORS": "",
    "OUTBASE_POLICY": "auto",
    "OUTBASE_OVERRIDE": "",
    "CLEAN_OLD": "0",
    "CLEAN_TMP": "0",
    "DEBUG": "1",
    "SPINNER": "0",  # Web UI should not show spinner by default (server handles progress)
    "YES": "1",
    "NO_INSTALL": "0",
    "DEPS_LEVEL": "core",
    "DEPS_MODE": "cleanup",
    "MAX_CPU": "85",
    "MAX_MEM": "95",
    "JOBS": "auto",
    "WEB_BIND": "0.0.0.0",
    "WEB_PORT": "0",
    "WEB_TOKEN": "",
}

ALLOWED: Dict[str, List[str]] = {
    "LANG_UI": ["ru", "en"],
    "PROFILE": ["auto", "forensic", "diagnostic", "lite"],
    "MODE": ["safe", "full", "extream"],
    "COLLECTORS": ["all", "shonly", "shpy", "custom"],
    "OUTBASE_POLICY": ["auto", "ram", "entware"],
    "DEPS_LEVEL": ["core", "collectors"],
    "DEPS_MODE": ["cleanup", "keep"],
    "JOBS": ["auto"],  # can also be a number string
}


def load_shell_config(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        data[k] = v
    return data


def save_shell_config(path: Path, updates: Dict[str, str]) -> None:
    # Minimal rewrite preserving comments when possible:
    existing_lines = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        existing_lines = ["# keenetic-maxprobe config", ""]

    out_lines: List[str] = []
    seen = set()
    for line in existing_lines:
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m:
            k = m.group(1)
            if k in updates:
                v = updates[k]
                out_lines.append(f'{k}="{v}"')
                seen.add(k)
                continue
        out_lines.append(line)

    # append new keys
    for k, v in updates.items():
        if k in seen:
            continue
        out_lines.append(f'{k}="{v}"')

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def tail_text(path: Path, max_bytes: int = 64_000) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size <= max_bytes:
                f.seek(0)
                data = f.read()
            else:
                f.seek(-max_bytes, os.SEEK_END)
                data = f.read()
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


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


@dataclass
class RunState:
    proc: Optional[subprocess.Popen]
    started_ts: float
    cmd: List[str]


class App:
    def __init__(self, *, bind: str, port: int, lang: str, probe_bin: Path, outbase: str, config: Path, token: str, static_root: Path):
        self.bind = bind
        self.port = port
        self.lang = lang
        self.probe_bin = probe_bin
        self.outbase = outbase
        self.config = config
        self.token = token
        self.static_root = static_root
        self.lock = threading.Lock()
        self.run_state = RunState(proc=None, started_ts=0.0, cmd=[])

    # ---------- auth ----------
    def check_token(self, handler: BaseHTTPRequestHandler) -> bool:
        # Allow token via:
        # - X-KMP-Token header
        # - Authorization: Bearer <token>
        # - ?token=...
        token = ""
        hdr = handler.headers.get("X-KMP-Token")
        if hdr:
            token = hdr.strip()
        auth = handler.headers.get("Authorization")
        if (not token) and auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1].strip()
        if not token:
            qs = parse_qs(urlparse(handler.path).query)
            token = (qs.get("token") or [""])[0]
        if not self.token:
            return True
        return bool(token) and token == self.token

    # ---------- files / scanning ----------
    def candidate_outbases(self) -> List[Path]:
        cand: List[Path] = []
        if self.outbase:
            cand.append(Path(self.outbase))
        cfg = load_shell_config(self.config)
        ov = (cfg.get("OUTBASE_OVERRIDE") or "").strip()
        if ov:
            cand.append(Path(ov))
        # likely locations
        cand += [Path(p) for p in ["/var/tmp", "/opt/var/tmp", "/opt/tmp", "/storage/var/tmp", "/storage/tmp", "/tmp"]]
        # unique + existing
        uniq: List[Path] = []
        for p in cand:
            if str(p) in {str(x) for x in uniq}:
                continue
            if p.exists() and p.is_dir():
                uniq.append(p)
        return uniq


    def find_latest_archive(self) -> Optional[Path]:
        # Only .tar.gz archives (exclude .sha256)
        archives: List[Tuple[float, Path]] = []
        for base in self.candidate_outbases():
            for p in base.glob("keenetic-maxprobe-*.tar.gz"):
                if not p.is_file():
                    continue
                try:
                    archives.append((p.stat().st_mtime, p))
                except Exception:
                    continue
        if not archives:
            return None
        archives.sort(key=lambda x: x[0], reverse=True)
        return archives[0][1]

    def extract_member_text(self, archive: Path, member: str, *, max_bytes: int = 256_000) -> str:
        """Extract a small text member from a .tar.gz without unpacking."""
        try:
            with tarfile.open(archive, mode="r:gz") as tf:
                ti = None
                try:
                    ti = tf.getmember(member)
                except KeyError:
                    # Sometimes tar stores without leading './'
                    try:
                        ti = tf.getmember(member.lstrip("./"))
                    except KeyError:
                        return ""
                f = tf.extractfile(ti) if ti else None
                if not f:
                    return ""
                data = f.read(max_bytes)
                try:
                    return data.decode("utf-8", errors="replace")
                except Exception:
                    return data.decode("latin-1", errors="replace")
        except Exception:
            return ""
    def list_archives(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for base in self.candidate_outbases():
            for p in base.glob("keenetic-maxprobe-*.tar.gz"):
                try:
                    st = p.stat()
                    out.append(
                        {
                            "name": p.name,
                            "path": str(p),
                            "base": str(base),
                            "size": st.st_size,
                            "size_h": human_bytes(st.st_size),
                            "mtime": st.st_mtime,
                        }
                    )
                except Exception:
                    continue
            for p in base.glob("keenetic-maxprobe-*.tar.gz.sha256"):
                # also list sha256 files as separate entries
                try:
                    st = p.stat()
                    out.append(
                        {
                            "name": p.name,
                            "path": str(p),
                            "base": str(base),
                            "size": st.st_size,
                            "size_h": human_bytes(st.st_size),
                            "mtime": st.st_mtime,
                        }
                    )
                except Exception:
                    continue
        out.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        return out

    def find_latest_workdir(self) -> Optional[Path]:
        workdirs: List[Tuple[float, Path]] = []
        for base in self.candidate_outbases():
            for p in base.glob("keenetic-maxprobe-*.work"):
                if not p.is_dir():
                    continue
                try:
                    workdirs.append((p.stat().st_mtime, p))
                except Exception:
                    continue
        if not workdirs:
            return None
        workdirs.sort(key=lambda x: x[0], reverse=True)
        return workdirs[0][1]

    def read_progress(self, workdir: Path) -> Dict[str, Any]:
        meta = workdir / "meta"
        phase = (meta / "phase.txt").read_text(encoding="utf-8", errors="replace").strip() if (meta / "phase.txt").exists() else ""
        prog = (meta / "progress.txt").read_text(encoding="utf-8", errors="replace").strip() if (meta / "progress.txt").exists() else ""
        started = (meta / "started_utc.txt").read_text(encoding="utf-8", errors="replace").strip() if (meta / "started_utc.txt").exists() else ""
        opkg_hint = (meta / "opkg_storage_hint.txt").read_text(encoding="utf-8", errors="replace").strip() if (meta / "opkg_storage_hint.txt").exists() else ""
        outbase = (meta / "outbase.txt").read_text(encoding="utf-8", errors="replace").strip() if (meta / "outbase.txt").exists() else ""
        return {"phase": phase, "progress": prog, "started_utc": started, "opkg_storage_hint": opkg_hint, "outbase": outbase}

    # ---------- run control ----------
    def start_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if self.run_state.proc and self.run_state.proc.poll() is None:
                return {"ok": False, "error": "Probe is already running"}

            cmd = self.build_command(params)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.run_state = RunState(proc=proc, started_ts=time.time(), cmd=cmd)
            return {"ok": True, "pid": proc.pid, "cmd": cmd}

    def stop_run(self) -> Dict[str, Any]:
        with self.lock:
            proc = self.run_state.proc
            if not proc or proc.poll() is not None:
                self.run_state = RunState(proc=None, started_ts=0.0, cmd=[])
                return {"ok": True, "stopped": False, "note": "Not running"}
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except Exception:
                    proc.kill()
            except Exception:
                pass
            self.run_state = RunState(proc=None, started_ts=0.0, cmd=[])
            return {"ok": True, "stopped": True}

    def build_command(self, params: Dict[str, Any]) -> List[str]:
        # Always run with --yes and --no-spinner (Web UI shows progress).
        # Validate values; ignore unknown keys.
        cfg = load_shell_config(self.config)
        eff: Dict[str, str] = {**DEFAULTS, **cfg}

        def pick(key: str, allowed: Optional[List[str]] = None) -> str:
            v = str(params.get(key, "")).strip()
            if not v:
                return eff.get(key, "")
            if allowed is not None and v not in allowed:
                return eff.get(key, "")
            return v

        lang = pick("LANG_UI", ALLOWED["LANG_UI"])
        mode = pick("MODE", ALLOWED["MODE"])
        profile = pick("PROFILE", ALLOWED["PROFILE"])
        collectors = pick("COLLECTORS", ALLOWED["COLLECTORS"])
        custom_collectors = str(params.get("CUSTOM_COLLECTORS", eff.get("CUSTOM_COLLECTORS", ""))).strip()

        outbase_policy = pick("OUTBASE_POLICY", ALLOWED["OUTBASE_POLICY"])
        outbase_override = str(params.get("OUTBASE_OVERRIDE", eff.get("OUTBASE_OVERRIDE", ""))).strip()

        # bool-ish flags
        clean_old = bool(params.get("CLEAN_OLD", eff.get("CLEAN_OLD", "0") in {"1", "true", "yes"}))
        clean_tmp = bool(params.get("CLEAN_TMP", eff.get("CLEAN_TMP", "0") in {"1", "true", "yes"}))
        debug = bool(params.get("DEBUG", True))
        no_install = bool(params.get("NO_INSTALL", False))

        deps_level = pick("DEPS_LEVEL", ALLOWED["DEPS_LEVEL"])
        deps_mode = pick("DEPS_MODE", ALLOWED["DEPS_MODE"])

        max_cpu = str(params.get("MAX_CPU", eff.get("MAX_CPU", "85"))).strip()
        max_mem = str(params.get("MAX_MEM", eff.get("MAX_MEM", "95"))).strip()
        jobs = str(params.get("JOBS", eff.get("JOBS", "auto"))).strip()

        cmd: List[str] = [str(self.probe_bin)]

        cmd += ["--lang", lang]
        cmd += ["--mode", mode]
        cmd += ["--profile", profile]
        cmd += ["--collectors", collectors]
        if collectors == "custom" and custom_collectors:
            cmd += ["--custom-collectors", custom_collectors]

        cmd += ["--outbase-policy", outbase_policy]
        if outbase_override:
            # Only allow absolute paths under known candidates
            p = Path(outbase_override)
            if p.is_absolute():
                cmd += ["--outbase", outbase_override]

        cmd += ["--deps-level", deps_level]
        cmd += ["--deps-mode", deps_mode]

        cmd += ["--max-cpu", max_cpu]
        cmd += ["--max-mem", max_mem]
        cmd += ["--jobs", jobs]

        if clean_old:
            cmd.append("--clean-old")
        if clean_tmp:
            cmd.append("--clean-tmp")

        if no_install:
            cmd.append("--no-install")

        if debug:
            cmd.append("--debug")
        else:
            cmd.append("--no-debug")

        # spinner off for UI
        cmd.append("--no-spinner")
        cmd.append("--yes")

        return cmd

    # ---------- status ----------
    def get_status(self) -> Dict[str, Any]:
        latest = self.find_latest_workdir()
        latest_info: Dict[str, Any] = {}
        if latest:
            latest_info = {"workdir": str(latest), **self.read_progress(latest)}
            # summary.json if present
            summ = latest / "analysis" / "summary.json"
            if summ.exists():
                try:
                    latest_info["summary"] = json.loads(summ.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    latest_info["summary"] = None

        else:
            # fallback: use latest archive to extract analysis/summary.json
            arch = self.find_latest_archive()
            if arch:
                latest_info = {"archive": str(arch)}
                txt = self.extract_member_text(arch, "./analysis/summary.json", max_bytes=512_000)
                if txt:
                    try:
                        latest_info["summary"] = json.loads(txt)
                    except Exception:
                        latest_info["summary"] = None

        with self.lock:
            running = bool(self.run_state.proc and self.run_state.proc.poll() is None)
            pid = self.run_state.proc.pid if running and self.run_state.proc else None
            cmd = self.run_state.cmd

        return {
            "ok": True,
            "running": running,
            "pid": pid,
            "cmd": cmd,
            "latest": latest_info,
            "archives": self.list_archives()[:50],
            "server": {"bind": self.bind, "port": self.port, "lang": self.lang},
            "config_path": str(self.config),
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "keenetic-maxprobe-webui/0.8.1"

    def do_GET(self) -> None:
        app: App = self.server.app  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self.serve_static("index.html")
        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            return self.serve_static(rel)

        if path.startswith("/download/"):
            if not app.check_token(self):
                return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            name = path[len("/download/") :]
            return self.serve_download(name)

        if path.startswith("/api/"):
            if not app.check_token(self):
                return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return self.handle_api_get(path, parsed)

        return self._text("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        app: App = self.server.app  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            if not app.check_token(self):
                return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return self.handle_api_post(path)

        return self._text("Not found", HTTPStatus.NOT_FOUND)

    # ---------- API ----------
    def handle_api_get(self, path: str, parsed) -> None:
        app: App = self.server.app  # type: ignore[attr-defined]

        if path == "/api/ping":
            return self._json({"ok": True, "time": time.time()}, HTTPStatus.OK)

        if path == "/api/status":
            return self._json(app.get_status(), HTTPStatus.OK)

        if path == "/api/config":
            cfg = load_shell_config(app.config)
            eff = {**DEFAULTS, **cfg}
            return self._json(
                {
                    "ok": True,
                    "config": eff,
                    "allowed": ALLOWED,
                },
                HTTPStatus.OK,
            )

        if path == "/api/log":
            qs = parse_qs(parsed.query)
            kind = (qs.get("kind") or ["run"])[0]

            latest = app.find_latest_workdir()
            if latest:
                meta = latest / "meta"
                if kind == "errors":
                    p = meta / "errors.log"
                else:
                    p = meta / "run.log"
                return self._json({"ok": True, "text": tail_text(p)}, HTTPStatus.OK)

            # fallback: try to read from latest archive (head only)
            arch = app.find_latest_archive()
            if not arch:
                return self._json({"ok": True, "text": ""}, HTTPStatus.OK)
            member = "./meta/errors.log" if kind == "errors" else "./meta/run.log"
            txt = app.extract_member_text(arch, member, max_bytes=256_000)
            return self._json({"ok": True, "text": txt, "note": "from_archive_head"}, HTTPStatus.OK)


        if path == "/api/report":
            qs = parse_qs(parsed.query)
            lang = (qs.get("lang") or ["ru"])[0]

            # Prefer latest workdir (during run)
            latest = app.find_latest_workdir()
            if latest:
                analysis = latest / "analysis"
                p = analysis / ("REPORT_EN.md" if lang == "en" else "REPORT_RU.md")
                return self._json({"ok": True, "text": tail_text(p, max_bytes=256_000)}, HTTPStatus.OK)

            # Fallback: extract from latest archive (fast, because report is usually early in tar)
            arch = app.find_latest_archive()
            if not arch:
                return self._json({"ok": True, "text": ""}, HTTPStatus.OK)
            member = "./analysis/REPORT_EN.md" if lang == "en" else "./analysis/REPORT_RU.md"
            txt = app.extract_member_text(arch, member, max_bytes=512_000)
            return self._json({"ok": True, "text": txt, "note": "from_archive"}, HTTPStatus.OK)
        if path == "/api/archives":
            return self._json({"ok": True, "archives": app.list_archives()}, HTTPStatus.OK)

        return self._json({"ok": False, "error": "unknown endpoint"}, HTTPStatus.NOT_FOUND)

    def handle_api_post(self, path: str) -> None:
        app: App = self.server.app  # type: ignore[attr-defined]
        body = self._read_json()

        if path == "/api/run":
            if not isinstance(body, dict):
                return self._json({"ok": False, "error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            res = app.start_run(body)
            return self._json(res, HTTPStatus.OK if res.get("ok") else HTTPStatus.CONFLICT)

        if path == "/api/stop":
            res = app.stop_run()
            return self._json(res, HTTPStatus.OK)

        if path == "/api/config":
            if not isinstance(body, dict):
                return self._json({"ok": False, "error": "invalid json"}, HTTPStatus.BAD_REQUEST)

            updates: Dict[str, str] = {}
            # allow only known keys
            for k in DEFAULTS.keys():
                if k in body:
                    updates[k] = str(body[k])

            # Validate some
            if "WEB_BIND" in updates and updates["WEB_BIND"] not in {"127.0.0.1", "0.0.0.0"}:
                updates["WEB_BIND"] = DEFAULTS["WEB_BIND"]
            if "WEB_PORT" in updates:
                try:
                    p = int(updates["WEB_PORT"])
                    # 0 means: auto-select a free port
                    if not (0 <= p <= 65535):
                        raise ValueError()
                except Exception:
                    updates["WEB_PORT"] = DEFAULTS["WEB_PORT"]

            save_shell_config(app.config, updates)
            return self._json({"ok": True, "saved": True}, HTTPStatus.OK)

        return self._json({"ok": False, "error": "unknown endpoint"}, HTTPStatus.NOT_FOUND)

    # ---------- static ----------
    def serve_static(self, rel: str) -> None:
        app: App = self.server.app  # type: ignore[attr-defined]
        rel = rel.lstrip("/")
        # prevent traversal
        if ".." in rel or rel.startswith(".") or rel.startswith("~") or "\\" in rel:
            return self._text("Bad path", HTTPStatus.BAD_REQUEST)

        p = app.static_root / rel
        if not p.exists() or not p.is_file():
            return self._text("Not found", HTTPStatus.NOT_FOUND)

        ctype = "application/octet-stream"
        if rel.endswith(".html"):
            ctype = "text/html; charset=utf-8"
        elif rel.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif rel.endswith(".js"):
            ctype = "application/javascript; charset=utf-8"
        elif rel.endswith(".svg"):
            ctype = "image/svg+xml"
        elif rel.endswith(".ico"):
            ctype = "image/x-icon"

        data = p.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_download(self, name: str) -> None:
        app: App = self.server.app  # type: ignore[attr-defined]
        # only allow expected filenames
        if not (fnmatch.fnmatch(name, "keenetic-maxprobe-*.tar.gz") or fnmatch.fnmatch(name, "keenetic-maxprobe-*.tar.gz.sha256")):
            return self._text("Forbidden", HTTPStatus.FORBIDDEN)

        # locate the file in candidate outbases
        target: Optional[Path] = None
        for base in app.candidate_outbases():
            p = base / name
            if p.exists() and p.is_file():
                target = p
                break
        if not target:
            return self._text("Not found", HTTPStatus.NOT_FOUND)

        data = target.read_bytes()
        ctype = "application/gzip" if name.endswith(".tar.gz") else "text/plain; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------- helpers ----------
    def _read_json(self) -> Any:
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except Exception:
            n = 0
        if n <= 0:
            return None
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            return None

    def _json(self, obj: Any, status: HTTPStatus) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _text(self, text: str, status: HTTPStatus) -> None:
        data = (text + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        # quieter, but still useful
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))


def _guess_lan_ip(bind: str) -> str:
    """Best-effort LAN IP detection for printing a usable URL.

    Note: on routers with multiple interfaces this may pick a non-LAN address.
    We try br0 first via `ip`, then fall back to a UDP socket trick.
    """
    if bind == "127.0.0.1":
        return "127.0.0.1"

    # Try `ip` for br0 (Keenetic LAN bridge)
    try:
        import subprocess

        out = subprocess.check_output(["ip", "-4", "addr", "show", "br0"], stderr=subprocess.DEVNULL).decode("utf-8", "replace")
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                ip = line.split()[1].split("/")[0]
                if ip and not ip.startswith("127."):
                    return ip
    except Exception:
        pass

    # Fallback: UDP connect trick (doesn't require real connectivity)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    return "<router-ip>"


def _pick_state_dir(cli_value: str) -> Path:
    cand: List[Path] = []
    if cli_value:
        cand.append(Path(cli_value))
    cand += [Path("/opt/var/run"), Path("/var/run"), Path("/tmp")]

    for p in cand:
        try:
            p.mkdir(parents=True, exist_ok=True)
            if p.is_dir():
                return p
        except Exception:
            continue
    return Path(".")


def _write_text_atomic(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        # best-effort only
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0", help="Bind address (default: 0.0.0.0 for LAN access)")
    ap.add_argument("--port", type=int, default=0, help="Port (0 = auto-select free port)")
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--probe-bin", required=True)
    ap.add_argument("--outbase", default="")
    ap.add_argument("--config", default="/opt/etc/keenetic-maxprobe.conf")
    ap.add_argument("--token", default="", help="Optional API token; if empty, API is open")
    ap.add_argument("--state-dir", default="", help="Where to write .port/.url state files (default: /opt/var/run)")
    args = ap.parse_args()

    static_root = Path(__file__).resolve().parent / "static"
    probe_bin = Path(args.probe_bin)

    app = App(
        bind=args.bind,
        port=args.port,
        lang=args.lang,
        probe_bin=probe_bin,
        outbase=args.outbase,
        config=Path(args.config),
        token=args.token,
        static_root=static_root,
    )

    try:
        httpd = ThreadingHTTPServer((args.bind, args.port), Handler)
    except OSError as e:
        # If a fixed port is busy, fall back to auto port selection
        if args.port != 0 and getattr(e, "errno", None) in {98, 48}:  # EADDRINUSE (linux/mac)
            httpd = ThreadingHTTPServer((args.bind, 0), Handler)
        else:
            raise
    httpd.app = app  # type: ignore[attr-defined]

    # If port=0 we get the actual chosen port after bind
    actual_port = int(httpd.server_address[1])
    app.port = actual_port

    state_dir = _pick_state_dir(args.state_dir)
    port_file = state_dir / "keenetic-maxprobe-webui.port"
    url_file = state_dir / "keenetic-maxprobe-webui.url"
    bind_file = state_dir / "keenetic-maxprobe-webui.bind"

    lan_ip = _guess_lan_ip(args.bind)
    url = f"http://{lan_ip}:{actual_port}/" + (f"?token={args.token}" if args.token else "")

    _write_text_atomic(port_file, str(actual_port) + "\n")
    _write_text_atomic(url_file, url + "\n")
    _write_text_atomic(bind_file, args.bind + "\n")

    # Print human-friendly URL
    if args.bind == "0.0.0.0":
        print(f"[+] keenetic-maxprobe Web UI listening on http://0.0.0.0:{actual_port}/ (LAN)", file=sys.stderr)
    else:
        print(f"[+] keenetic-maxprobe Web UI listening on http://{args.bind}:{actual_port}/", file=sys.stderr)
    print(f"[+] Suggested URL: {url}", file=sys.stderr)
    print(f"[i] State files: {port_file} , {url_file}", file=sys.stderr)
    print("[i] API token: enabled" if args.token else "[i] API token: disabled", file=sys.stderr)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
