from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.models import CollectionNode
from proc_map_designer.domain.project_state import (
    LayerGenerationSettings,
    LayerState,
    LatestOutputInfo,
    MapSettings,
    ProjectState,
    RoadGeneratorSettings,
    RoadPoint,
    RoadState,
    RoadStyleSettings,
)


class ProjectStateTests(unittest.TestCase):
    def test_project_round_trip_serialization(self) -> None:
        state = ProjectState.create_new(
            project_name="MapaTest",
            source_blend="/tmp/example.blend",
            blender_executable="/usr/bin/blender",
            output_blend="/tmp/output.blend",
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
            base_plane_object="BasePlane",
            terrain_material_id="terrain_dirt",
        )

        payload = state.to_dict()
        loaded = ProjectState.from_dict(payload)

        self.assertEqual(loaded.schema_version, 3)
        self.assertEqual(loaded.project_name, "MapaTest")
        self.assertEqual(loaded.source_blend, "/tmp/example.blend")
        self.assertEqual(loaded.output_blend, "/tmp/output.blend")
        self.assertEqual(loaded.collection_tree[0].name, "vegetation")
        self.assertEqual(loaded.collection_tree[0].children[0].object_count, 3)
        self.assertEqual(loaded.map_settings.mask_width, 2048)
        self.assertEqual(loaded.map_settings.base_plane_object, "BasePlane")
        self.assertEqual(loaded.map_settings.terrain_material_id, "terrain_dirt")
        self.assertFalse(loaded.terrain_settings.enabled)

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

    def test_legacy_layer_without_generation_settings_is_supported(self) -> None:
        state = ProjectState.create_new(project_name="Legacy")
        state.layers = [
            LayerState(
                layer_id="vegetation/tree",
                name="vegetation/tree",
            )
        ]
        payload = state.to_dict()
        payload["layers"][0].pop("generation_settings", None)

        loaded = ProjectState.from_dict(payload)
        settings = loaded.layers[0].generation_settings
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.density, 1.0)
        self.assertEqual(settings.min_distance, 0.0)
        self.assertEqual(settings.scale_min, 1.0)
        self.assertEqual(settings.scale_max, 1.0)
        self.assertEqual(settings.rotation_random_z, 180.0)

    def test_legacy_project_without_output_blend_and_base_plane_is_supported(self) -> None:
        payload = ProjectState.create_new(project_name="LegacyCompat").to_dict()
        payload.pop("output_blend", None)
        payload["map_settings"].pop("base_plane_object", None)
        payload.pop("roads", None)
        payload["schema_version"] = 1

        loaded = ProjectState.from_dict(payload)

        self.assertEqual(loaded.output_blend, "")
        self.assertEqual(loaded.map_settings.base_plane_object, "")
        self.assertEqual(loaded.map_settings.terrain_material_id, "terrain_grass")

    def test_road_round_trip_serialization(self) -> None:
        state = ProjectState.create_new(project_name="Roads")
        state.roads = [
            RoadState(
                road_id="road/001",
                name="road/001",
                points=[RoadPoint(x=-10.0, y=5.0), RoadPoint(x=12.0, y=8.0)],
                style=RoadStyleSettings(width=7.5, resolution=32),
                generator=RoadGeneratorSettings(seed=123, material_library_blend_path="blender_defaults/road.blend"),
            )
        ]

        loaded = ProjectState.from_dict(state.to_dict())
        self.assertEqual(len(loaded.roads), 1)
        self.assertEqual(loaded.roads[0].road_id, "road/001")
        self.assertEqual(loaded.roads[0].style.width, 7.5)
        self.assertEqual(loaded.roads[0].style.profile, "single")
        self.assertEqual(loaded.roads[0].generator.seed, 123)
        self.assertEqual(loaded.roads[0].generator.material_library_blend_path, "blender_defaults/road.blend")

    def test_road_style_profile_round_trip(self) -> None:
        state = ProjectState.create_new(project_name="RoadProfile")
        state.roads = [
            RoadState(
                road_id="road/002",
                name="road/002",
                points=[RoadPoint(x=0.0, y=0.0), RoadPoint(x=20.0, y=5.0)],
                style=RoadStyleSettings(width=8.0, resolution=16, profile="double"),
            )
        ]

        loaded = ProjectState.from_dict(state.to_dict())
        self.assertEqual(loaded.roads[0].style.profile, "double")

    def test_legacy_project_without_roads_is_supported(self) -> None:
        payload = ProjectState.create_new(project_name="LegacyRoadCompat").to_dict()
        payload["schema_version"] = 2
        payload.pop("roads", None)
        payload.pop("terrain_settings", None)

        loaded = ProjectState.from_dict(payload)
        self.assertEqual(loaded.roads, [])
        self.assertFalse(loaded.terrain_settings.enabled)

    def test_layer_generation_settings_round_trip(self) -> None:
        state = ProjectState.create_new(project_name="GenLayer")
        state.layers = [
            LayerState(
                layer_id="vegetation/tree",
                name="vegetation/tree",
                generation_settings=LayerGenerationSettings(
                    enabled=False,
                    density=2.5,
                    seed=123,
                    allow_overlap=False,
                    min_distance=1.25,
                    scale_min=0.7,
                    scale_max=1.8,
                    rotation_random_z=45.0,
                    priority=9,
                    bounding_radius=0.45,
                    slope_limit_deg=25.0,
                    max_count=150,
                    align_to_surface_normal=True,
                ),
            )
        ]

        loaded = ProjectState.from_dict(state.to_dict())
        settings = loaded.layers[0].generation_settings
        self.assertFalse(settings.enabled)
        self.assertEqual(settings.density, 2.5)
        self.assertEqual(settings.seed, 123)
        self.assertFalse(settings.allow_overlap)
        self.assertEqual(settings.min_distance, 1.25)
        self.assertEqual(settings.scale_min, 0.7)
        self.assertEqual(settings.scale_max, 1.8)
        self.assertEqual(settings.rotation_random_z, 45.0)
        self.assertEqual(settings.priority, 9)
        self.assertEqual(settings.bounding_radius, 0.45)
        self.assertEqual(settings.slope_limit_deg, 25.0)
        self.assertEqual(settings.max_count, 150)
        self.assertTrue(settings.align_to_surface_normal)

    def test_layer_generation_settings_validation(self) -> None:
        with self.assertRaises(ValueError):
            LayerGenerationSettings(scale_min=2.0, scale_max=1.0)
        with self.assertRaises(ValueError):
            LayerGenerationSettings(density=-0.1)
        with self.assertRaises(ValueError):
            LayerGenerationSettings(min_distance=-0.1)

    def test_latest_output_metadata_round_trip(self) -> None:
        state = ProjectState.create_new(project_name="LatestOutput")
        state.latest_output = LatestOutputInfo(
            backend_id="python_batch",
            status="completed",
            export_manifest_path="/tmp/export/project.json",
            result_path="/tmp/output.blend",
            final_output_path="",
            completed_at="2026-04-05T10:00:00+00:00",
            error_message="",
            used_layer_ids=["vegetation/pino"],
            validation_warnings=["mask dimensions ok"],
        )

        loaded = ProjectState.from_dict(state.to_dict())

        self.assertIsNotNone(loaded.latest_output)
        assert loaded.latest_output is not None
        self.assertEqual(loaded.latest_output.backend_id, "python_batch")
        self.assertEqual(loaded.latest_output.status, "completed")
        self.assertEqual(loaded.latest_output.export_manifest_path, "/tmp/export/project.json")
        self.assertEqual(loaded.latest_output.result_path, "/tmp/output.blend")
        self.assertEqual(loaded.latest_output.used_layer_ids, ["vegetation/pino"])
        self.assertEqual(loaded.latest_output.validation_warnings, ["mask dimensions ok"])


if __name__ == "__main__":
    unittest.main()
