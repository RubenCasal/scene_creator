from __future__ import annotations

from pathlib import Path

from proc_map_designer.domain.models import BlendInspectionResult
from proc_map_designer.infrastructure.blender_runner import BlenderExecutionError, BlenderRunner


class BlendInspectionError(RuntimeError):
    """Raised when a blend inspection cannot be completed."""


class BlendInspectionService:
    def __init__(self, runner: BlenderRunner, script_path: Path) -> None:
        self._runner = runner
        self._script_path = script_path

    def inspect(self, blend_file: Path) -> BlendInspectionResult:
        if blend_file.suffix.lower() != ".blend":
            raise BlendInspectionError("El archivo seleccionado no tiene extensión .blend.")

        try:
            payload = self._runner.run_script_for_blend(
                blend_file=blend_file,
                script_path=self._script_path,
            )
            return BlendInspectionResult.from_dict(payload)
        except BlenderExecutionError as exc:
            raise BlendInspectionError(str(exc)) from exc
        except ValueError as exc:
            raise BlendInspectionError(f"Respuesta inválida desde Blender: {exc}") from exc

