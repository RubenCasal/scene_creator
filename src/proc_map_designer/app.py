from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from proc_map_designer.infrastructure.blender_runner import BlenderRunner
from proc_map_designer.infrastructure.project_repository import ProjectRepository
from proc_map_designer.infrastructure.settings import AppSettings
from proc_map_designer.services.export_package_service import ExportPackageService
from proc_map_designer.services.final_export_service import FinalExportService
from proc_map_designer.services.generation_service import GenerationService
from proc_map_designer.services.generation_pipeline_service import GenerationPipelineService
from proc_map_designer.services.inspection_service import BlendInspectionService
from proc_map_designer.services.project_service import ProjectService
from proc_map_designer.services.validation_service import ValidationService
from proc_map_designer.ui.main_window import MainWindow


def run_app() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    QCoreApplication.setOrganizationName("SceneGenerator")
    QCoreApplication.setApplicationName("ProceduralMapDesigner")

    app = QApplication(sys.argv)
    settings = AppSettings()
    runner = BlenderRunner(settings=settings)
    project_service = ProjectService(ProjectRepository())
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    inspection_script_path = scripts_dir / "inspect_blend_collections.py"
    validation_script_path = scripts_dir / "blender_validate_project.py"
    python_batch_script_path = scripts_dir / "blender_generate_python_batch.py"
    geometry_nodes_script_path = scripts_dir / "blender_generate_geometry_nodes.py"
    final_export_script_path = scripts_dir / "blender_export_final_map.py"

    inspection_service = BlendInspectionService(runner=runner, script_path=inspection_script_path)
    validation_service = ValidationService(runner=runner, script_path=validation_script_path)
    generation_service = GenerationService(
        runner=runner,
        python_batch_script=python_batch_script_path,
        geometry_nodes_script=geometry_nodes_script_path,
    )
    final_export_service = FinalExportService(runner=runner, script_path=final_export_script_path)
    pipeline_service = GenerationPipelineService(
        export_service=ExportPackageService(),
        validation_service=validation_service,
        generation_service=generation_service,
        final_export_service=final_export_service,
        runner=runner,
    )

    window = MainWindow(
        inspection_service=inspection_service,
        project_service=project_service,
        pipeline_service=pipeline_service,
        settings=settings,
    )
    window.show()
    return app.exec()
