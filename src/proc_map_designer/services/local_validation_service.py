from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from proc_map_designer.domain.project_state import ProjectState


@dataclass(slots=True)
class LocalValidationResult:
    success: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class LocalValidationService:
    def validate(
        self,
        project_state: ProjectState,
        mask_snapshots: Mapping[str, object],
    ) -> LocalValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if not project_state.project_id:
            errors.append("Project ID is not set.")
        if not project_state.source_blend:
            errors.append("No source .blend file selected.")
        elif not Path(project_state.source_blend).is_file():
            errors.append(f"Source .blend not found: {project_state.source_blend}")

        if not project_state.output_blend:
            errors.append("No output path set.")
        else:
            output_dir = Path(project_state.output_blend).expanduser().parent
            if not output_dir.exists():
                errors.append(f"Output directory does not exist: {output_dir}")

        blender_executable = Path(project_state.blender_executable or "")
        if not blender_executable.is_file():
            errors.append(f"Blender executable not found: {blender_executable}")

        enabled_layers = [layer for layer in project_state.layers if layer.generation_settings.enabled]
        if not enabled_layers and not any(road.visible for road in project_state.roads) and not project_state.terrain_settings.enabled:
            warnings.append("No enabled layers, visible roads, or terrain sculpt content were found.")

        for layer in enabled_layers:
            if not layer.layer_id:
                errors.append(f"Layer '{layer.name or layer.layer_id}' has no collection ID set.")
                continue
            if layer.generation_settings.mode == "procedural":
                if layer.layer_id not in mask_snapshots:
                    warnings.append(f"Layer '{layer.name or layer.layer_id}' has no painted mask snapshot.")
            elif layer.generation_settings.mode == "single":
                if not layer.generation_settings.single_instances:
                    errors.append(f"Layer '{layer.name or layer.layer_id}' is in single mode but has no placements.")

        ms = project_state.map_settings
        if ms.logical_width <= 0 or ms.logical_height <= 0:
            errors.append("Map dimensions must be positive.")
        if ms.mask_width < 64 or ms.mask_height < 64:
            warnings.append("Mask resolution is very low (< 64 px). Object placement may be inaccurate.")

        return LocalValidationResult(success=not errors, errors=errors, warnings=warnings)
