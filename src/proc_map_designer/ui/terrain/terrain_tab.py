from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from proc_map_designer.domain.terrain_state import TerrainSettings
from proc_map_designer.services.terrain_service import TerrainService
from proc_map_designer.ui.terrain.terrain_settings_panel import TerrainSettingsPanel
from proc_map_designer.ui.terrain.terrain_toolbar import TerrainToolbar
from proc_map_designer.ui.terrain.terrain_viewport import TerrainViewport


class TerrainTab(QWidget):
    terrain_state_changed = Signal(object)

    def __init__(self, terrain_settings: TerrainSettings, map_width: float, map_height: float, project_dir: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_dir = Path(project_dir) if project_dir else None
        self._service = TerrainService(terrain_settings)
        self._toolbar = TerrainToolbar()
        self._viewport = TerrainViewport(self._service, map_width, map_height)
        self._settings_panel = TerrainSettingsPanel()
        self._settings_panel.populate_from_settings(terrain_settings)
        layout = QHBoxLayout(self)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._viewport, stretch=1)
        layout.addWidget(self._settings_panel)
        self._wire()
        self._load_initial_heightfield()

    @property
    def terrain_service(self) -> TerrainService:
        return self._service

    def save_heightfield(self) -> None:
        path = self._resolve_heightfield_path()
        self._service.save_to_path(path)
        self._service.settings.heightfield_path = str(path.resolve())
        self._service.settings.enabled = True
        self._settings_panel.populate_from_settings(self._service.settings)
        self.terrain_state_changed.emit(self._service.settings)

    def set_project_dir(self, project_dir: str) -> None:
        self._project_dir = Path(project_dir) if project_dir else None

    def set_map_dimensions(self, map_width: float, map_height: float) -> None:
        self._viewport._map_width = map_width
        self._viewport._map_height = map_height
        self._viewport._camera.frame_terrain(map_width, map_height, self._service.settings.max_height)
        self._viewport.update()

    def set_terrain_settings(self, settings: TerrainSettings) -> None:
        self._service.update_settings(settings)
        self._settings_panel.populate_from_settings(settings)
        path = self._resolve_existing_heightfield_path(settings.heightfield_path)
        if path is not None:
            try:
                self._service.load_from_path(path)
            except Exception:
                pass
        self._viewport.refresh_heightfield()

    def _wire(self) -> None:
        self._toolbar.tool_changed.connect(self._viewport.set_tool)
        self._toolbar.radius_changed.connect(self._viewport.set_brush_radius)
        self._toolbar.strength_changed.connect(self._viewport.set_brush_strength)
        self._toolbar.falloff_changed.connect(self._viewport.set_falloff)
        self._toolbar.undo_requested.connect(self._undo)
        self._toolbar.redo_requested.connect(self._redo)
        self._toolbar.reset_requested.connect(self._reset)
        self._settings_panel.settings_changed.connect(self._on_settings_changed)
        self._settings_panel.apply_noise_requested.connect(self._apply_noise)
        self._settings_panel.save_heightfield_requested.connect(self.save_heightfield)
        self._viewport.heightfield_modified.connect(self._on_heightfield_modified)

    def _load_initial_heightfield(self) -> None:
        path = self._service.settings.heightfield_path
        if path and Path(path).exists():
            try:
                self._service.load_from_path(path)
                self._viewport.refresh_heightfield()
            except Exception:
                pass

    def _on_settings_changed(self, settings: TerrainSettings) -> None:
        settings.heightfield_path = self._service.settings.heightfield_path
        self._service.update_settings(settings)
        self.terrain_state_changed.emit(self._service.settings)
        self._viewport.refresh_heightfield()

    def _apply_noise(self) -> None:
        self._service.apply_base_noise()
        self._viewport.refresh_heightfield()
        self._on_heightfield_modified()

    def _on_heightfield_modified(self) -> None:
        path = self._resolve_heightfield_path()
        self._service.settings.heightfield_path = self._serialize_heightfield_path(path)
        self.terrain_state_changed.emit(self._service.settings)

    def _undo(self) -> None:
        if self._service.undo():
            self._viewport.refresh_heightfield()
            self._on_heightfield_modified()

    def _redo(self) -> None:
        if self._service.redo():
            self._viewport.refresh_heightfield()
            self._on_heightfield_modified()

    def _reset(self) -> None:
        self._service.reset_flat()
        self._viewport.refresh_heightfield()
        self._on_heightfield_modified()

    def _resolve_heightfield_path(self) -> Path:
        if self._project_dir is not None:
            return self._project_dir / "terrain" / "heightfield.png"
        return Path.cwd() / "terrain" / "heightfield.png"

    def _resolve_existing_heightfield_path(self, raw_path: str) -> Path | None:
        if not raw_path:
            return None
        candidate = Path(raw_path)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        if self._project_dir is not None:
            project_relative = (self._project_dir / candidate).resolve()
            if project_relative.exists():
                return project_relative
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
        return None

    def _serialize_heightfield_path(self, path: Path) -> str:
        return str(path.resolve())
