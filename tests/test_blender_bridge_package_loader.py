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

from proc_map_designer.blender_bridge.package_loader import load_export_package


class PackageLoaderTests(unittest.TestCase):
    def test_load_package_reads_layers_and_masks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir)
            masks_dir = package_dir / "masks"
            masks_dir.mkdir()
            mask_file = masks_dir / "000_test.png"
            mask_file.write_bytes(b"fake")

            manifest = {
                "schema_version": 1,
                "project_id": "proj-123",
                "source_blend": "/tmp/source.blend",
                "blender_executable": "/usr/bin/blender",
                "output_blend": "/tmp/output.blend",
                "map": {
                    "width": 100.0,
                    "height": 200.0,
                    "unit": "m",
                    "base_plane_object": "BasePlane",
                    "mask_resolution": {"width": 4, "height": 4},
                },
                "layers": [
                    {
                        "category": "vegetation",
                        "name": "Pino",
                        "blender_collection": "vegetation/pino",
                        "enabled": True,
                        "mask_path": "masks/000_test.png",
                        "settings": {
                            "density": 1.0,
                            "min_distance": 0.5,
                            "allow_overlap": False,
                            "scale_min": 0.8,
                            "scale_max": 1.2,
                            "rotation_random_z": 90.0,
                            "seed": 7,
                            "priority": 3,
                        },
                    }
                ],
            }

            manifest_path = package_dir / "project.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            package = load_export_package(manifest_path, require_mask_files=True)

            self.assertEqual(package.project_id, "proj-123")
            self.assertEqual(package.map.base_plane_object, "BasePlane")
            self.assertEqual(len(package.layers), 1)
            layer = package.layers[0]
            self.assertTrue(layer.mask_exists)
            self.assertEqual(layer.settings.seed, 7)
            self.assertAlmostEqual(layer.settings.scale_min, 0.8)

    def test_missing_mask_reports_flag_without_strict_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir)
            manifest = {
                "schema_version": 1,
                "project_id": "proj-456",
                "source_blend": "/tmp/source.blend",
                "blender_executable": "/usr/bin/blender",
                "output_blend": "/tmp/output.blend",
                "map": {
                    "width": 50.0,
                    "height": 50.0,
                    "unit": "m",
                    "base_plane_object": "Plane",
                    "mask_resolution": {"width": 8, "height": 8},
                },
                "layers": [
                    {
                        "category": "building",
                        "name": "House",
                        "blender_collection": "building/house",
                        "enabled": True,
                        "mask_path": "masks/missing.png",
                        "settings": {
                            "density": 1.0,
                            "min_distance": 0.0,
                            "allow_overlap": True,
                            "scale_min": 1.0,
                            "scale_max": 1.0,
                            "rotation_random_z": 0.0,
                            "seed": 0,
                            "priority": 0,
                        },
                    }
                ],
            }
            manifest_path = package_dir / "project.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            package = load_export_package(manifest_path)
            self.assertFalse(package.layers[0].mask_exists)

            with self.assertRaises(ValueError):
                load_export_package(manifest_path, require_mask_files=True)

    def test_missing_required_layer_setting_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir)
            masks_dir = package_dir / "masks"
            masks_dir.mkdir()
            (masks_dir / "ok.png").write_bytes(b"fake")

            manifest = {
                "schema_version": 1,
                "project_id": "proj-789",
                "source_blend": "/tmp/source.blend",
                "blender_executable": "/usr/bin/blender",
                "output_blend": "/tmp/output.blend",
                "map": {
                    "width": 50.0,
                    "height": 50.0,
                    "unit": "m",
                    "base_plane_object": "Plane",
                    "mask_resolution": {"width": 8, "height": 8},
                },
                "layers": [
                    {
                        "category": "building",
                        "name": "House",
                        "blender_collection": "building/house",
                        "enabled": True,
                        "mask_path": "masks/ok.png",
                        "settings": {
                            "density": 1.0,
                            "min_distance": 0.0,
                            "allow_overlap": True,
                            "scale_min": 1.0,
                            "scale_max": 1.0,
                            "rotation_random_z": 0.0,
                            "seed": 0,
                        },
                    }
                ],
            }
            manifest_path = package_dir / "project.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_export_package(manifest_path, require_mask_files=True)

    def test_load_package_reads_roads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir)
            assets_dir = package_dir / "assets" / "roads"
            assets_dir.mkdir(parents=True)
            asset_file = assets_dir / "geometry_nodes_procedural_road.json"
            asset_file.write_text('{"object": "Procedural Road", "root_tree": {"tree_name": "Road", "nodes": [], "links": []}}', encoding="utf-8")
            material_blend = package_dir / "road.blend"
            material_blend.write_bytes(b"blend")

            manifest = {
                "schema_version": 2,
                "project_id": "proj-road",
                "source_blend": "/tmp/source.blend",
                "blender_executable": "/usr/bin/blender",
                "output_blend": "/tmp/output.blend",
                "map": {
                    "width": 100.0,
                    "height": 100.0,
                    "unit": "m",
                    "base_plane_object": "BasePlane",
                    "mask_resolution": {"width": 4, "height": 4},
                },
                "layers": [],
                "roads": [
                    {
                        "road_id": "road/001",
                        "name": "Road 1",
                        "visible": True,
                        "closed": False,
                        "points": [{"x": 0.0, "y": 0.0}, {"x": 10.0, "y": 5.0}],
                        "style": {"width": 6.0, "resolution": 24, "profile": "double"},
                        "generator": {
                            "seed": 9,
                            "geometry_nodes_asset_path": "assets/roads/geometry_nodes_procedural_road.json",
                            "material_library_blend_path": str(material_blend),
                        },
                    }
                ],
            }
            manifest_path = package_dir / "project.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            package = load_export_package(manifest_path, require_mask_files=True)
            self.assertEqual(len(package.roads), 1)
            self.assertEqual(package.roads[0].road_id, "road/001")
            self.assertEqual(package.roads[0].style.profile, "double")
            self.assertTrue(package.roads[0].generator.geometry_nodes_asset_exists)
            self.assertTrue(package.roads[0].generator.material_library_blend_exists)


if __name__ == "__main__":
    unittest.main()
