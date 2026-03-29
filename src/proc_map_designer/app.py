from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from proc_map_designer.infrastructure.blender_runner import BlenderRunner
from proc_map_designer.infrastructure.project_repository import ProjectRepository
from proc_map_designer.infrastructure.settings import AppSettings
from proc_map_designer.services.inspection_service import BlendInspectionService
from proc_map_designer.services.project_service import ProjectService
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
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "inspect_blend_collections.py"
    service = BlendInspectionService(runner=runner, script_path=script_path)

    window = MainWindow(
        inspection_service=service,
        project_service=project_service,
        settings=settings,
    )
    window.show()
    return app.exec()
