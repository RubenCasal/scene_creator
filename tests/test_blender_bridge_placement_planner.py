from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.blender_bridge.package_loader import ExportLayerSettings
from proc_map_designer.blender_bridge.placement_planner import (
    LayerPlanInput,
    MapDimensions,
    MaskField,
    plan_generation,
)


class PlacementPlannerTests(unittest.TestCase):
    def test_plan_generation_is_deterministic(self) -> None:
        dims = MapDimensions(width=10.0, height=10.0, mask_width=2, mask_height=1)
        mask = MaskField(width=2, height=1, values=(1.0, 0.5))
        settings = ExportLayerSettings(
            density=1.0,
            min_distance=0.0,
            allow_overlap=True,
            scale_min=1.0,
            scale_max=1.0,
            rotation_random_z=0.0,
            seed=42,
            priority=0,
        )
        layer = LayerPlanInput(
            layer_id="vegetation/pino",
            category="vegetation",
            enabled=True,
            settings=settings,
            mask=mask,
        )

        plan_a = plan_generation("project-1", dims, [layer])
        plan_b = plan_generation("project-1", dims, [layer])

        self.assertEqual(len(plan_a[0].placements), len(plan_b[0].placements))
        self.assertEqual(
            [(p.x, p.y) for p in plan_a[0].placements],
            [(p.x, p.y) for p in plan_b[0].placements],
        )

    def test_priority_blocks_lower_layers_when_overlap_not_allowed(self) -> None:
        dims = MapDimensions(width=10.0, height=10.0, mask_width=2, mask_height=2)
        mask_values = (1.0, 1.0, 1.0, 1.0)
        mask = MaskField(width=2, height=2, values=mask_values)

        high = LayerPlanInput(
            layer_id="category/high",
            category="category",
            enabled=True,
            settings=ExportLayerSettings(
                density=1.0,
                min_distance=100.0,
                allow_overlap=False,
                scale_min=1.0,
                scale_max=1.0,
                rotation_random_z=0.0,
                seed=1,
                priority=10,
            ),
            mask=mask,
        )
        low = LayerPlanInput(
            layer_id="category/low",
            category="category",
            enabled=True,
            settings=ExportLayerSettings(
                density=1.0,
                min_distance=100.0,
                allow_overlap=False,
                scale_min=1.0,
                scale_max=1.0,
                rotation_random_z=0.0,
                seed=1,
                priority=1,
            ),
            mask=mask,
        )

        plans = plan_generation("project-x", dims, [low, high])
        plan_by_id = {plan.layer_id: plan for plan in plans}
        self.assertGreater(len(plan_by_id["category/high"].placements), 0)
        self.assertEqual(len(plan_by_id["category/low"].placements), 0)

    def test_min_distance_applies_within_layer_even_with_overlap(self) -> None:
        dims = MapDimensions(width=10.0, height=10.0, mask_width=2, mask_height=2)
        mask_values = (1.0,) * 4
        mask = MaskField(width=2, height=2, values=mask_values)
        layer = LayerPlanInput(
            layer_id="cat/sample",
            category="cat",
            enabled=True,
            settings=ExportLayerSettings(
                density=4.0,
                min_distance=100.0,
                allow_overlap=True,
                scale_min=1.0,
                scale_max=1.0,
                rotation_random_z=0.0,
                seed=99,
                priority=0,
            ),
            mask=mask,
        )

        plan = plan_generation("proj", dims, [layer])[0]
        # Despite high density, the large min_distance should limit output dramatically.
        self.assertLessEqual(len(plan.placements), 1)

    def test_uniform_density_is_not_resolution_dependent(self) -> None:
        settings = ExportLayerSettings(
            density=1.0,
            min_distance=0.0,
            allow_overlap=True,
            scale_min=1.0,
            scale_max=1.0,
            rotation_random_z=0.0,
            seed=7,
            priority=0,
        )

        low_res_plan = plan_generation(
            "proj",
            MapDimensions(width=10.0, height=10.0, mask_width=10, mask_height=10),
            [
                LayerPlanInput(
                    layer_id="veg/low",
                    category="veg",
                    enabled=True,
                    settings=settings,
                    mask=MaskField(width=10, height=10, values=(1.0,) * 100),
                )
            ],
        )[0]

        high_res_plan = plan_generation(
            "proj",
            MapDimensions(width=10.0, height=10.0, mask_width=100, mask_height=100),
            [
                LayerPlanInput(
                    layer_id="veg/high",
                    category="veg",
                    enabled=True,
                    settings=settings,
                    mask=MaskField(width=100, height=100, values=(1.0,) * 10000),
                )
            ],
        )[0]

        self.assertEqual(len(low_res_plan.placements), len(high_res_plan.placements))


if __name__ == "__main__":
    unittest.main()
