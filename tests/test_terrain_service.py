from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.terrain_state import TerrainSettings
from proc_map_designer.services.terrain_service import TerrainService

try:
    import numpy  # noqa: F401
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False


@unittest.skipUnless(HAS_NUMPY, "numpy no disponible")
class TerrainServiceTests(unittest.TestCase):
    def test_reset_and_undo_redo(self) -> None:
        service = TerrainService(TerrainSettings(heightfield_resolution=64))
        service.begin_stroke()
        service.apply_brush((0.5, 0.5), 0.1, 0.5, "raise", "smooth", 1.0)
        self.assertTrue(service.heightfield.max() > 0.0)
        self.assertTrue(service.undo())
        self.assertAlmostEqual(float(service.heightfield.max()), 0.0)
        self.assertTrue(service.redo())
        self.assertTrue(service.heightfield.max() > 0.0)

    def test_save_and_load_heightfield(self) -> None:
        service = TerrainService(TerrainSettings(heightfield_resolution=64))
        service.begin_stroke()
        service.apply_brush((0.5, 0.5), 0.1, 0.5, "raise", "smooth", 1.0)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "heightfield.png"
            service.save_to_path(path)
            loaded = TerrainService(TerrainSettings(heightfield_resolution=64))
            loaded.load_from_path(path)
            self.assertTrue(float(loaded.heightfield.max()) > 0.0)


if __name__ == "__main__":
    unittest.main()
