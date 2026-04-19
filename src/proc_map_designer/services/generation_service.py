from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any

from proc_map_designer.blender_bridge.package_loader import load_export_package
from proc_map_designer.infrastructure.blender_runner import BlenderExecutionError, BlenderRunner

LogCallback = Callable[[str], None]


class GenerationServiceError(RuntimeError):
    """Raised when map generation fails."""


@dataclass(slots=True)
class GenerationResult:
    success: bool
    backend: str
    output_blend: str
    warnings: list[str] = field(default_factory=list)
    placed_layers: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "GenerationResult":
        return cls(
            success=bool(payload.get("success", False)),
            backend=str(payload.get("backend", "")),
            output_blend=str(payload.get("output_blend", "")),
            warnings=[str(item) for item in payload.get("warnings", [])],
            placed_layers=[dict(item) for item in payload.get("placed_layers", []) if isinstance(item, dict)],
        )


class GenerationService:
    def __init__(self, runner: BlenderRunner, python_batch_script: Path, geometry_nodes_script: Path) -> None:
        self._runner = runner
        self._script_by_backend = {
            "python_batch": python_batch_script,
            "geometry_nodes": geometry_nodes_script,
        }

    def generate(
        self,
        project_json_path: Path,
        backend_id: str,
        output_blend: Path | None,
        log: LogCallback | None = None,
    ) -> GenerationResult:
        script_path = self._script_by_backend.get(backend_id)
        if script_path is None:
            raise GenerationServiceError(f"Backend no soportado: {backend_id}")

        try:
            package = load_export_package(project_json_path, require_mask_files=True)
            blend_file = Path(package.source_blend).expanduser().resolve()
            if not blend_file.exists():
                raise GenerationServiceError(f"El .blend fuente no existe: {blend_file}")
            has_enabled_layers = any(layer.enabled for layer in package.layers)
            has_enabled_roads = any(road.visible for road in package.roads)
            has_enabled_terrain = bool(package.map.terrain.enabled and package.map.terrain.heightfield_exists)
            if not has_enabled_layers and not has_enabled_roads and not has_enabled_terrain:
                raise GenerationServiceError(
                    "No hay contenido habilitado para generar. Activa al menos una capa, una road visible o el terrain sculpt."
                )

            resolved_output = self._resolve_output_path(
                requested_output=output_blend,
                package_output=Path(package.output_blend).expanduser(),
            )

            args = ["--project", str(project_json_path)]
            args.extend(["--output", str(resolved_output)])
            if log is not None:
                log(f"Ruta de salida normalizada: {resolved_output}")

            payload = self._runner.run_script_with_blend(
                blend_file=blend_file,
                script_path=script_path,
                script_args=args,
                log_callback=log,
            )
        except (ValueError, BlenderExecutionError) as exc:
            raise GenerationServiceError(str(exc)) from exc

        result = GenerationResult.from_payload(payload)
        if not result.success:
            raise GenerationServiceError(str(payload.get("error", "La generación falló.")))
        return result

    def _resolve_output_path(self, requested_output: Path | None, package_output: Path) -> Path:
        candidate = (requested_output or package_output).expanduser()

        if candidate.exists() and candidate.is_dir():
            return (candidate / "working_map.blend").resolve()

        if candidate.suffix.lower() == ".blend":
            return candidate.resolve()

        if candidate.exists() and candidate.is_file():
            return candidate.with_suffix(".blend").resolve()

        if candidate.suffix:
            return candidate.resolve()

        return candidate.with_suffix(".blend").resolve()
