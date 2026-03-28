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
    from proc_map_designer.app import run_app

    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
