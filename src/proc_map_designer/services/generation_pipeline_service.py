from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from proc_map_designer.domain.project_state import LatestOutputInfo, ProjectState, utc_now_iso
from proc_map_designer.infrastructure.blender_runner import BlenderExecutionError, BlenderRunner
from proc_map_designer.services.export_package_service import ExportPackageService
from proc_map_designer.services.final_export_service import FinalExportService, FinalExportServiceError
from proc_map_designer.services.generation_service import GenerationResult, GenerationService, GenerationServiceError
from proc_map_designer.services.validation_service import ValidationReport, ValidationService, ValidationServiceError

MaskExporter = Callable[[Path, Sequence[str]], dict[str, str]]
LogCallback = Callable[[str], None]
StateCallback = Callable[[str], None]


class GenerationPipelineError(RuntimeError):
    """Raised when a generation pipeline step fails."""


@dataclass(frozen=True, slots=True)
class PipelineBackendInfo:
    backend_id: str
    display_name: str
    supports_final_export: bool = False


class GenerationPipelineService:
    def __init__(
        self,
        export_service: ExportPackageService,
        validation_service: ValidationService,
        generation_service: GenerationService,
        final_export_service: FinalExportService,
        runner: BlenderRunner,
    ) -> None:
        self._export_service = export_service
        self._validation_service = validation_service
        self._generation_service = generation_service
        self._final_export_service = final_export_service
        self._runner = runner
        self._backends = {
            "python_batch": PipelineBackendInfo(
                backend_id="python_batch",
                display_name="Python Batch",
                supports_final_export=True,
            ),
            "geometry_nodes": PipelineBackendInfo(
                backend_id="geometry_nodes",
                display_name="Geometry Nodes",
                supports_final_export=True,
            ),
        }

    def list_backends(self) -> list[PipelineBackendInfo]:
        return [self._backends["python_batch"], self._backends["geometry_nodes"]]

    def supports_final_export(self, backend_id: str) -> bool:
        return self._get_backend(backend_id).supports_final_export

    def validate_project(
        self,
        project: ProjectState,
        package_dir: Path,
        mask_exporter: MaskExporter,
        backend_id: str,
        log: LogCallback | None = None,
        state: StateCallback | None = None,
    ) -> LatestOutputInfo:
        self._get_backend(backend_id)
        if state:
            state("exporting")
        manifest_path = self._export_project(project, package_dir, mask_exporter, log)
        if state:
            state("validating")
        report = self._validate_manifest(manifest_path, log)
        return LatestOutputInfo(
            backend_id=backend_id,
            status="validated",
            export_manifest_path=str(manifest_path),
            result_path="",
            completed_at=utc_now_iso(),
            used_layer_ids=[layer.layer_id for layer in project.layers if layer.generation_settings.enabled],
            validation_warnings=list(report.warnings),
        )

    def generate_project(
        self,
        project: ProjectState,
        package_dir: Path,
        mask_exporter: MaskExporter,
        backend_id: str,
        log: LogCallback | None = None,
        state: StateCallback | None = None,
    ) -> LatestOutputInfo:
        self._get_backend(backend_id)
        if state:
            state("exporting")
        manifest_path = self._export_project(project, package_dir, mask_exporter, log)
        if state:
            state("validating")
        report = self._validate_manifest(manifest_path, log)
        if state:
            state("generating")
        result = self._generate_manifest(manifest_path, backend_id, project, log)
        if result.warnings and log is not None:
            for warning in result.warnings:
                log(f"Warning: {warning}")

        return LatestOutputInfo(
            backend_id=backend_id,
            status="completed",
            export_manifest_path=str(manifest_path),
            result_path=result.output_blend,
            completed_at=utc_now_iso(),
            used_layer_ids=[entry["layer_id"] for entry in result.placed_layers if "layer_id" in entry],
            validation_warnings=list(report.warnings),
        )

    def final_export(
        self,
        latest_output: LatestOutputInfo,
        destination_path: Path,
        log: LogCallback | None = None,
        state: StateCallback | None = None,
    ) -> LatestOutputInfo:
        backend = self._get_backend(latest_output.backend_id)
        if not backend.supports_final_export:
            raise GenerationPipelineError("El backend seleccionado no soporta exportación final adicional.")
        if not latest_output.result_path.strip() or not latest_output.export_manifest_path.strip():
            raise GenerationPipelineError("No hay suficiente información del resultado para exportar el mapa final.")

        if state:
            state("finalizing")

        try:
            result = self._final_export_service.export_final(
                project_json_path=Path(latest_output.export_manifest_path).expanduser(),
                working_blend_path=Path(latest_output.result_path).expanduser(),
                output_blend_path=destination_path.expanduser(),
                log=log,
            )
        except FinalExportServiceError as exc:
            raise GenerationPipelineError(str(exc)) from exc

        if result.warnings and log is not None:
            for warning in result.warnings:
                log(f"Warning: {warning}")

        return LatestOutputInfo(
            backend_id=latest_output.backend_id,
            status="completed",
            export_manifest_path=latest_output.export_manifest_path,
            result_path=latest_output.result_path,
            final_output_path=result.output_blend,
            completed_at=utc_now_iso(),
            used_layer_ids=list(latest_output.used_layer_ids),
            validation_warnings=list(latest_output.validation_warnings),
        )

    def open_result_in_blender(self, result_path: Path) -> None:
        try:
            self._runner.open_blend_interactive(result_path.expanduser())
        except BlenderExecutionError as exc:
            raise GenerationPipelineError(str(exc)) from exc

    def _export_project(
        self,
        project: ProjectState,
        package_dir: Path,
        mask_exporter: MaskExporter,
        log: LogCallback | None = None,
    ) -> Path:
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True, exist_ok=True)
        if log:
            log(f"Exportando paquete intermedio: {package_dir}")
        try:
            manifest_path = self._export_service.export_package(project, package_dir, mask_exporter)
        except Exception as exc:
            raise GenerationPipelineError(str(exc)) from exc
        if log:
            log(f"Manifiesto exportado: {manifest_path}")
        return manifest_path

    def _validate_manifest(self, manifest_path: Path, log: LogCallback | None = None) -> ValidationReport:
        if log:
            log("Validando paquete exportado en Blender headless...")
        try:
            report = self._validation_service.validate_package(manifest_path, log=log)
        except ValidationServiceError as exc:
            raise GenerationPipelineError(str(exc)) from exc
        if log:
            for warning in report.warnings:
                log(f"Warning: {warning}")
        return report

    def _generate_manifest(
        self,
        manifest_path: Path,
        backend_id: str,
        project: ProjectState,
        log: LogCallback | None = None,
    ) -> GenerationResult:
        if log:
            log(f"Ejecutando backend de generación: {backend_id}")
        output_path = Path(project.output_blend).expanduser() if project.output_blend.strip() else None
        try:
            return self._generation_service.generate(
                project_json_path=manifest_path,
                backend_id=backend_id,
                output_blend=output_path,
                log=log,
            )
        except GenerationServiceError as exc:
            raise GenerationPipelineError(str(exc)) from exc

    def _get_backend(self, backend_id: str) -> PipelineBackendInfo:
        backend = self._backends.get(backend_id)
        if backend is None:
            raise GenerationPipelineError(f"Backend no soportado: {backend_id}")
        return backend
