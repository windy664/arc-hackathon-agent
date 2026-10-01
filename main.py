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
    """Accept the platform invocation, bare flags like --type web, or no args at all.

    Fallbacks: ARCBENCH_TASK_DIR (default ./requirements) for the source, and
    ARCBENCH_OUTPUT_DIR / ARCBENCH_TEMPLATE_DIR (default /workspace/template)
    for the output directory.
    """
    source: Path | None = None
    out = Path(
        os.environ.get("ARCBENCH_OUTPUT_DIR")
        or os.environ.get("ARCBENCH_TEMPLATE_DIR")
        or "/workspace/template"
    )
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--output-dir" and i + 1 < len(argv):
            out = Path(argv[i + 1])
            i += 2
        elif arg == "--type" and i + 1 < len(argv):
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            source = Path(arg)
            i += 1
    if source is None:
        source = Path(os.environ.get("ARCBENCH_TASK_DIR") or "requirements")
    return source, out


def main() -> int:
    source, out = parse_args(sys.argv[1:])
    if not source.exists():
        raise SystemExit(
            f"requirements source not found: {source} "
            "(pass it as the first argument or set ARCBENCH_TASK_DIR)"
        )
    try:
        run(source, out)
        return 0
    except Exception as exc:  # keep exit code 0 unless fatal per platform contract
        print(f"[fatal] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
