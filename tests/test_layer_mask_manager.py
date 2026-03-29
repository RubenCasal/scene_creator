from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

try:
    from PySide6.QtCore import QPointF

    PYSIDE6_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - depende del entorno de ejecución
    QPointF = object  # type: ignore[assignment]
    PYSIDE6_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.models import CollectionNode
from proc_map_designer.domain.project_state import MapSettings

if PYSIDE6_AVAILABLE:
    from proc_map_designer.ui.canvas.brush_tool import BrushTool
    from proc_map_designer.ui.canvas.layer_mask_manager import LayerMaskManager


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 no disponible en este entorno")
class LayerMaskManagerTests(unittest.TestCase):
    def test_family_colors_are_similar_and_distinct(self) -> None:
        roots = [
            CollectionNode(
                name="vegetation",
                children=[
                    CollectionNode(name="bush"),
                    CollectionNode(name="tree"),
                ],
            ),
            CollectionNode(
                name="building",
                children=[CollectionNode(name="house")],
            ),
        ]

        map_settings = MapSettings(
            logical_width=200.0,
            logical_height=200.0,
            logical_unit="m",
            mask_width=128,
            mask_height=128,
        )
        manager = LayerMaskManager(map_settings)
        manager.sync_from_collection_tree(roots)

        bush = manager.get_layer("vegetation/bush")
        tree = manager.get_layer("vegetation/tree")
        house = manager.get_layer("building/house")
        self.assertIsNotNone(bush)
        self.assertIsNotNone(tree)
        self.assertIsNotNone(house)
        assert bush is not None and tree is not None and house is not None

        self.assertNotEqual(bush.color_hex, tree.color_hex)
        self.assertNotEqual(bush.color_hex, house.color_hex)

        bush_hue = self._hex_to_hue(bush.color_hex)
        tree_hue = self._hex_to_hue(tree.color_hex)
        house_hue = self._hex_to_hue(house.color_hex)

        self.assertLessEqual(self._hue_distance(bush_hue, tree_hue), 20.0)
        self.assertGreater(self._hue_distance(bush_hue, house_hue), 20.0)

    def test_existing_layer_colors_are_preserved_on_resync(self) -> None:
        initial_roots = [
            CollectionNode(
                name="vegetation",
                children=[CollectionNode(name="bush"), CollectionNode(name="tree")],
            )
        ]
        expanded_roots = [
            CollectionNode(
                name="vegetation",
                children=[
                    CollectionNode(name="bush"),
                    CollectionNode(name="tree"),
                    CollectionNode(name="grass"),
                ],
            )
        ]

        manager = LayerMaskManager(
            MapSettings(
                logical_width=200.0,
                logical_height=200.0,
                logical_unit="m",
                mask_width=128,
                mask_height=128,
            )
        )
        manager.sync_from_collection_tree(initial_roots)
        tree_before = manager.get_layer("vegetation/tree")
        self.assertIsNotNone(tree_before)
        assert tree_before is not None
        tree_color_before = tree_before.color_hex

        manager.sync_from_collection_tree(expanded_roots)
        tree_after = manager.get_layer("vegetation/tree")
        grass = manager.get_layer("vegetation/grass")
        self.assertIsNotNone(tree_after)
        self.assertIsNotNone(grass)
        assert tree_after is not None and grass is not None
        self.assertEqual(tree_after.color_hex, tree_color_before)
        self.assertNotEqual(grass.color_hex, tree_after.color_hex)

    def test_sync_paint_and_persist_masks(self) -> None:
        roots = [
            CollectionNode(
                name="vegetation",
                children=[
                    CollectionNode(name="pino"),
                    CollectionNode(name="arbusto"),
                ],
            )
        ]
        map_settings = MapSettings(
            logical_width=200.0,
            logical_height=200.0,
            logical_unit="m",
            mask_width=128,
            mask_height=128,
        )
        manager = LayerMaskManager(map_settings)
        manager.sync_from_collection_tree(roots)

        all_layers = manager.all_layers()
        layer_ids = [layer.layer_id for layer in all_layers]
        self.assertIn("vegetation/pino", layer_ids)
        self.assertIn("vegetation/arbusto", layer_ids)

        brush = BrushTool(radius_px=8, intensity=1.0, mode="paint")
        changed = manager.paint_stroke(
            layer_id="vegetation/pino",
            brush=brush,
            start_scene=QPointF(0.0, 0.0),
            end_scene=QPointF(10.0, 10.0),
        )
        self.assertTrue(changed)

        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            states = manager.to_layer_states(project_dir)
            self.assertGreater(len(states), 0)
            self.assertTrue(any(state.mask_data_path for state in states))

            restored = LayerMaskManager(map_settings)
            restored.load_from_project_layers(states, project_dir)
            restored_layer = restored.get_layer("vegetation/pino")
            self.assertIsNotNone(restored_layer)
            assert restored_layer is not None
            alpha = restored_layer.mask_image.pixelColor(64, 64).alpha()  # type: ignore[union-attr]
            self.assertGreater(alpha, 0)

    def _hex_to_hue(self, color_hex: str) -> float:
        color = color_hex.lstrip("#")
        r = int(color[0:2], 16) / 255.0
        g = int(color[2:4], 16) / 255.0
        b = int(color[4:6], 16) / 255.0
        import colorsys

        hue, _, _ = colorsys.rgb_to_hsv(r, g, b)
        return hue * 360.0

    def _hue_distance(self, a: float, b: float) -> float:
        diff = abs(a - b) % 360.0
        return min(diff, 360.0 - diff)


if __name__ == "__main__":
    unittest.main()
