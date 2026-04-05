#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_path() -> None:
    project_root = Path(__file__).resolve().parent
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def main() -> int:
    _bootstrap_path()

    try:
        from proc_map_designer.app import run_app
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print(
                "Missing dependency: PySide6\n"
                "Install project dependencies in the Python environment that runs ./main.py:\n"
                "  python -m pip install -r requirements.txt\n"
                "Or activate the project virtualenv first, then run ./main.py.",
                file=sys.stderr,
            )
            return 1
        raise

    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
