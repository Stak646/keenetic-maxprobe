#!/usr/bin/env python3
# keenetic-maxprobe Web UI server
# - Starts probe runs
# - Streams status/phase/progress/metrics
# - Lists & serves archives from /var/tmp

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"

DEFAULT_OUTBASES = ["/var/tmp", "/tmp"]
STATE_DIR = Path("/var/tmp/keenetic-maxprobe-webui")
STATE_FILE = STATE_DIR / "state.json"
LOCK_FILE = STATE_DIR / "run.lock"

RUN_PAT = re.compile(r"^keenetic-maxprobe-[A-Za-z0-9._-]+-\d+-\d{8}T\d{6}Z$")


def _read_text(p: Path, max_bytes: int = 256 * 1024) -> str:
    try:
        with p.open("rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except Exception as e:
        return f"[error reading {p}: {e}]"


def _tail_lines(p: Path, n: int = 200) -> str:
    # Simple tail implementation without external deps
    try:
        data = _read_text(p, max_bytes=1024 * 1024)
        lines = data.splitlines()
        return "\n".join(lines[-n:])
    except Exception as e:
        return f"[error tailing {p}: {e}]"


def _parse_metrics_cur(p: Path) -> Dict[str, Any]:
    # Format: ts_utc\tcpu_pct\tmem_used_pct\tmem_avail_kb\tload1
    s = _read_text(p, max_bytes=4096).strip().splitlines()[-1:]  # last line
    if not s:
        return {"cpu_pct": 0, "mem_used_pct": 0, "mem_avail_kb": 0, "load1": 0, "ts_utc": ""}
    parts = s[0].split("\t")
    try:
        return {
            "ts_utc": parts[0] if len(parts) > 0 else "",
            "cpu_pct": int(float(parts[1])) if len(parts) > 1 and parts[1] else 0,
            "mem_used_pct": int(float(parts[2])) if len(parts) > 2 and parts[2] else 0,
            "mem_avail_kb": int(float(parts[3])) if len(parts) > 3 and parts[3] else 0,
            "load1": float(parts[4]) if len(parts) > 4 and parts[4] else 0,
        }
    except Exception:
        return {"cpu_pct": 0, "mem_used_pct": 0, "mem_avail_kb": 0, "load1": 0, "ts_utc": ""}


def _scan_runs(outbases: list[str]) -> Dict[str, Any]:
    workdirs: list[Dict[str, Any]] = []
    archives: list[Dict[str, Any]] = []

    for base in outbases:
        b = Path(base)
        if not b.exists():
            continue

        for wd in sorted(b.glob("keenetic-maxprobe-*.work"), key=lambda p: p.stat().st_mtime, reverse=True):
            run_id = wd.name[:-5]  # strip .work
            if not RUN_PAT.match(run_id):
                continue
            workdirs.append({
                "id": run_id,
                "workdir": str(wd),
                "mtime": int(wd.stat().st_mtime),
            })

        for ar in sorted(b.glob("keenetic-maxprobe-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True):
            run_id = ar.name[:-7]  # strip .tar.gz
            if not RUN_PAT.match(run_id):
                continue
            archives.append({
                "id": run_id,
                "archive": str(ar),
                "sha256": str(ar) + ".sha256",
                "size": int(ar.stat().st_size),
                "mtime": int(ar.stat().st_mtime),
            })

    return {"workdirs": workdirs, "archives": archives}


def _status_for_workdir(workdir: Path) -> Dict[str, Any]:
    meta = workdir / "meta"
    phase = _read_text(meta / "phase.txt", max_bytes=4096).strip() or "..."
    progress = _read_text(meta / "progress.txt", max_bytes=128).strip() or "0/0"
    metrics = _parse_metrics_cur(meta / "metrics_current.tsv")

    errors_log = meta / "errors.log"
    errors_tail = _tail_lines(errors_log, n=50) if errors_log.exists() else ""

    return {
        "workdir": str(workdir),
        "phase": phase,
        "progress": progress,
        "metrics": metrics,
        "errors_tail": errors_tail,
    }


def _load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(_read_text(STATE_FILE))
    except Exception:
        return {}


def _save_state(st: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE_FILE)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_lock(pid: int) -> bool:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        # stale lock?
        try:
            old = int(_read_text(LOCK_FILE).strip() or "0")
        except Exception:
            old = 0
        if old and _pid_alive(old):
            return False
        try:
            LOCK_FILE.unlink()
        except Exception:
            return False
    try:
        LOCK_FILE.write_text(str(pid), encoding="utf-8")
        return True
    except Exception:
        return False


def _release_lock() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


def _start_probe(probe_bin: str, preset: str, lang: str, extra: list[str]) -> Tuple[bool, str, Dict[str, Any]]:
    # Map presets to args
    preset = (preset or "forensic").lower()
    if preset not in {"lite", "diagnostic", "forensic", "extream"}:
        preset = "forensic"

    args = [probe_bin, "--no-spinner"]

    if lang:
        args += ["--lang", lang]

    if preset == "lite":
        args += ["--profile", "lite", "--mode", "safe", "--collectors", "shonly"]
    elif preset == "diagnostic":
        args += ["--profile", "diagnostic", "--mode", "safe", "--collectors", "all"]
    elif preset == "forensic":
        args += ["--profile", "forensic", "--mode", "full", "--collectors", "all"]
    elif preset == "extream":
        args += ["--profile", "forensic", "--mode", "extream", "--collectors", "all", "--deps-level", "collectors"]

    args += extra

    # output dir is fixed by probe itself (/var/tmp)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    launcher_log = STATE_DIR / "launcher.log"

    # Start process
    try:
        with launcher_log.open("ab") as lf:
            p = subprocess.Popen(args, stdout=lf, stderr=lf, close_fds=True)
    except FileNotFoundError:
        return False, f"probe binary not found: {probe_bin}", {}
    except Exception as e:
        return False, f"failed to start probe: {e}", {}

    if not _acquire_lock(p.pid):
        try:
            p.terminate()
        except Exception:
            pass
        return False, "another run is already active", {}

    st = {
        "pid": p.pid,
        "started": int(time.time()),
        "preset": preset,
        "probe_bin": probe_bin,
        "lang": lang,
        "args": args,
    }
    _save_state(st)
    return True, "started", st


class Handler(BaseHTTPRequestHandler):
    server_version = "keenetic-maxprobe-webui/0.1"

    def _send_json(self, obj: Any, code: int = 200) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, s: str, code: int = 200, ctype: str = "text/plain; charset=utf-8") -> None:
        data = s.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/runs":
            outbases = DEFAULT_OUTBASES
            self._send_json(_scan_runs(outbases))
            return

        if path == "/api/status":
            outbases = DEFAULT_OUTBASES
            runs = _scan_runs(outbases)
            st = _load_state()
            pid = int(st.get("pid", 0) or 0)
            alive = _pid_alive(pid)

            # choose the newest workdir if any
            workdir_status: Optional[Dict[str, Any]] = None
            if runs["workdirs"]:
                wd = Path(runs["workdirs"][0]["workdir"])
                workdir_status = _status_for_workdir(wd)

            # newest archive id
            latest_archive = runs["archives"][0] if runs["archives"] else None

            self._send_json({
                "state": st,
                "alive": alive,
                "work": workdir_status,
                "latest_archive": latest_archive,
                "server_time": int(time.time()),
            })
            return

        if path == "/api/log":
            # tail run.log if workdir exists
            outbases = DEFAULT_OUTBASES
            runs = _scan_runs(outbases)
            n = int((qs.get("n") or ["200"])[0])
            if runs["workdirs"]:
                wd = Path(runs["workdirs"][0]["workdir"])
                logp = wd / "meta" / "run.log"
                self._send_text(_tail_lines(logp, n=n))
            else:
                # fallback to launcher log
                self._send_text(_tail_lines(STATE_DIR / "launcher.log", n=n))
            return

        if path == "/api/start":
            preset = (qs.get("preset") or ["forensic"])[0]
            lang = (qs.get("lang") or [""])[0]
            ok, msg, st = _start_probe(self.server.probe_bin, preset=preset, lang=lang, extra=[])
            self._send_json({"ok": ok, "msg": msg, "state": st}, code=200 if ok else 409)
            return

        if path == "/api/stop":
            st = _load_state()
            pid = int(st.get("pid", 0) or 0)
            if pid and _pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.2)
                except Exception as e:
                    self._send_json({"ok": False, "msg": str(e)}, code=500)
                    return
            _release_lock()
            self._send_json({"ok": True, "msg": "stopped"})
            return

        if path.startswith("/download/"):
            # Serve only keenetic-maxprobe archives from /var/tmp
            fn = path[len("/download/") :]
            fn = fn.replace("..", "")
            if not (fn.endswith(".tar.gz") or fn.endswith(".tar.gz.sha256")):
                self._send_text("bad filename", code=400)
                return
            p = Path("/var/tmp") / fn
            if not p.exists():
                self._send_text("not found", code=404)
                return
            # Stream file
            try:
                self.send_response(200)
                ctype = "application/gzip" if fn.endswith(".tar.gz") else "text/plain; charset=utf-8"
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(p.stat().st_size))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with p.open("rb") as f:
                    while True:
                        chunk = f.read(1024 * 128)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except Exception as e:
                try:
                    self._send_text(f"error: {e}", code=500)
                except Exception:
                    pass
            return

        # Static
        if path == "/":
            path = "/index.html"
        sp = (STATIC_DIR / path.lstrip("/")).resolve()
        if not str(sp).startswith(str(STATIC_DIR.resolve())):
            self._send_text("not found", code=404)
            return
        if not sp.exists() or not sp.is_file():
            self._send_text("not found", code=404)
            return

        ctype = "text/html; charset=utf-8"
        if sp.name.endswith(".js"):
            ctype = "application/javascript; charset=utf-8"
        elif sp.name.endswith(".css"):
            ctype = "text/css; charset=utf-8"

        self._send_text(_read_text(sp, max_bytes=2 * 1024 * 1024), ctype=ctype)

    def log_message(self, fmt: str, *args: Any) -> None:
        # Quiet default logging (keep router load low)
        return


class WebUIServer(ThreadingHTTPServer):
    def __init__(self, server_address: Tuple[str, int], RequestHandlerClass: Any, probe_bin: str):
        super().__init__(server_address, RequestHandlerClass)
        self.probe_bin = probe_bin


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", default=8088, type=int)
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--probe-bin", default="/opt/bin/keenetic-maxprobe")
    args = ap.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    srv = WebUIServer((args.bind, args.port), Handler, probe_bin=args.probe_bin)
    print(f"[+] keenetic-maxprobe Web UI listening on http://{args.bind}:{args.port}/", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
