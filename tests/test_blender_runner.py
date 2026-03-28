from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.infrastructure.blender_runner import BlenderExecutionError, BlenderRunner


class BlenderRunnerParsingTests(unittest.TestCase):
    def test_extract_payload_from_stdout_ok(self) -> None:
        payload = {"total_collections": 2, "roots": [], "warnings": [], "blend_file": "/tmp/a.blend"}
        output = (
            "Blender startup lines\n"
            f"{BlenderRunner.JSON_START}\n"
            f"{json.dumps(payload)}\n"
            f"{BlenderRunner.JSON_END}\n"
        )
        parsed = BlenderRunner.extract_payload_from_stdout(output)
        self.assertEqual(parsed, payload)

    def test_extract_payload_without_markers_fails(self) -> None:
        with self.assertRaises(BlenderExecutionError):
            BlenderRunner.extract_payload_from_stdout("{}")


if __name__ == "__main__":
    unittest.main()

