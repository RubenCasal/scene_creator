from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.blender_bridge.mask_decoder import decode_mask_values


class MaskDecoderTests(unittest.TestCase):
    def test_rgba_grayscale_uses_luminance_not_alpha(self) -> None:
        buffer = [
            0.0, 0.0, 0.0, 1.0,
            0.5, 0.5, 0.5, 1.0,
            1.0, 1.0, 1.0, 1.0,
        ]

        values = decode_mask_values(width=3, height=1, channels=4, buffer=buffer, flip_y=False)

        self.assertEqual(values, (0.0, 0.5, 1.0))

    def test_alpha_modulates_luminance(self) -> None:
        buffer = [1.0, 1.0, 1.0, 0.25]

        values = decode_mask_values(width=1, height=1, channels=4, buffer=buffer, flip_y=False)

        self.assertEqual(values, (0.25,))


if __name__ == "__main__":
    unittest.main()
