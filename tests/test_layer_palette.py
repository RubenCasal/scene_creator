from __future__ import annotations

import colorsys
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.layer_palette import (
    base_hue_for_category,
    is_valid_hex_color,
    split_layer_id,
    variant_color_for_sibling,
)


def _hex_to_hue(color_hex: str) -> float:
    value = color_hex.lstrip("#")
    r = int(value[0:2], 16) / 255.0
    g = int(value[2:4], 16) / 255.0
    b = int(value[4:6], 16) / 255.0
    hue, _, _ = colorsys.rgb_to_hsv(r, g, b)
    return hue * 360.0


def _circular_hue_distance(a: float, b: float) -> float:
    diff = abs(a - b) % 360.0
    return min(diff, 360.0 - diff)


class LayerPaletteTests(unittest.TestCase):
    def test_split_layer_id(self) -> None:
        category, leaf = split_layer_id("vegetation/tree")
        self.assertEqual(category, "vegetation")
        self.assertEqual(leaf, "tree")

        category_single, leaf_single = split_layer_id("building")
        self.assertEqual(category_single, "building")
        self.assertEqual(leaf_single, "building")

    def test_base_hue_is_deterministic(self) -> None:
        hue_a = base_hue_for_category("vegetation")
        hue_b = base_hue_for_category("vegetation")
        self.assertEqual(hue_a, hue_b)

    def test_sibling_colors_same_family_but_distinct(self) -> None:
        color_0 = variant_color_for_sibling("vegetation", 0)
        color_1 = variant_color_for_sibling("vegetation", 1)
        color_2 = variant_color_for_sibling("vegetation", 2)

        self.assertNotEqual(color_0, color_1)
        self.assertNotEqual(color_1, color_2)
        self.assertTrue(is_valid_hex_color(color_0))
        self.assertTrue(is_valid_hex_color(color_1))
        self.assertTrue(is_valid_hex_color(color_2))

        hue_0 = _hex_to_hue(color_0)
        hue_1 = _hex_to_hue(color_1)
        hue_2 = _hex_to_hue(color_2)

        self.assertLessEqual(_circular_hue_distance(hue_0, hue_1), 20.0)
        self.assertLessEqual(_circular_hue_distance(hue_0, hue_2), 20.0)

    def test_different_categories_are_stable(self) -> None:
        color_vegetation_a = variant_color_for_sibling("vegetation", 0)
        color_vegetation_b = variant_color_for_sibling("vegetation", 0)
        color_building = variant_color_for_sibling("building", 0)

        self.assertEqual(color_vegetation_a, color_vegetation_b)
        self.assertNotEqual(color_vegetation_a, color_building)


if __name__ == "__main__":
    unittest.main()

