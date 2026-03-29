from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.models import CollectionNode
from proc_map_designer.domain.project_state import LayerState, MapSettings, ProjectState


class ProjectStateTests(unittest.TestCase):
    def test_project_round_trip_serialization(self) -> None:
        state = ProjectState.create_new(
            project_name="MapaTest",
            source_blend="/tmp/example.blend",
            blender_executable="/usr/bin/blender",
        )
        state.collection_tree = [
            CollectionNode(name="vegetation", object_count=0, children=[CollectionNode(name="pino", object_count=3)])
        ]
        state.map_settings = MapSettings(
            logical_width=350.0,
            logical_height=150.0,
            logical_unit="m",
            mask_width=2048,
            mask_height=1024,
        )

        payload = state.to_dict()
        loaded = ProjectState.from_dict(payload)

        self.assertEqual(loaded.schema_version, 1)
        self.assertEqual(loaded.project_name, "MapaTest")
        self.assertEqual(loaded.source_blend, "/tmp/example.blend")
        self.assertEqual(loaded.collection_tree[0].name, "vegetation")
        self.assertEqual(loaded.collection_tree[0].children[0].object_count, 3)
        self.assertEqual(loaded.map_settings.mask_width, 2048)

    def test_invalid_schema_version_fails(self) -> None:
        payload = ProjectState.create_new().to_dict()
        payload["schema_version"] = 999
        with self.assertRaises(ValueError):
            ProjectState.from_dict(payload)

    def test_invalid_map_settings_fails(self) -> None:
        payload = ProjectState.create_new().to_dict()
        payload["map_settings"]["logical_width"] = -1
        with self.assertRaises(ValueError):
            ProjectState.from_dict(payload)

    def test_legacy_layer_without_color_hex_is_supported(self) -> None:
        state = ProjectState.create_new(project_name="Legacy")
        state.layers = [
            LayerState(
                layer_id="vegetation/tree",
                name="vegetation/tree",
                visible=True,
                opacity=0.8,
                mask_data_path=None,
                color_hex="#22aa88",
            )
        ]
        payload = state.to_dict()
        payload["layers"][0].pop("color_hex", None)

        loaded = ProjectState.from_dict(payload)
        self.assertEqual(len(loaded.layers), 1)
        self.assertEqual(loaded.layers[0].layer_id, "vegetation/tree")
        self.assertEqual(loaded.layers[0].color_hex, "")


if __name__ == "__main__":
    unittest.main()
