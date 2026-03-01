#!/usr/bin/env python3
# Compatibility wrapper (legacy name): analysis.py
# Calls collectors/py/analyze.py with --workdir.
import sys
from pathlib import Path

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: analysis.py <workdir>", file=sys.stderr)
        return 2
    workdir = sys.argv[1]
    here = Path(__file__).resolve().parent
    analyzer = here / "collectors" / "py" / "analyze.py"
    if analyzer.exists():
        import subprocess
        return subprocess.call([str(analyzer), "--workdir", workdir])
    print("Analyzer not found", file=sys.stderr)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
