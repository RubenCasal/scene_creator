from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any

from proc_map_designer.infrastructure.blender_runner import BlenderExecutionError, BlenderRunner

LogCallback = Callable[[str], None]


class FinalExportServiceError(RuntimeError):
    """Raised when final blend export fails."""


@dataclass(slots=True)
class FinalExportResult:
    success: bool
    output_blend: str
    warnings: list[str] = field(default_factory=list)
    category_counts: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FinalExportResult":
        return cls(
            success=bool(payload.get("success", False)),
            output_blend=str(payload.get("output_blend", "")),
            warnings=[str(item) for item in payload.get("warnings", [])],
            category_counts=[dict(item) for item in payload.get("category_counts", []) if isinstance(item, dict)],
        )


class FinalExportService:
    def __init__(self, runner: BlenderRunner, script_path: Path) -> None:
        self._runner = runner
        self._script_path = script_path

    def export_final(
        self,
        project_json_path: Path,
        working_blend_path: Path,
        output_blend_path: Path,
        log: LogCallback | None = None,
    ) -> FinalExportResult:
        if not working_blend_path.exists():
            raise FinalExportServiceError(f"No existe el .blend de trabajo: {working_blend_path}")

        try:
            payload = self._runner.run_script_with_blend(
                blend_file=working_blend_path,
                script_path=self._script_path,
                script_args=["--project", str(project_json_path), "--output", str(output_blend_path)],
                log_callback=log,
            )
        except BlenderExecutionError as exc:
            raise FinalExportServiceError(str(exc)) from exc

        result = FinalExportResult.from_payload(payload)
        if not result.success:
            raise FinalExportServiceError(str(payload.get("error", "La exportación final falló.")))
        return result
