#!/usr/bin/env python3
"""
keenetic-maxprobe Web UI (no external deps)

- Start probe runs: profile/mode/collectors (+ deps_level for extream)
- Live status: phase/progress + CPU/RAM/Load1 from metrics_current.tsv
- Live log tail (meta/run.log)
- List & download archives from /var/tmp
- Port fallback: if requested port is busy, tries next ports.

Requires: python3 (Entware)
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

OUTBASE = Path("/var/tmp")
WORK_GLOB = "keenetic-maxprobe-*.work"
ARCH_GLOB = "keenetic-maxprobe-*.tar.gz"

def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)

def latest_workdir() -> Path | None:
    ws = sorted(OUTBASE.glob(WORK_GLOB), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    return ws[-1] if ws else None

def list_archives(limit: int | None = None):
    items = []
    for p in sorted(OUTBASE.glob(ARCH_GLOB), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
        items.append({
            "name": p.name,
            "size": p.stat().st_size,
            "mtime": int(p.stat().st_mtime),
            "sha256": (p.with_suffix(p.suffix + ".sha256").name if p.with_suffix(p.suffix + ".sha256").exists() else None),
        })
        if limit and len(items) >= limit:
            break
    return items

def read_text(path: Path, max_bytes: int = 200_000) -> str:
    try:
        b = path.read_bytes()
        if len(b) > max_bytes:
            b = b[-max_bytes:]
        return b.decode("utf-8", errors="replace")
    except Exception:
        return ""

def parse_metrics(line: str):
    parts = line.strip().split("\t")
    if len(parts) >= 4:
        return {"ts": parts[0], "cpu": parts[1], "mem": parts[2], "load1": parts[3]}
    return None

class State:
    lock = threading.Lock()
    running: bool = False
    pid: int | None = None
    started: float | None = None
    last_cmd: list[str] | None = None

STATE = State()

def start_probe(probe_bin: str, profile: str, mode: str, collectors: str, deps_level: str):
    with STATE.lock:
        if STATE.running and STATE.pid:
            try:
                os.kill(STATE.pid, 0)
                return {"ok": False, "error": "already_running", "pid": STATE.pid}
            except OSError:
                STATE.running = False
                STATE.pid = None

        cmd = [probe_bin, "--profile", profile, "--mode", mode, "--collectors", collectors, "--yes", "--no-spinner"]
        if mode == "extream":
            cmd += ["--deps-level", deps_level]
        env = os.environ.copy()
        env["LANG_UI"] = env.get("LANG_UI", "ru")

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        STATE.running = True
        STATE.pid = p.pid
        STATE.started = time.time()
        STATE.last_cmd = cmd

    def drain():
        try:
            if p.stdout:
                for _ in p.stdout:
                    pass
        finally:
            with STATE.lock:
                STATE.running = False
                STATE.pid = None

    threading.Thread(target=drain, daemon=True).start()
    return {"ok": True, "pid": p.pid, "cmd": cmd}

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        root = Path(__file__).parent / "static"
        up = urlparse(path).path
        if up in ("/", ""):
            return str(root / "index.html")
        if up.startswith("/static/"):
            up = up[len("/static/"):]
        return str(root / up.lstrip("/"))

    def log_message(self, fmt, *args):
        return

    def _json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        up = urlparse(self.path)
        if up.path == "/api/status":
            w = latest_workdir()
            with STATE.lock:
                st = {
                    "running": STATE.running,
                    "pid": STATE.pid,
                    "cmd": STATE.last_cmd,
                    "started": STATE.started,
                    "workdir": str(w) if w else None,
                }
            if w and w.exists():
                st["phase"] = read_text(w / "meta" / "phase.txt", 512).strip()
                st["progress"] = read_text(w / "meta" / "progress.txt", 64).strip()
                cur = read_text(w / "meta" / "metrics_current.tsv", 512).strip().splitlines()
                st["metrics"] = parse_metrics(cur[-1]) if cur else None
            st["archives"] = list_archives(limit=10)
            return self._json(st)

        if up.path == "/api/log":
            w = latest_workdir()
            if not w:
                return self._json({"ok": True, "log": ""})
            return self._json({"ok": True, "log": read_text(w / "meta" / "run.log")})

        if up.path == "/api/archives":
            return self._json({"ok": True, "archives": list_archives()})

        if up.path.startswith("/download/"):
            name = safe_name(up.path.split("/download/", 1)[1])
            f = OUTBASE / name
            if not f.exists() or not f.is_file():
                return self._json({"ok": False, "error": "not_found"}, status=404)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(f.stat().st_size))
            self.send_header("Content-Disposition", f'attachment; filename="{f.name}"')
            self.end_headers()
            with f.open("rb") as rf:
                while True:
                    chunk = rf.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return

        return super().do_GET()

    def do_POST(self):
        up = urlparse(self.path)
        if up.path == "/api/start":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {}
            profile = payload.get("profile", "forensic")
            mode = payload.get("mode", "full")
            collectors = payload.get("collectors", "all")
            deps_level = payload.get("deps_level", "core")
            return self._json(start_probe(self.server.probe_bin, profile, mode, collectors, deps_level))
        return self._json({"ok": False, "error": "bad_endpoint"}, status=404)

class WebServer(ThreadingHTTPServer):
    def __init__(self, addr, handler, probe_bin: str):
        super().__init__(addr, handler)
        self.probe_bin = probe_bin

def bind_with_fallback(bind: str, port: int, probe_bin: str):
    for i in range(20):
        try:
            srv = WebServer((bind, port + i), Handler, probe_bin=probe_bin)
            return srv, port + i
        except OSError as e:
            if getattr(e, "errno", None) == 98:  # EADDRINUSE
                continue
            raise
    raise OSError(98, "No free port in range")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--probe-bin", default="/opt/bin/keenetic-maxprobe")
    args = ap.parse_args()

    srv, actual = bind_with_fallback(args.bind, args.port, args.probe_bin)
    print(f"[+] Web UI: http://{args.bind}:{actual}/", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        srv.server_close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
