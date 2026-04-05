from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Callable, Mapping, Sequence

from proc_map_designer.domain.export_package import ExportLayer, ExportLayerSettings, ExportMap, ExportProject
from proc_map_designer.domain.layer_palette import split_layer_id
from proc_map_designer.domain.project_state import LayerState, ProjectState

MaskExporter = Callable[[Path, Sequence[str]], Mapping[str, str]]


class ExportPackageError(RuntimeError):
    """Raised when an export package cannot be created."""


class ExportPackageService:
    def export_package(
        self,
        project: ProjectState,
        package_dir: Path,
        mask_exporter: MaskExporter,
    ) -> Path:
        self._validate_required_project_fields(project)
        package_dir.mkdir(parents=True, exist_ok=True)

        layer_ids = [layer.layer_id for layer in project.layers]
        try:
            mask_paths = mask_exporter(package_dir, layer_ids)
        except ExportPackageError:
            raise
        except Exception as exc:
            raise ExportPackageError(f"Error al exportar máscaras: {exc}") from exc

        manifest = self._build_manifest(project, package_dir, mask_paths)
        project_json = package_dir / "project.json"

        try:
            project_json.write_text(
                json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise ExportPackageError(f"No se pudo escribir project.json: {exc}") from exc

        return project_json

    def _validate_required_project_fields(self, project: ProjectState) -> None:
        missing: list[str] = []
        if not project.project_id.strip():
            missing.append("project_id")
        if not project.source_blend.strip():
            missing.append("source_blend")
        if not project.blender_executable.strip():
            missing.append("blender_executable")
        if not project.output_blend.strip():
            missing.append("output_blend")
        if not project.map_settings.base_plane_object.strip():
            missing.append("map_settings.base_plane_object")

        if missing:
            fields = ", ".join(missing)
            raise ExportPackageError(f"No se puede exportar. Faltan campos requeridos: {fields}.")

    def _build_manifest(
        self,
        project: ProjectState,
        package_dir: Path,
        mask_paths: Mapping[str, str],
    ) -> ExportProject:
        map_payload = ExportMap(
            width=project.map_settings.logical_width,
            height=project.map_settings.logical_height,
            unit=project.map_settings.logical_unit,
            mask_resolution={
                "width": project.map_settings.mask_width,
                "height": project.map_settings.mask_height,
            },
            base_plane_object=project.map_settings.base_plane_object,
        )

        layers_payload: list[ExportLayer] = []
        for layer in project.layers:
            mask_path = self._resolve_and_validate_mask_path(
                package_dir=package_dir,
                layer_state=layer,
                mask_paths=mask_paths,
            )
            category, _ = split_layer_id(layer.layer_id)
            layer_seed = self._resolve_layer_seed(project, layer)
            settings = layer.generation_settings

            layers_payload.append(
                ExportLayer(
                    category=category,
                    name=layer.name or layer.layer_id,
                    blender_collection=layer.layer_id,
                    enabled=settings.enabled,
                    mask_path=mask_path,
                    settings=ExportLayerSettings(
                        density=settings.density,
                        min_distance=settings.min_distance,
                        allow_overlap=settings.allow_overlap,
                        scale_min=settings.scale_min,
                        scale_max=settings.scale_max,
                        rotation_random_z=settings.rotation_random_z,
                        seed=layer_seed,
                        priority=settings.priority,
                    ),
                )
            )

        return ExportProject(
            project_id=project.project_id,
            source_blend=project.source_blend,
            blender_executable=project.blender_executable,
            output_blend=project.output_blend,
            map=map_payload,
            layers=layers_payload,
        )

    def _resolve_layer_seed(self, project: ProjectState, layer: LayerState) -> int:
        if layer.generation_settings.seed is not None:
            return layer.generation_settings.seed
        if project.generation_settings.seed is not None:
            return project.generation_settings.seed
        if project.generation_settings.randomize_seed:
            seed_text = f"{project.project_id}:{layer.layer_id}:default"
            digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
            return int.from_bytes(digest[:4], byteorder="big", signed=False)
        return 0

    def _resolve_and_validate_mask_path(
        self,
        package_dir: Path,
        layer_state: LayerState,
        mask_paths: Mapping[str, str],
    ) -> str:
        path_text = str(mask_paths.get(layer_state.layer_id, "")).strip()
        if not path_text:
            raise ExportPackageError(
                f"No se pudo exportar la máscara de la capa '{layer_state.layer_id}'."
            )

        relative_path = Path(path_text)
        if relative_path.is_absolute():
            try:
                relative_path = relative_path.relative_to(package_dir)
            except ValueError as exc:
                raise ExportPackageError(
                    f"La máscara de '{layer_state.layer_id}' quedó fuera del paquete: {path_text}"
                ) from exc

        normalized = relative_path.as_posix()
        if not normalized.startswith("masks/"):
            raise ExportPackageError(
                f"La máscara de '{layer_state.layer_id}' debe guardarse bajo 'masks/': {normalized}"
            )

        absolute_path = package_dir / relative_path
        if not absolute_path.exists():
            raise ExportPackageError(
                f"Archivo de máscara no encontrado para '{layer_state.layer_id}': {absolute_path}"
            )

        return normalized
