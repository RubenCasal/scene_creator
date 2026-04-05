from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any

from proc_map_designer.blender_bridge.package_loader import load_export_package
from proc_map_designer.infrastructure.blender_runner import BlenderExecutionError, BlenderRunner

LogCallback = Callable[[str], None]


class ValidationServiceError(RuntimeError):
    """Raised when exported-package validation fails."""


@dataclass(slots=True)
class ValidationReport:
    success: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    resolved_collections: list[dict[str, Any]] = field(default_factory=list)
    resolved_base_plane: dict[str, Any] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ValidationReport":
        return cls(
            success=bool(payload.get("success", False)),
            errors=[str(item) for item in payload.get("errors", [])],
            warnings=[str(item) for item in payload.get("warnings", [])],
            resolved_collections=[dict(item) for item in payload.get("resolved_collections", []) if isinstance(item, dict)],
            resolved_base_plane=(
                dict(payload["resolved_base_plane"])
                if isinstance(payload.get("resolved_base_plane"), dict)
                else None
            ),
        )


class ValidationService:
    def __init__(self, runner: BlenderRunner, script_path: Path) -> None:
        self._runner = runner
        self._script_path = script_path

    def validate_package(
        self,
        project_json_path: Path,
        log: LogCallback | None = None,
    ) -> ValidationReport:
        try:
            package = load_export_package(project_json_path, require_mask_files=True)
            blend_file = Path(package.source_blend).expanduser().resolve()
            if not blend_file.exists():
                raise ValidationServiceError(f"El .blend fuente no existe: {blend_file}")

            payload = self._runner.run_script_with_blend(
                blend_file=blend_file,
                script_path=self._script_path,
                script_args=["--project", str(project_json_path)],
                log_callback=log,
            )
        except (ValueError, BlenderExecutionError) as exc:
            raise ValidationServiceError(str(exc)) from exc

        report = ValidationReport.from_payload(payload)
        if not report.success:
            detail = "; ".join(report.errors) if report.errors else "Validación fallida sin detalles."
            raise ValidationServiceError(detail)
        return report
