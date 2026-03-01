#!/usr/bin/env python3
"""
keenetic-maxprobe Web UI server

Goals:
- Start/stop a probe run from browser
- Show live status (phase/progress/metrics)
- Tail logs
- List and download archives from /var/tmp (and /tmp as fallback)

This server is intentionally self-contained and dependency-free.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_OUTDIRS = [Path("/var/tmp"), Path("/tmp")]
STATE_DIR = Path("/var/tmp/keenetic-maxprobe-webui")
STATE_FILE = STATE_DIR / "state.json"
LOCK_FILE = STATE_DIR / "run.lock"

STATIC_DIR = Path(__file__).resolve().parent / "static"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_text(path: Path, limit: int = 2_000_000) -> str:
    try:
        data = path.read_bytes()
        if len(data) > limit:
            data = data[:limit] + b"\n...<truncated>...\n"
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def safe_int(x: str, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return default


def list_ipv4_addrs() -> List[str]:
    # Best-effort: prefer `ip -4 -o addr show`
    addrs: List[str] = []
    try:
        out = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for line in out.splitlines():
            # "... inet 192.168.1.1/24 ..."
            m = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/", line)
            if m:
                ip = m.group(1)
                if ip != "127.0.0.1":
                    addrs.append(ip)
    except Exception:
        pass

    # Fallback: try hostname resolution (may return 127.0.0.1 only)
    if not addrs:
        try:
            host = socket.gethostname()
            ip = socket.gethostbyname(host)
            if ip and ip != "127.0.0.1":
                addrs.append(ip)
        except Exception:
            pass

    # Unique preserve order
    seen = set()
    out2: List[str] = []
    for a in addrs:
        if a not in seen:
            out2.append(a)
            seen.add(a)
    return out2


def find_archives(outdirs: List[Path]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for d in outdirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("keenetic-maxprobe-*.tar.gz"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                st = p.stat()
                items.append(
                    {
                        "path": str(p),
                        "name": p.name,
                        "size": st.st_size,
                        "mtime": int(st.st_mtime),
                        "sha256_path": str(p) + ".sha256" if (p.with_suffix(p.suffix + ".sha256")).exists() else "",
                    }
                )
            except Exception:
                continue
    return items


def find_workdirs(outdirs: List[Path]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for d in outdirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("keenetic-maxprobe-*.work"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                st = p.stat()
                items.append(
                    {
                        "path": str(p),
                        "name": p.name,
                        "mtime": int(st.st_mtime),
                    }
                )
            except Exception:
                continue
    return items


def read_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_state(st: Dict[str, Any]) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(st, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def acquire_lock() -> bool:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        # O_EXCL ensures we do not overwrite if exists
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(utc_now())
        return True
    except FileExistsError:
        return False
    except Exception:
        return False


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
        except Exception:
            pass


class WebUIServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: Tuple[str, int], handler_cls, probe_bin: str, lang: str, outdirs: List[Path]):
        super().__init__(server_address, handler_cls)
        self.probe_bin = probe_bin
        self.lang = lang
        self.outdirs = outdirs
        self._run_proc: Optional[subprocess.Popen] = None
        self._run_thread: Optional[threading.Thread] = None


class Handler(SimpleHTTPRequestHandler):
    server: WebUIServer  # type: ignore[assignment]

    def log_message(self, fmt: str, *args) -> None:
        # Keep stdout clean; state is in run.log
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], utc_now(), fmt % args))

    def _send_json(self, obj: Any, status: int = 200) -> None:
        data = json.dumps(obj, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text: str, status: int = 200, ctype: str = "text/plain; charset=utf-8") -> None:
        data = text.encode("utf-8", errors="replace")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, rel: str) -> None:
        path = (STATIC_DIR / rel).resolve()
        if not str(path).startswith(str(STATIC_DIR.resolve())):
            self._send_text("forbidden", status=403)
            return
        if not path.exists():
            self._send_text("not found", status=404)
            return
        ctype = "text/plain; charset=utf-8"
        if path.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        elif path.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        self._send_text(read_text(path), status=200, ctype=ctype)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._serve_static("index.html")
            return
        if self.path == "/app.js":
            self._serve_static("app.js")
            return
        if self.path == "/style.css":
            self._serve_static("style.css")
            return

        if self.path.startswith("/api/status"):
            self._handle_status()
            return
        if self.path.startswith("/api/runs"):
            self._handle_runs()
            return
        if self.path.startswith("/api/log"):
            self._handle_log()
            return
        if self.path.startswith("/api/start"):
            self._handle_start()
            return
        if self.path.startswith("/api/stop"):
            self._handle_stop()
            return
        if self.path.startswith("/download?path="):
            self._handle_download()
            return

        self._send_text("not found", status=404)

    def _handle_status(self) -> None:
        st = read_state()
        # try to enrich with meta from the most recent workdir
        workdirs = find_workdirs(self.server.outdirs)
        meta: Dict[str, Any] = {}
        if workdirs:
            wd = Path(workdirs[0]["path"])
            phase = read_text(wd / "meta" / "phase.txt", limit=10_000).strip()
            prog = read_text(wd / "meta" / "progress.txt", limit=1000).strip()
            metrics = read_text(wd / "meta" / "metrics_current.tsv", limit=1000).strip()
            meta = {"workdir": str(wd), "phase": phase, "progress": prog, "metrics_current": metrics}

        st_out = {"state": st, "meta": meta, "utc": utc_now()}
        self._send_json(st_out)

    def _handle_runs(self) -> None:
        self._send_json(
            {
                "archives": find_archives(self.server.outdirs),
                "workdirs": find_workdirs(self.server.outdirs),
                "outdirs": [str(d) for d in self.server.outdirs],
                "utc": utc_now(),
            }
        )

    def _handle_log(self) -> None:
        # query string: ?n=200
        n = 200
        try:
            m = re.search(r"[?&]n=(\d+)", self.path)
            if m:
                n = min(5000, max(10, int(m.group(1))))
        except Exception:
            n = 200

        workdirs = find_workdirs(self.server.outdirs)
        if not workdirs:
            self._send_text("no active workdir found", status=200)
            return
        wd = Path(workdirs[0]["path"])
        logp = wd / "meta" / "run.log"
        errp = wd / "meta" / "errors.log"
        log_txt = read_text(logp, limit=500_000)
        err_txt = read_text(errp, limit=200_000)

        # tail last n lines (cheap)
        log_lines = log_txt.splitlines()[-n:]
        err_lines = err_txt.splitlines()[-n:]
        out = []
        if err_lines:
            out.append("=== errors.log (tail) ===")
            out.extend(err_lines)
        if log_lines:
            out.append("\n=== run.log (tail) ===")
            out.extend(log_lines)
        self._send_text("\n".join(out), status=200)

    def _handle_start(self) -> None:
        qs = self.path.split("?", 1)[1] if "?" in self.path else ""
        preset = "forensic"
        lang = self.server.lang
        for part in qs.split("&"):
            if part.startswith("preset="):
                preset = part.split("=", 1)[1] or preset
            if part.startswith("lang="):
                lang = part.split("=", 1)[1] or lang

        preset = preset.strip()
        if preset not in {"lite", "diagnostic", "forensic", "extream", "safe", "full"}:
            preset = "forensic"

        if not acquire_lock():
            self._send_json({"ok": False, "error": "run already active (lock exists)"}, status=409)
            return

        # Build args
        args = [self.server.probe_bin, "--lang", lang]
        if preset in {"lite", "diagnostic", "forensic"}:
            args += ["--profile", preset, "--mode", "full"]
        elif preset == "safe":
            args += ["--mode", "safe"]
        elif preset == "full":
            args += ["--mode", "full"]
        elif preset == "extream":
            args += ["--mode", "extream", "--deps-level", "collectors"]

        st = {"active": True, "started_utc": utc_now(), "preset": preset, "args": args}
        write_state(st)

        def runner() -> None:
            try:
                with subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                ) as proc:
                    self.server._run_proc = proc
                    # Stream to state_dir log as well
                    logp = STATE_DIR / "webui_run_stream.log"
                    with logp.open("a", encoding="utf-8") as f:
                        f.write(f"\n=== start {utc_now()} preset={preset} ===\n")
                        for line in proc.stdout or []:
                            f.write(line)
                    rc = proc.wait()
                    st2 = read_state()
                    st2.update({"active": False, "finished_utc": utc_now(), "returncode": rc})
                    write_state(st2)
            except Exception as e:
                st2 = read_state()
                st2.update({"active": False, "finished_utc": utc_now(), "error": str(e)})
                write_state(st2)
            finally:
                self.server._run_proc = None
                release_lock()

        t = threading.Thread(target=runner, daemon=True)
        self.server._run_thread = t
        t.start()

        self._send_json({"ok": True, "state": st})

    def _handle_stop(self) -> None:
        proc = self.server._run_proc
        if not proc:
            # Still clear lock if stale
            release_lock()
            st = read_state()
            st["active"] = False
            write_state(st)
            self._send_json({"ok": True, "stopped": False, "note": "no running process"})
            return

        try:
            proc.terminate()
            self._send_json({"ok": True, "stopped": True})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _handle_download(self) -> None:
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        m = re.search(r"(?:^|&)path=([^&]+)", q)
        if not m:
            self._send_text("bad request", status=400)
            return
        req = m.group(1)
        # decode minimal percent-encoding for spaces etc.
        try:
            from urllib.parse import unquote

            req = unquote(req)
        except Exception:
            pass

        path = Path(req).resolve()
        # allow only under outdirs
        allowed = any(str(path).startswith(str(d.resolve()) + os.sep) for d in self.server.outdirs)
        if not allowed:
            self._send_text("forbidden", status=403)
            return
        if not path.exists() or not path.is_file():
            self._send_text("not found", status=404)
            return

        # Stream file
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with path.open("rb") as f:
            shutil.copyfileobj(f, self.wfile)


def bind_server(bind: str, port: int, handler_cls, probe_bin: str, lang: str, outdirs: List[Path]) -> Tuple[WebUIServer, int]:
    # If port == 0, bind once and return actual port
    if port == 0:
        srv = WebUIServer((bind, 0), handler_cls, probe_bin=probe_bin, lang=lang, outdirs=outdirs)
        return srv, srv.server_address[1]

    last_exc: Optional[OSError] = None
    for p in range(port, port + 20):
        try:
            srv = WebUIServer((bind, p), handler_cls, probe_bin=probe_bin, lang=lang, outdirs=outdirs)
            return srv, p
        except OSError as e:
            last_exc = e
            if getattr(e, "errno", None) == 98:  # EADDRINUSE
                continue
            raise
    if last_exc:
        raise last_exc
    raise OSError("Failed to bind server")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--probe-bin", default="keenetic-maxprobe")
    args = ap.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Prefer /var/tmp, but if missing, fallback to /tmp
    outdirs = [d for d in DEFAULT_OUTDIRS if d.is_dir()] or DEFAULT_OUTDIRS

    try:
        srv, port = bind_server(args.bind, int(args.port), Handler, probe_bin=args.probe_bin, lang=args.lang, outdirs=outdirs)
    except OSError as e:
        if getattr(e, "errno", None) == 98:
            sys.stderr.write(f"[!] Port is busy: {args.bind}:{args.port}\n")
            sys.stderr.write("    Stop the previous instance or choose another port: --port 8089\n")
            sys.stderr.write("    To find who listens: ss -lntp | grep :8088  (or netstat -lntp)\n")
            return 98
        raise

    base_url = f"http://{args.bind}:{port}/"
    sys.stderr.write(f"[+] Web UI listening on {base_url}\n")

    if args.bind in {"0.0.0.0", "::"}:
        ips = list_ipv4_addrs()
        if ips:
            sys.stderr.write("[+] Open from LAN:\n")
            for ip in ips:
                sys.stderr.write(f"    http://{ip}:{port}/\n")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[+] Stopped.\n")
    finally:
        try:
            srv.server_close()
        except Exception:
            pass
        # do not remove lock automatically (may be used by active run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
