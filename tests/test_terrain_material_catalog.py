from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.services.terrain_material_catalog import load_terrain_material_catalog


class TerrainMaterialCatalogTests(unittest.TestCase):
    def test_default_catalog_loads_expected_entries(self) -> None:
        catalog = load_terrain_material_catalog()
        self.assertTrue(catalog.blend_path.name.endswith("ground_materials.blend"))
        self.assertEqual(
            [entry.id for entry in catalog.entries],
            [
                "terrain_dirt",
                "terrain_dry_grass",
                "terrain_grass",
                "terrain_rocky_ground",
                "terrain_wet_rocky_ground",
            ],
        )


if __name__ == "__main__":
    unittest.main()
