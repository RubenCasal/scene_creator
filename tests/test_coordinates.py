from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.coordinates import mask_to_scene, scene_to_mask, viewport_to_scene
from proc_map_designer.domain.project_state import MapSettings


class CoordinateTransformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.map_settings = MapSettings(
            logical_width=200.0,
            logical_height=200.0,
            logical_unit="m",
            mask_width=2048,
            mask_height=2048,
        )

    def test_scene_to_mask_and_back_round_trip(self) -> None:
        mask_x, mask_y = scene_to_mask(10.0, -5.0, self.map_settings)
        scene_x, scene_y = mask_to_scene(mask_x, mask_y, self.map_settings)

        self.assertAlmostEqual(scene_x, 10.0, delta=0.2)
        self.assertAlmostEqual(scene_y, -5.0, delta=0.2)

    def test_viewport_center_maps_to_scene_center(self) -> None:
        scene_x, scene_y = viewport_to_scene(
            viewport_x=500.0,
            viewport_y=250.0,
            viewport_width=1000.0,
            viewport_height=500.0,
            map_settings=self.map_settings,
        )
        self.assertAlmostEqual(scene_x, 0.0, delta=0.001)
        self.assertAlmostEqual(scene_y, 0.0, delta=0.001)

    def test_viewport_values_are_clamped(self) -> None:
        scene_x, scene_y = viewport_to_scene(
            viewport_x=-200.0,
            viewport_y=900.0,
            viewport_width=500.0,
            viewport_height=500.0,
            map_settings=self.map_settings,
        )
        self.assertAlmostEqual(scene_x, -100.0, delta=0.001)
        self.assertAlmostEqual(scene_y, -100.0, delta=0.001)


if __name__ == "__main__":
    unittest.main()

