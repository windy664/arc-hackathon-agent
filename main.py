#!/usr/bin/env python3
"""ARC-Bench agent entrypoint.

Usage (as invoked by the platform):
    python3 main.py /path/to/requirements --output-dir /path/to/output [--type web]

Everything lives in the `compiler/` package; this file only wires argv to the
pipeline so the platform contract (root entrypoint named main.py) is satisfied.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from compiler.pipeline import run


def parse_args(argv: list[str]) -> tuple[Path, Path]:
    if not argv:
        raise SystemExit("Usage: main.py <requirements_source> --output-dir <dir>")
    source = Path(argv[0])
    out = Path(os.environ.get("ARCBENCH_OUTPUT_DIR") or "/workspace/template")
    for i, arg in enumerate(argv):
        if arg == "--output-dir" and i + 1 < len(argv):
            out = Path(argv[i + 1])
    return source, out


def main() -> int:
    source, out = parse_args(sys.argv[1:])
    try:
        run(source, out)
        return 0
    except Exception as exc:  # keep exit code 0 unless fatal per platform contract
        print(f"[fatal] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
