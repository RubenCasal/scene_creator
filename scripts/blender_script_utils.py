from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

JSON_START = "__BLEND_JSON_START__"
JSON_END = "__BLEND_JSON_END__"


def emit_json(payload: dict[str, Any]) -> None:
    print(JSON_START)
    print(json.dumps(payload, ensure_ascii=False))
    print(JSON_END)


def bootstrap_src_path() -> Path:
    script_dir = Path(__file__).resolve().parent
    src_path = script_dir.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    return src_path
