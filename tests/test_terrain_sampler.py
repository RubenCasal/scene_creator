from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.blender_bridge.terrain_sampler import TerrainSampler

try:
    import numpy  # noqa: F401
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


@unittest.skipIf(Image is None or not HAS_NUMPY, "Pillow/numpy no disponible")
class TerrainSamplerTests(unittest.TestCase):
    def test_sample_at_returns_scaled_height(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "heightfield.png"
            image = Image.new("I;16", (2, 2))
            image.putdata([0, 65535, 32768, 65535])
            image.save(path)
            sampler = TerrainSampler(path, max_height=10.0, map_width=2.0, map_height=2.0)
            self.assertGreaterEqual(sampler.sample_at(0.9, 0.9), 0.0)
            self.assertLessEqual(sampler.sample_at(0.9, 0.9), 10.0)
            normal = sampler.sample_normal_at(0.0, 0.0)
            self.assertEqual(len(normal), 3)


if __name__ == "__main__":
    unittest.main()
