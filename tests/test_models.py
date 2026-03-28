from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.models import BlendInspectionResult, CollectionNode


class ModelsTestCase(unittest.TestCase):
    def test_collection_node_from_dict_builds_children(self) -> None:
        node = CollectionNode.from_dict(
            {
                "name": "vegetation",
                "children": [
                    {"name": "pino", "children": [], "object_count": 3},
                    {"name": "arbusto", "children": [], "object_count": 2},
                ],
                "object_count": 10,
            }
        )
        self.assertEqual(node.name, "vegetation")
        self.assertEqual(node.object_count, 10)
        self.assertEqual([child.name for child in node.children], ["pino", "arbusto"])
        self.assertEqual([child.object_count for child in node.children], [3, 2])

    def test_result_parsing_and_missing_expected(self) -> None:
        result = BlendInspectionResult.from_dict(
            {
                "blend_file": "/tmp/sample.blend",
                "roots": [{"name": "building", "children": []}],
                "total_collections": 3,
                "warnings": [],
            }
        )
        missing = result.missing_expected_roots({"vegetation", "building"})
        self.assertEqual(missing, {"vegetation"})


if __name__ == "__main__":
    unittest.main()
