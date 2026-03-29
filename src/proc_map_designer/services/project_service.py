from __future__ import annotations

from pathlib import Path

from proc_map_designer.domain.project_state import PROJECT_SCHEMA_VERSION, ProjectState
from proc_map_designer.infrastructure.project_repository import ProjectRepository, ProjectRepositoryError


class ProjectServiceError(RuntimeError):
    """Raised when a project cannot be loaded or saved."""


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def create_new_project(
        self,
        project_name: str = "Nuevo proyecto",
        source_blend: str = "",
        blender_executable: str = "",
    ) -> ProjectState:
        return ProjectState.create_new(
            project_name=project_name,
            source_blend=source_blend,
            blender_executable=blender_executable,
        )

    def load_project(self, file_path: Path) -> ProjectState:
        try:
            payload = self._repository.load_json(file_path)
            return ProjectState.from_dict(payload)
        except ProjectRepositoryError as exc:
            raise ProjectServiceError(str(exc)) from exc
        except ValueError as exc:
            raise ProjectServiceError(f"Proyecto inválido: {exc}") from exc

    def save_project(self, project: ProjectState, file_path: Path) -> None:
        try:
            project.schema_version = PROJECT_SCHEMA_VERSION
            project.touch()
            if not project.project_name.strip():
                project.project_name = file_path.stem
            self._repository.save_json(file_path, project.to_dict())
        except ProjectRepositoryError as exc:
            raise ProjectServiceError(str(exc)) from exc

