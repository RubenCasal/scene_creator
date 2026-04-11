from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.project_state import (
    LayerGenerationSettings,
    LayerState,
    ProjectState,
    RoadGeneratorSettings,
    RoadPoint,
    RoadState,
    RoadStyleSettings,
)
from proc_map_designer.services.export_package_service import ExportPackageError, ExportPackageService


class ExportPackageServiceTests(unittest.TestCase):
    def test_export_package_writes_project_manifest_and_masks(self) -> None:
        service = ExportPackageService()
        project = ProjectState.create_new(
            project_name="ExportTest",
            source_blend="/tmp/source.blend",
            blender_executable="/usr/bin/blender",
            output_blend="/tmp/output.blend",
        )
        project.map_settings.base_plane_object = "BasePlane"
        project.generation_settings.seed = 77
        project.layers = [
            LayerState(
                layer_id="vegetation/pino",
                name="Pino",
                generation_settings=LayerGenerationSettings(
                    enabled=True,
                    density=2.5,
                    min_distance=1.0,
                    allow_overlap=False,
                    scale_min=0.8,
                    scale_max=1.2,
                    rotation_random_z=45.0,
                    seed=None,
                    priority=8,
                ),
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "export_pkg"

            def exporter(export_root: Path, layer_ids: list[str]) -> dict[str, str]:
                masks_dir = export_root / "masks"
                masks_dir.mkdir(parents=True, exist_ok=True)
                output: dict[str, str] = {}
                for index, layer_id in enumerate(layer_ids):
                    filename = f"{index:03d}_{layer_id.replace('/', '_')}.png"
                    relative = Path("masks") / filename
                    (export_root / relative).write_bytes(b"fake-png")
                    output[layer_id] = relative.as_posix()
                return output

            project_json_path = service.export_package(project, package_dir, exporter)

            self.assertTrue(project_json_path.exists())
            payload = json.loads(project_json_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["project_id"], project.project_id)
            self.assertEqual(payload["source_blend"], "/tmp/source.blend")
            self.assertEqual(payload["blender_executable"], "/usr/bin/blender")
            self.assertEqual(payload["output_blend"], "/tmp/output.blend")
            self.assertEqual(payload["map"]["base_plane_object"], "BasePlane")
            self.assertEqual(payload["map"]["mask_resolution"]["width"], project.map_settings.mask_width)
            self.assertEqual(payload["map"]["mask_resolution"]["height"], project.map_settings.mask_height)

            self.assertEqual(len(payload["layers"]), 1)
            layer = payload["layers"][0]
            self.assertEqual(layer["category"], "vegetation")
            self.assertEqual(layer["name"], "Pino")
            self.assertEqual(layer["blender_collection"], "vegetation/pino")
            self.assertEqual(layer["mask_path"], "masks/000_vegetation_pino.png")
            # seed de capa ausente => fallback a seed global de proyecto
            self.assertEqual(layer["settings"]["seed"], 77)

    def test_export_package_includes_roads_and_copies_geometry_asset(self) -> None:
        service = ExportPackageService()
        project = ProjectState.create_new(
            project_name="RoadExport",
            source_blend="/tmp/source.blend",
            blender_executable="/usr/bin/blender",
            output_blend="/tmp/output.blend",
        )
        project.map_settings.base_plane_object = "BasePlane"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            asset_path = temp_path / "geometry_nodes_procedural_road.json"
            asset_path.write_text('{"object": "Procedural Road", "root_tree": {"tree_name": "Road", "nodes": [], "links": []}}', encoding="utf-8")
            material_blend = temp_path / "road.blend"
            material_blend.write_bytes(b"blend")
            project.roads = [
                RoadState(
                    road_id="road/001",
                    name="Road 1",
                    points=[RoadPoint(x=0.0, y=0.0), RoadPoint(x=10.0, y=5.0)],
                    style=RoadStyleSettings(width=6.0, resolution=20),
                    generator=RoadGeneratorSettings(
                        seed=55,
                        geometry_nodes_asset_path=str(asset_path),
                        material_library_blend_path=str(material_blend),
                    ),
                )
            ]

            manifest_path = service.export_package(project, temp_path / "pkg", lambda _root, _layer_ids: {})
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["roads"]), 1)
            self.assertEqual(payload["roads"][0]["road_id"], "road/001")
            self.assertEqual(payload["roads"][0]["style"]["width"], 6.0)
            self.assertEqual(payload["roads"][0]["style"]["profile"], "single")
            copied_asset = (manifest_path.parent / payload["roads"][0]["generator"]["geometry_nodes_asset_path"]).resolve()
            self.assertTrue(copied_asset.exists())
            self.assertEqual(payload["roads"][0]["generator"]["material_library_blend_path"], str(material_blend.resolve()))

    def test_export_fails_when_required_base_plane_is_missing(self) -> None:
        service = ExportPackageService()
        project = ProjectState.create_new(
            source_blend="/tmp/source.blend",
            blender_executable="/usr/bin/blender",
            output_blend="/tmp/output.blend",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ExportPackageError):
                service.export_package(project, Path(temp_dir), lambda _root, _layer_ids: {})

    def test_export_fails_when_layer_mask_is_not_exported(self) -> None:
        service = ExportPackageService()
        project = ProjectState.create_new(
            source_blend="/tmp/source.blend",
            blender_executable="/usr/bin/blender",
            output_blend="/tmp/output.blend",
        )
        project.map_settings.base_plane_object = "BasePlane"
        project.layers = [LayerState(layer_id="building/house", name="House")]

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ExportPackageError):
                service.export_package(project, Path(temp_dir), lambda _root, _layer_ids: {})

    def test_export_uses_stable_derived_seed_when_randomize_seed_is_enabled(self) -> None:
        service = ExportPackageService()
        project = ProjectState.create_new(
            project_name="SeedTest",
            source_blend="/tmp/source.blend",
            blender_executable="/usr/bin/blender",
            output_blend="/tmp/output.blend",
        )
        project.map_settings.base_plane_object = "BasePlane"
        project.layers = [LayerState(layer_id="vegetation/pino", name="Pino")]

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir)

            def exporter(export_root: Path, layer_ids: list[str]) -> dict[str, str]:
                masks_dir = export_root / "masks"
                masks_dir.mkdir(parents=True, exist_ok=True)
                relative = Path("masks") / "000_vegetation_pino.png"
                (export_root / relative).write_bytes(b"fake-png")
                return {layer_ids[0]: relative.as_posix()}

            manifest_path = service.export_package(project, package_dir, exporter)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIsInstance(payload["layers"][0]["settings"]["seed"], int)
            self.assertNotEqual(payload["layers"][0]["settings"]["seed"], 0)


if __name__ == "__main__":
    unittest.main()
