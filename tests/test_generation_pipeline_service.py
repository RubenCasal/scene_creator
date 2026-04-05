from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.project_state import LatestOutputInfo, LayerState, ProjectState
from proc_map_designer.services.export_package_service import ExportPackageService
from proc_map_designer.services.final_export_service import FinalExportResult
from proc_map_designer.services.generation_pipeline_service import GenerationPipelineService
from proc_map_designer.services.generation_service import GenerationResult, GenerationService, GenerationServiceError
from proc_map_designer.services.validation_service import ValidationReport


class _FakeRunner:
    def __init__(self) -> None:
        self.last_opened: Path | None = None

    def open_blend_interactive(self, blend_file: Path) -> None:
        self.last_opened = blend_file


class _FakeValidationService:
    def validate_package(self, project_json_path: Path, log=None) -> ValidationReport:
        if log is not None:
            log(f"validated {project_json_path}")
        return ValidationReport(success=True, warnings=["warn-a"])


class _FakeGenerationService:
    def generate(self, project_json_path: Path, backend_id: str, output_blend: Path | None, log=None) -> GenerationResult:
        if log is not None:
            log(f"generated {backend_id}")
        return GenerationResult(
            success=True,
            backend=backend_id,
            output_blend=str(output_blend or (project_json_path.parent / "working.blend")),
            warnings=["warn-b"],
            placed_layers=[{"layer_id": "vegetation/pino", "count": 3}],
        )


class _FakeFinalExportService:
    def export_final(self, project_json_path: Path, working_blend_path: Path, output_blend_path: Path, log=None) -> FinalExportResult:
        if log is not None:
            log(f"final {working_blend_path}")
        return FinalExportResult(success=True, output_blend=str(output_blend_path))


class GenerationPipelineServiceTests(unittest.TestCase):
    def _build_service(self) -> GenerationPipelineService:
        return GenerationPipelineService(
            export_service=ExportPackageService(),
            validation_service=_FakeValidationService(),
            generation_service=_FakeGenerationService(),
            final_export_service=_FakeFinalExportService(),
            runner=_FakeRunner(),
        )

    def test_validate_and_generate_with_python_batch_backend(self) -> None:
        service = self._build_service()
        project = ProjectState.create_new(
            project_name="PipelineTest",
            source_blend="/tmp/source.blend",
            blender_executable="/usr/bin/blender",
            output_blend="/tmp/result.blend",
        )
        project.map_settings.base_plane_object = "BasePlane"
        project.layers = [LayerState(layer_id="vegetation/pino", name="Pino")]

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "pkg"

            def exporter(export_root: Path, layer_ids: list[str]) -> dict[str, str]:
                masks_dir = export_root / "masks"
                masks_dir.mkdir(parents=True, exist_ok=True)
                exported: dict[str, str] = {}
                for index, layer_id in enumerate(layer_ids):
                    relative = Path("masks") / f"{index:03d}_{layer_id.replace('/', '_')}.png"
                    (export_root / relative).write_bytes(b"fake-png")
                    exported[layer_id] = relative.as_posix()
                return exported

            validate_result = service.validate_project(
                project,
                package_dir,
                exporter,
                backend_id="python_batch",
            )
            self.assertEqual(validate_result.status, "validated")
            self.assertEqual(validate_result.validation_warnings, ["warn-a"])
            self.assertTrue(Path(validate_result.export_manifest_path).exists())

            generate_result = service.generate_project(
                project,
                package_dir,
                exporter,
                backend_id="python_batch",
            )
            self.assertEqual(generate_result.status, "completed")
            self.assertEqual(generate_result.result_path, "/tmp/result.blend")
            self.assertEqual(generate_result.used_layer_ids, ["vegetation/pino"])

    def test_final_export_preserves_existing_result_metadata(self) -> None:
        service = self._build_service()
        latest_output = service.final_export(
            latest_output=LatestOutputInfo(
                backend_id="python_batch",
                status="completed",
                export_manifest_path="/tmp/pkg/project.json",
                result_path="/tmp/output.blend",
                used_layer_ids=["vegetation/pino"],
                validation_warnings=["warn-a"],
            ),
            destination_path=Path("/tmp/final_map.blend"),
        )
        self.assertEqual(latest_output.final_output_path, "/tmp/final_map.blend")
        self.assertEqual(latest_output.used_layer_ids, ["vegetation/pino"])

    def test_generation_service_normalizes_directory_output_path(self) -> None:
        service = GenerationService(
            runner=_FakeRunner(),
            python_batch_script=Path("/tmp/python_batch.py"),
            geometry_nodes_script=Path("/tmp/gn.py"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            resolved = service._resolve_output_path(output_dir, Path("/tmp/package_output.blend"))
            self.assertEqual(resolved, (output_dir / "working_map.blend").resolve())

    def test_generation_service_rejects_when_no_layers_enabled(self) -> None:
        service = GenerationService(
            runner=_FakeRunner(),
            python_batch_script=Path("/tmp/python_batch.py"),
            geometry_nodes_script=Path("/tmp/gn.py"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir)
            source_blend = package_dir / "source.blend"
            source_blend.write_bytes(b"blend")
            mask_dir = package_dir / "masks"
            mask_dir.mkdir()
            (mask_dir / "000_test.png").write_bytes(b"png")
            project_json = package_dir / "project.json"
            project_json.write_text(
                (
                    "{"
                    '\n  "schema_version": 1,'
                    '\n  "project_id": "proj",'
                    f'\n  "source_blend": "{source_blend.as_posix()}",'
                    '\n  "blender_executable": "/usr/bin/blender",'
                    f'\n  "output_blend": "{(package_dir / "out.blend").as_posix()}",'
                    '\n  "map": {'
                    '\n    "width": 10.0,'
                    '\n    "height": 10.0,'
                    '\n    "unit": "m",'
                    '\n    "mask_resolution": {"width": 1, "height": 1},'
                    '\n    "base_plane_object": "Plane"'
                    '\n  },'
                    '\n  "layers": ['
                    '\n    {'
                    '\n      "category": "vegetation",'
                    '\n      "name": "Pino",'
                    '\n      "blender_collection": "vegetation/pino",'
                    '\n      "enabled": false,'
                    '\n      "mask_path": "masks/000_test.png",'
                    '\n      "settings": {'
                    '\n        "density": 1.0,'
                    '\n        "min_distance": 0.0,'
                    '\n        "allow_overlap": true,'
                    '\n        "scale_min": 1.0,'
                    '\n        "scale_max": 1.0,'
                    '\n        "rotation_random_z": 0.0,'
                    '\n        "seed": 1,'
                    '\n        "priority": 0'
                    '\n      }'
                    '\n    }'
                    '\n  ]'
                    '\n}'
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationServiceError):
                service.generate(project_json, "python_batch", None)


if __name__ == "__main__":
    unittest.main()
