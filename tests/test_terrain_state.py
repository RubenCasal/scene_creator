from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.project_state import ProjectState
from proc_map_designer.domain.terrain_state import TerrainNoiseSettings, TerrainSettings


class TerrainStateTests(unittest.TestCase):
    def test_terrain_settings_round_trip(self) -> None:
        settings = TerrainSettings(
            enabled=True,
            max_height=25.0,
            viewport_subdivision=6,
            export_subdivision=7,
            heightfield_resolution=512,
            heightfield_path="terrain/heightfield.png",
            noise=TerrainNoiseSettings(enabled=True, scale=2.0, strength=0.4, octaves=5, roughness=0.6, seed=7),
        )
        loaded = TerrainSettings.from_dict(settings.to_dict())
        self.assertTrue(loaded.enabled)
        self.assertEqual(loaded.heightfield_path, "terrain/heightfield.png")
        self.assertTrue(loaded.noise.enabled)
        self.assertEqual(loaded.noise.seed, 7)

    def test_v2_project_loads_default_terrain_settings(self) -> None:
        payload = ProjectState.create_new().to_dict()
        payload["schema_version"] = 2
        payload.pop("terrain_settings", None)
        loaded = ProjectState.from_dict(payload)
        self.assertFalse(loaded.terrain_settings.enabled)

    def test_invalid_terrain_validation(self) -> None:
        with self.assertRaises(ValueError):
            TerrainSettings(max_height=-1.0)
        with self.assertRaises(ValueError):
            TerrainSettings(viewport_subdivision=3)


if __name__ == "__main__":
    unittest.main()
