from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSplitter,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from proc_map_designer.domain.models import BlendInspectionResult
from proc_map_designer.domain.project_state import ProjectState
from proc_map_designer.infrastructure.settings import AppSettings
from proc_map_designer.services.inspection_service import BlendInspectionError, BlendInspectionService
from proc_map_designer.services.project_service import ProjectService, ProjectServiceError
from proc_map_designer.ui.canvas.brush_tool import BrushTool
from proc_map_designer.ui.canvas.canvas_view import CanvasView
from proc_map_designer.ui.canvas.layer_mask_manager import LayerMaskManager
from proc_map_designer.ui.map_settings_dialog import MapSettingsDialog

EXPECTED_ROOTS = {"vegetation", "building"}


@dataclass(slots=True)
class LoadState:
    is_busy: bool = False


class InspectionWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, service: BlendInspectionService, blend_file: Path) -> None:
        super().__init__()
        self._service = service
        self._blend_file = blend_file

    @Slot()
    def run(self) -> None:
        self.log.emit(f"Inspeccionando: {self._blend_file}")
        try:
            result = self._service.inspect(self._blend_file)
        except BlendInspectionError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"Error inesperado: {exc}")
            return
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(
        self,
        inspection_service: BlendInspectionService,
        project_service: ProjectService,
        settings: AppSettings,
    ) -> None:
        super().__init__()
        self._inspection_service = inspection_service
        self._project_service = project_service
        self._settings = settings
        self._load_state = LoadState()
        self._active_thread: QThread | None = None
        self._active_worker: InspectionWorker | None = None
        self._current_blend: Path | None = None
        self._project_state: ProjectState = self._project_service.create_new_project(
            blender_executable=self._settings.get_blender_executable() or ""
        )
        self._project_file_path: Path | None = None

        self._brush_tool = BrushTool(radius_px=24, intensity=0.75, mode="paint")
        self._layer_manager = LayerMaskManager(self._project_state.map_settings)
        self._active_layer_id: str | None = None
        self._updating_layer_tree = False

        self.setWindowTitle("Procedural Map Designer")
        self.resize(1380, 860)
        self._build_actions()
        self._build_menu_and_toolbar()
        self._build_ui()
        self._wire_canvas()
        self._apply_project_to_ui()
        self._append_log("Proyecto nuevo inicializado.")

    def _build_actions(self) -> None:
        self.action_new_project = QAction("Nuevo proyecto", self)
        self.action_new_project.triggered.connect(self._new_project)

        self.action_open_project = QAction("Abrir proyecto", self)
        self.action_open_project.triggered.connect(self._open_project)

        self.action_save_project = QAction("Guardar proyecto", self)
        self.action_save_project.triggered.connect(self._save_project)

        self.action_save_project_as = QAction("Guardar como...", self)
        self.action_save_project_as.triggered.connect(self._save_project_as)

        self.action_configure_map = QAction("Configurar mapa", self)
        self.action_configure_map.triggered.connect(self._configure_map)

    def _build_menu_and_toolbar(self) -> None:
        project_menu = self.menuBar().addMenu("Proyecto")
        project_menu.addAction(self.action_new_project)
        project_menu.addAction(self.action_open_project)
        project_menu.addSeparator()
        project_menu.addAction(self.action_save_project)
        project_menu.addAction(self.action_save_project_as)
        project_menu.addSeparator()
        project_menu.addAction(self.action_configure_map)

        toolbar = QToolBar("Proyecto", self)
        toolbar.setMovable(False)
        toolbar.addAction(self.action_new_project)
        toolbar.addAction(self.action_open_project)
        toolbar.addAction(self.action_save_project)
        toolbar.addAction(self.action_save_project_as)
        toolbar.addSeparator()
        toolbar.addAction(self.action_configure_map)
        self.addToolBar(toolbar)

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        controls_layout = QHBoxLayout()
        self.select_blend_button = QPushButton("Seleccionar .blend")
        self.select_blend_button.clicked.connect(self._on_select_blend)
        controls_layout.addWidget(self.select_blend_button)

        self.configure_blender_button = QPushButton("Configurar Blender")
        self.configure_blender_button.clicked.connect(self._on_configure_blender)
        controls_layout.addWidget(self.configure_blender_button)
        controls_layout.addStretch(1)
        root_layout.addLayout(controls_layout)

        self.project_label = QLabel("Proyecto: sin guardar")
        self.project_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root_layout.addWidget(self.project_label)

        self.blend_file_label = QLabel("Blend fuente: ninguno")
        self.blend_file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root_layout.addWidget(self.blend_file_label)

        self.blender_path_label = QLabel()
        root_layout.addWidget(self.blender_path_label)

        self.map_summary_label = QLabel()
        root_layout.addWidget(self.map_summary_label)

        splitter = QSplitter()
        root_layout.addWidget(splitter, stretch=1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        layer_title = QLabel("Capas pintables (subcollections)")
        layer_font = QFont()
        layer_font.setBold(True)
        layer_title.setFont(layer_font)
        left_layout.addWidget(layer_title)

        self.layer_tree = QTreeWidget()
        self.layer_tree.setHeaderLabels(["Layer"])
        self.layer_tree.setAlternatingRowColors(True)
        self.layer_tree.itemChanged.connect(self._on_layer_item_changed)
        self.layer_tree.itemSelectionChanged.connect(self._on_layer_selection_changed)
        left_layout.addWidget(self.layer_tree, stretch=1)

        self.active_layer_label = QLabel("Capa activa: ninguna")
        left_layout.addWidget(self.active_layer_label)

        self.brush_size_label = QLabel(f"Tamaño pincel: {self._brush_tool.radius_px}px")
        left_layout.addWidget(self.brush_size_label)
        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setRange(1, 256)
        self.brush_size_slider.setValue(self._brush_tool.radius_px)
        self.brush_size_slider.valueChanged.connect(self._on_brush_size_changed)
        left_layout.addWidget(self.brush_size_slider)

        self.brush_intensity_label = QLabel(f"Intensidad: {int(self._brush_tool.intensity * 100)}%")
        left_layout.addWidget(self.brush_intensity_label)
        self.brush_intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_intensity_slider.setRange(1, 100)
        self.brush_intensity_slider.setValue(int(self._brush_tool.intensity * 100))
        self.brush_intensity_slider.valueChanged.connect(self._on_brush_intensity_changed)
        left_layout.addWidget(self.brush_intensity_slider)

        mode_layout = QHBoxLayout()
        self.paint_mode_button = QPushButton("Pintar")
        self.paint_mode_button.setCheckable(True)
        self.paint_mode_button.setChecked(True)
        self.paint_mode_button.clicked.connect(lambda: self._set_brush_mode("paint"))
        mode_layout.addWidget(self.paint_mode_button)

        self.erase_mode_button = QPushButton("Borrar")
        self.erase_mode_button.setCheckable(True)
        self.erase_mode_button.setChecked(False)
        self.erase_mode_button.clicked.connect(lambda: self._set_brush_mode("erase"))
        mode_layout.addWidget(self.erase_mode_button)
        left_layout.addLayout(mode_layout)

        self.clear_layer_button = QPushButton("Limpiar capa activa")
        self.clear_layer_button.clicked.connect(self._clear_active_layer)
        left_layout.addWidget(self.clear_layer_button)

        splitter.addWidget(left_panel)

        self.canvas_view = CanvasView()
        splitter.addWidget(self.canvas_view)
        splitter.setSizes([410, 970])

        self.log_panel = QPlainTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumBlockCount(700)
        self.log_panel.setPlaceholderText("Logs básicos de ejecución...")
        self.log_panel.setFixedHeight(180)
        root_layout.addWidget(self.log_panel)

        self.statusBar().showMessage("Listo.")

    def _wire_canvas(self) -> None:
        self.canvas_view.set_brush_tool(self._brush_tool)
        self.canvas_view.set_mask_manager(self._layer_manager)
        self.canvas_view.set_map_settings(self._project_state.map_settings)
        self.canvas_view.mask_modified.connect(self._on_mask_modified)

    def _new_project(self) -> None:
        if self._load_state.is_busy:
            QMessageBox.information(self, "Inspección en curso", "Espera a que termine la inspección actual.")
            return

        blender_exec = self._settings.get_blender_executable() or ""
        self._project_state = self._project_service.create_new_project(blender_executable=blender_exec)
        self._project_file_path = None
        self._current_blend = None
        self._active_layer_id = None
        self._rebuild_layer_manager(project_dir=None)
        self._apply_project_to_ui()
        self._append_log("Proyecto nuevo creado.")

    def _open_project(self) -> None:
        if self._load_state.is_busy:
            QMessageBox.information(self, "Inspección en curso", "Espera a que termine la inspección actual.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto",
            str(Path.home()),
            "Project JSON (*.json)",
        )
        if not file_path:
            return

        project_path = Path(file_path)
        try:
            project_state = self._project_service.load_project(project_path)
        except ProjectServiceError as exc:
            QMessageBox.critical(self, "Error al abrir proyecto", str(exc))
            self._append_log(f"ERROR al abrir proyecto: {exc}")
            return

        self._project_state = project_state
        self._project_file_path = project_path
        self._current_blend = Path(project_state.source_blend) if project_state.source_blend else None
        self._active_layer_id = None

        if project_state.blender_executable:
            self._settings.set_blender_executable(project_state.blender_executable)

        self._rebuild_layer_manager(project_dir=project_path.parent)
        self._apply_project_to_ui()
        self.statusBar().showMessage("Proyecto cargado.")
        self._append_log(f"Proyecto abierto: {project_path}")

    def _save_project(self) -> None:
        if self._project_file_path is None:
            self._save_project_as()
            return
        self._persist_project(self._project_file_path)

    def _save_project_as(self) -> None:
        suggested = self._project_file_path or (Path.home() / "procedural_project.json")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar proyecto como",
            str(suggested),
            "Project JSON (*.json)",
        )
        if not file_path:
            return

        project_path = Path(file_path)
        if project_path.suffix.lower() != ".json":
            project_path = project_path.with_suffix(".json")
        self._persist_project(project_path)

    def _persist_project(self, project_path: Path) -> None:
        self._sync_project_runtime_data()
        try:
            self._project_state.layers = self._layer_manager.to_layer_states(project_path.parent)
            self._project_service.save_project(self._project_state, project_path)
        except (ProjectServiceError, RuntimeError) as exc:
            QMessageBox.critical(self, "Error al guardar proyecto", str(exc))
            self._append_log(f"ERROR al guardar proyecto: {exc}")
            return

        self._project_file_path = project_path
        self._apply_project_to_ui()
        self.statusBar().showMessage("Proyecto guardado.")
        self._append_log(f"Proyecto guardado: {project_path}")

    def _configure_map(self) -> None:
        dialog = MapSettingsDialog(self._project_state.map_settings, self)
        if dialog.exec() != MapSettingsDialog.DialogCode.Accepted:
            return

        self._project_state.map_settings = dialog.result_settings()
        self._project_state.touch()
        self._layer_manager.set_map_settings(self._project_state.map_settings)
        self.canvas_view.set_map_settings(self._project_state.map_settings)
        self.canvas_view.refresh_overlay()
        self._refresh_map_summary_label()
        self._append_log(
            "Mapa configurado: "
            f"{self._project_state.map_settings.logical_width:.2f} x "
            f"{self._project_state.map_settings.logical_height:.2f} "
            f"{self._project_state.map_settings.logical_unit} | "
            f"raster {self._project_state.map_settings.mask_width}x"
            f"{self._project_state.map_settings.mask_height}"
        )

    def _on_select_blend(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo .blend",
            str(Path.home()),
            "Blender Files (*.blend)",
        )
        if not file_path:
            return

        self._current_blend = Path(file_path)
        self._project_state.source_blend = str(self._current_blend)
        self._refresh_blend_label()
        self._start_inspection(self._current_blend)

    def _on_configure_blender(self) -> None:
        blender_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar ejecutable de Blender",
            str(Path.home()),
            "All Files (*)",
        )
        if not blender_path:
            return

        self._settings.set_blender_executable(blender_path)
        self._project_state.blender_executable = blender_path
        self._project_state.touch()
        self._refresh_blender_path_label()
        self._append_log(f"Ruta de Blender guardada: {blender_path}")

    def _start_inspection(self, blend_file: Path) -> None:
        if self._load_state.is_busy:
            self._append_log("Ya hay una inspección en curso. Espera a que finalice.")
            return

        self._set_loading_state(True)
        self._append_log(f"Iniciando inspección de {blend_file}")

        thread = QThread(self)
        worker = InspectionWorker(self._inspection_service, blend_file)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._on_inspection_success)
        worker.failed.connect(self._on_inspection_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)

        self._active_thread = thread
        self._active_worker = worker
        thread.start()

    def _on_thread_finished(self) -> None:
        self._set_loading_state(False)
        self._active_thread = None
        self._active_worker = None
        if self.statusBar().currentMessage() == "Inspeccionando .blend...":
            self.statusBar().showMessage("Listo.")

    def _on_inspection_success(self, result: BlendInspectionResult) -> None:
        self._append_log(
            f"Inspección completada: {result.total_collections} collections encontradas."
        )
        for warning in result.warnings:
            self._append_log(f"Warning: {warning}")

        self._project_state.collection_tree = result.roots
        self._project_state.source_blend = result.blend_file
        self._project_state.blender_executable = self._settings.get_blender_executable() or ""
        self._project_state.touch()

        self._layer_manager.sync_from_collection_tree(result.roots)
        self._refresh_layer_tree()
        self.canvas_view.refresh_overlay()
        self._refresh_blend_label()

        if not result.roots:
            self.statusBar().showMessage("No se encontraron collections útiles en el .blend.")
            self._append_log("No se detectaron collections raíz para crear capas.")
            return

        missing_roots = result.missing_expected_roots(EXPECTED_ROOTS)
        if missing_roots:
            self._append_log(
                "Collections principales esperadas no encontradas: "
                + ", ".join(sorted(missing_roots))
            )
        else:
            self._append_log("Se encontraron collections principales esperadas: vegetation, building.")

        if self._active_layer_id is None:
            self._select_first_layer()

        self.statusBar().showMessage("Inspección finalizada correctamente.")

    def _on_inspection_failed(self, message: str) -> None:
        self.statusBar().showMessage("Error durante la inspección del archivo.")
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Error al inspeccionar .blend", message)

    def _set_loading_state(self, is_busy: bool) -> None:
        self._load_state.is_busy = is_busy
        self.select_blend_button.setEnabled(not is_busy)
        self.configure_blender_button.setEnabled(not is_busy)
        self.action_new_project.setEnabled(not is_busy)
        self.action_open_project.setEnabled(not is_busy)
        self.action_configure_map.setEnabled(not is_busy)
        if is_busy:
            self.statusBar().showMessage("Inspeccionando .blend...")

    def _refresh_project_label(self) -> None:
        if self._project_file_path:
            self.project_label.setText(f"Proyecto: {self._project_file_path}")
        else:
            self.project_label.setText("Proyecto: sin guardar")

    def _refresh_blend_label(self) -> None:
        if self._project_state.source_blend:
            self.blend_file_label.setText(f"Blend fuente: {self._project_state.source_blend}")
        else:
            self.blend_file_label.setText("Blend fuente: ninguno")

    def _refresh_blender_path_label(self) -> None:
        blender_path, source = self._settings.get_blender_path_and_source()
        if blender_path and source == "settings":
            self.blender_path_label.setText(f"Blender: {blender_path} (configurado en la app/proyecto)")
            return
        if blender_path and source == "env":
            self.blender_path_label.setText(f"Blender: {blender_path} (BLENDER_EXECUTABLE)")
            return
        self.blender_path_label.setText(
            "Blender: no configurado. Usa 'Configurar Blender' o define BLENDER_EXECUTABLE."
        )

    def _refresh_map_summary_label(self) -> None:
        settings = self._project_state.map_settings
        self.map_summary_label.setText(
            "Mapa: "
            f"{settings.logical_width:.2f} x {settings.logical_height:.2f} {settings.logical_unit} | "
            f"máscaras {settings.mask_width}x{settings.mask_height}"
        )

    def _refresh_layer_tree(self) -> None:
        self._updating_layer_tree = True
        self.layer_tree.clear()
        items_by_path: dict[str, QTreeWidgetItem] = {}

        for layer in self._layer_manager.all_layers():
            parts = layer.layer_id.split("/")
            current_path: list[str] = []
            parent_item: QTreeWidgetItem | None = None

            for index, part in enumerate(parts):
                current_path.append(part)
                path_key = "/".join(current_path)
                item = items_by_path.get(path_key)
                if item is None:
                    item = QTreeWidgetItem([part])
                    if parent_item is None:
                        self.layer_tree.addTopLevelItem(item)
                    else:
                        parent_item.addChild(item)
                    items_by_path[path_key] = item

                is_leaf = index == len(parts) - 1
                if is_leaf:
                    item.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    item.setData(0, Qt.ItemDataRole.UserRole, layer.layer_id)
                    item.setCheckState(
                        0,
                        Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked,
                    )
                    item.setForeground(0, QColor(layer.color_hex))
                else:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    group_font = QFont()
                    group_font.setBold(True)
                    item.setFont(0, group_font)

                parent_item = item

        self.layer_tree.expandAll()
        self._updating_layer_tree = False

        if self._active_layer_id and self._select_layer_item(self._active_layer_id):
            return
        self._select_first_layer()

    def _select_layer_item(self, layer_id: str) -> bool:
        for item in self._iter_leaf_items():
            if item.data(0, Qt.ItemDataRole.UserRole) == layer_id:
                self.layer_tree.setCurrentItem(item)
                return True
        return False

    def _select_first_layer(self) -> None:
        for item in self._iter_leaf_items():
            self.layer_tree.setCurrentItem(item)
            return
        self._set_active_layer(None)

    def _iter_leaf_items(self):
        stack = [self.layer_tree.topLevelItem(i) for i in range(self.layer_tree.topLevelItemCount())]
        while stack:
            current = stack.pop(0)
            layer_id = current.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(layer_id, str):
                yield current
            for idx in range(current.childCount()):
                stack.append(current.child(idx))

    def _on_layer_selection_changed(self) -> None:
        selected = self.layer_tree.selectedItems()
        if not selected:
            self._set_active_layer(None)
            return

        layer_id = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(layer_id, str):
            self._set_active_layer(None)
            return
        self._set_active_layer(layer_id)

    def _set_active_layer(self, layer_id: str | None) -> None:
        self._active_layer_id = layer_id
        self.canvas_view.set_active_layer(layer_id)
        if layer_id is None:
            self.active_layer_label.setText("Capa activa: ninguna")
            return
        self.active_layer_label.setText(f"Capa activa: {layer_id}")
        self.statusBar().showMessage(f"Capa activa: {layer_id}")

    def _on_layer_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating_layer_tree or column != 0:
            return
        layer_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(layer_id, str):
            return

        visible = item.checkState(0) == Qt.CheckState.Checked
        self._layer_manager.set_layer_visibility(layer_id, visible)
        self.canvas_view.refresh_overlay()
        self._project_state.touch()

    def _on_brush_size_changed(self, value: int) -> None:
        self._brush_tool.set_radius(value)
        self.brush_size_label.setText(f"Tamaño pincel: {self._brush_tool.radius_px}px")

    def _on_brush_intensity_changed(self, value: int) -> None:
        intensity = value / 100.0
        self._brush_tool.set_intensity(intensity)
        self.brush_intensity_label.setText(f"Intensidad: {value}%")

    def _set_brush_mode(self, mode: str) -> None:
        if mode == "paint":
            self.paint_mode_button.setChecked(True)
            self.erase_mode_button.setChecked(False)
            self._brush_tool.set_mode("paint")
            return

        self.paint_mode_button.setChecked(False)
        self.erase_mode_button.setChecked(True)
        self._brush_tool.set_mode("erase")

    def _clear_active_layer(self) -> None:
        if not self._active_layer_id:
            QMessageBox.information(self, "Sin capa activa", "Selecciona una capa para limpiarla.")
            return
        self._layer_manager.clear_layer(self._active_layer_id)
        self.canvas_view.refresh_overlay()
        self._project_state.touch()
        self._append_log(f"Capa limpiada: {self._active_layer_id}")

    def _on_mask_modified(self) -> None:
        self._project_state.touch()

    def _sync_project_runtime_data(self) -> None:
        self._project_state.source_blend = str(self._current_blend) if self._current_blend else ""
        self._project_state.blender_executable = self._settings.get_blender_executable() or ""
        if self._project_file_path and not self._project_state.project_name.strip():
            self._project_state.project_name = self._project_file_path.stem

    def _rebuild_layer_manager(self, project_dir: Path | None) -> None:
        self._layer_manager = LayerMaskManager(self._project_state.map_settings)
        if project_dir and self._project_state.layers:
            self._layer_manager.load_from_project_layers(self._project_state.layers, project_dir)
        if self._project_state.collection_tree:
            self._layer_manager.ensure_layers_for_collections(self._project_state.collection_tree)

        self.canvas_view.set_mask_manager(self._layer_manager)
        self.canvas_view.set_map_settings(self._project_state.map_settings)
        self.canvas_view.refresh_overlay()
        self._refresh_layer_tree()

    def _apply_project_to_ui(self) -> None:
        self._refresh_project_label()
        self._refresh_blend_label()
        self._refresh_blender_path_label()
        self._refresh_map_summary_label()
        self._refresh_layer_tree()
        project_title = self._project_state.project_name or "Proyecto"
        self.setWindowTitle(f"Procedural Map Designer - {project_title}")

    @Slot(str)
    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_panel.appendPlainText(f"[{timestamp}] {message}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._active_thread and self._active_thread.isRunning():
            self._append_log("Cerrando inspección en curso antes de salir...")
            self._active_thread.quit()
            self._active_thread.wait(3000)
        super().closeEvent(event)

