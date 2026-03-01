#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional python collector for keenetic-maxprobe.

This is NOT required for the core tool, but can enrich analysis data.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


def read_text(p: Path, max_bytes: int = 1_000_000) -> str:
    try:
        b = p.read_bytes()
        if len(b) > max_bytes:
            b = b[:max_bytes]
        return b.decode("utf-8", errors="replace")
    except Exception:
        return ""


def parse_metrics(p: Path) -> Dict[str, Any]:
    txt = read_text(p, max_bytes=2_000_000)
    cpu: List[float] = []
    mem: List[float] = []
    load: List[float] = []
    for line in txt.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        try:
            cpu.append(float(parts[1]))
            mem.append(float(parts[2]))
            load.append(float(parts[3]))
        except Exception:
            continue
    def summary(x: List[float]) -> Dict[str, Any]:
        if not x:
            return {"count": 0}
        x_sorted = sorted(x)
        return {
            "count": len(x_sorted),
            "min": x_sorted[0],
            "max": x_sorted[-1],
            "p50": x_sorted[len(x_sorted)//2],
            "p95": x_sorted[int(len(x_sorted)*0.95)-1] if len(x_sorted) >= 20 else x_sorted[-1],
        }
    return {"cpu": summary(cpu), "mem": summary(mem), "load": summary(load)}


def dmesg_signals(p: Path) -> Dict[str, Any]:
    txt = read_text(p, max_bytes=1_000_000)
    err = 0
    warn = 0
    for line in txt.splitlines():
        l = line.lower()
        if "error" in l or "fail" in l or "oom" in l:
            err += 1
        if "warn" in l:
            warn += 1
    return {"error_like_lines": err, "warn_like_lines": warn}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    args = ap.parse_args()

    w = Path(args.workdir)
    analysis = w / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)

    out: Dict[str, Any] = {"collector": "probe.py"}

    out["metrics_summary"] = parse_metrics(w / "meta" / "metrics.tsv")
    out["dmesg_signals"] = dmesg_signals(w / "sys" / "dmesg.txt")

    (analysis / "python_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
