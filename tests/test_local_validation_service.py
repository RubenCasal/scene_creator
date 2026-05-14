from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.project_state import LayerGenerationSettings, LayerState, ProjectState, SingleInstancePlacement
from proc_map_designer.services.local_validation_service import LocalValidationService


class LocalValidationServiceTests(unittest.TestCase):
    def test_missing_blend_and_output_are_reported(self) -> None:
        project = ProjectState.create_new()
        result = LocalValidationService().validate(project, {})
        self.assertFalse(result.success)
        self.assertTrue(any("source .blend" in error for error in result.errors))

    def test_single_mode_without_placements_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_blend = Path(tmp_dir) / "source.blend"
            source_blend.write_bytes(b"blend")
            blender_exe = Path(tmp_dir) / "blender"
            blender_exe.write_text("#!/bin/sh\n", encoding="utf-8")
            output_blend = Path(tmp_dir) / "out.blend"
            project = ProjectState.create_new(
                source_blend=str(source_blend),
                blender_executable=str(blender_exe),
                output_blend=str(output_blend),
            )
            project.layers = [
                LayerState(
                    layer_id="building/house",
                    name="House",
                    generation_settings=LayerGenerationSettings(mode="single", single_instances=[]),
                )
            ]
            result = LocalValidationService().validate(project, {})
            self.assertFalse(result.success)
            self.assertTrue(any("single mode" in error for error in result.errors))
