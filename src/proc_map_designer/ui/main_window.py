from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QSpinBox,
)

from proc_map_designer.domain.models import BlendInspectionResult
from proc_map_designer.domain.project_state import LatestOutputInfo, ProjectState, utc_now_iso
from proc_map_designer.infrastructure.settings import AppSettings
from proc_map_designer.services.generation_pipeline_service import (
    GenerationPipelineError,
    GenerationPipelineService,
)
from proc_map_designer.services.inspection_service import BlendInspectionError, BlendInspectionService
from proc_map_designer.services.project_service import ProjectService, ProjectServiceError
from proc_map_designer.services.terrain_material_catalog import (
    TerrainMaterialCatalog,
    TerrainMaterialCatalogError,
    load_terrain_material_catalog,
)
from proc_map_designer.ui.canvas.brush_tool import BrushTool
from proc_map_designer.ui.canvas.canvas_view import CanvasView
from proc_map_designer.ui.canvas.layer_mask_manager import LayerMaskManager
from proc_map_designer.ui.canvas.road_manager import RoadManager
from proc_map_designer.ui.map_settings_dialog import MapSettingsDialog

try:
    from proc_map_designer.ui.terrain import TerrainTab
    _TERRAIN_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - optional runtime dependency path
    TerrainTab = None  # type: ignore[assignment]
    _TERRAIN_IMPORT_ERROR = exc

EXPECTED_ROOTS = {"vegetation", "building"}
ROAD_TOOL_TREE_ID = "__road_tool__"


@dataclass(slots=True)
class LoadState:
    is_busy: bool = False


@dataclass(slots=True)
class PipelineState:
    is_busy: bool = False
    current_stage: str = "idle"


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


class PipelineWorker(QObject):
    state_changed = Signal(str)
    finished = Signal(object)
    failed = Signal(str, object)
    log = Signal(str)

    def __init__(
        self,
        pipeline_service: GenerationPipelineService,
        operation: str,
        project_state: ProjectState,
        package_dir: Path,
        backend_id: str,
        mask_exporter,
        latest_output: LatestOutputInfo | None = None,
        destination_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._pipeline_service = pipeline_service
        self._operation = operation
        self._project_state = project_state
        self._package_dir = package_dir
        self._backend_id = backend_id
        self._mask_exporter = mask_exporter
        self._latest_output = latest_output
        self._destination_path = destination_path

    @Slot()
    def run(self) -> None:
        try:
            if self._operation == "validate":
                result = self._pipeline_service.validate_project(
                    self._project_state,
                    self._package_dir,
                    self._mask_exporter,
                    self._backend_id,
                    log=self.log.emit,
                    state=self.state_changed.emit,
                )
            elif self._operation == "generate":
                result = self._pipeline_service.generate_project(
                    self._project_state,
                    self._package_dir,
                    self._mask_exporter,
                    self._backend_id,
                    log=self.log.emit,
                    state=self.state_changed.emit,
                )
            elif self._operation == "final_export":
                if self._latest_output is None or self._destination_path is None:
                    raise GenerationPipelineError("Faltan datos para exportación final.")
                self.log.emit(f"Exportando resultado final a: {self._destination_path}")
                result = self._pipeline_service.final_export(
                    self._latest_output,
                    self._destination_path,
                    log=self.log.emit,
                    state=self.state_changed.emit,
                )
            else:
                raise GenerationPipelineError(f"Operación de pipeline no soportada: {self._operation}")
        except GenerationPipelineError as exc:
            self.state_changed.emit("failed")
            self.failed.emit(str(exc), self._build_failed_metadata(str(exc)))
            return
        except Exception as exc:  # pragma: no cover
            message = f"Error inesperado en pipeline: {exc}"
            self.state_changed.emit("failed")
            self.failed.emit(message, self._build_failed_metadata(message))
            return

        self.state_changed.emit(result.status)
        self.finished.emit(result)

    def _build_failed_metadata(self, error_message: str) -> LatestOutputInfo:
        base = self._latest_output or LatestOutputInfo(backend_id=self._backend_id)
        if self._operation == "final_export":
            result_path = base.result_path
            final_output_path = ""
        else:
            result_path = ""
            final_output_path = ""
        return LatestOutputInfo(
            backend_id=base.backend_id or self._backend_id,
            status="failed",
            export_manifest_path=base.export_manifest_path,
            result_path=result_path,
            final_output_path=final_output_path,
            completed_at=utc_now_iso(),
            error_message=error_message,
            used_layer_ids=list(base.used_layer_ids),
            validation_warnings=list(base.validation_warnings),
        )


class MainWindow(QMainWindow):
    def __init__(
        self,
        inspection_service: BlendInspectionService,
        project_service: ProjectService,
        pipeline_service: GenerationPipelineService,
        settings: AppSettings,
    ) -> None:
        super().__init__()
        self._inspection_service = inspection_service
        self._project_service = project_service
        self._pipeline_service = pipeline_service
        self._settings = settings
        self._load_state = LoadState()
        self._pipeline_state = PipelineState()
        self._active_thread: QThread | None = None
        self._active_worker: InspectionWorker | None = None
        self._pipeline_thread: QThread | None = None
        self._pipeline_worker: PipelineWorker | None = None
        self._current_blend: Path | None = None
        self._project_state: ProjectState = self._project_service.create_new_project(
            blender_executable=self._settings.get_blender_executable() or ""
        )
        self._project_file_path: Path | None = None

        self._brush_tool = BrushTool(radius_px=24, intensity=0.75, mode="paint")
        self._layer_manager = LayerMaskManager(self._project_state.map_settings)
        self._road_manager = RoadManager(self._project_state.map_settings)
        self._terrain_material_catalog: TerrainMaterialCatalog | None = None
        self._terrain_available = TerrainTab is not None
        self._active_layer_id: str | None = None
        self._editing_target = "layer"
        self._raster_mode = "paint"
        self._parameter_layer_id: str | None = None
        self._updating_layer_tree = False
        self._updating_parameter_form = False

        self.setWindowTitle("Procedural Map Designer")
        self.resize(1380, 860)
        self._build_actions()
        self._build_menu_and_toolbar()
        self._build_ui()
        self._load_terrain_material_catalog()
        self._populate_backend_choices()
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

        self.action_validate_pipeline = QAction("Validar", self)
        self.action_validate_pipeline.triggered.connect(self._validate_pipeline)

        self.action_generate = QAction("Generar", self)
        self.action_generate.triggered.connect(self._generate_pipeline)

        self.action_open_result = QAction("Abrir resultado", self)
        self.action_open_result.triggered.connect(self._open_result)

        self.action_final_export = QAction("Exportación final", self)
        self.action_final_export.triggered.connect(self._final_export)

    def _build_menu_and_toolbar(self) -> None:
        project_menu = self.menuBar().addMenu("Proyecto")
        project_menu.addAction(self.action_new_project)
        project_menu.addAction(self.action_open_project)
        project_menu.addSeparator()
        project_menu.addAction(self.action_save_project)
        project_menu.addAction(self.action_save_project_as)
        project_menu.addSeparator()
        project_menu.addAction(self.action_configure_map)

        pipeline_menu = self.menuBar().addMenu("Pipeline")
        pipeline_menu.addAction(self.action_validate_pipeline)
        pipeline_menu.addAction(self.action_generate)
        pipeline_menu.addAction(self.action_open_result)
        pipeline_menu.addAction(self.action_final_export)

        toolbar = QToolBar("Proyecto", self)
        toolbar.setMovable(False)
        toolbar.addAction(self.action_new_project)
        toolbar.addAction(self.action_open_project)
        toolbar.addAction(self.action_save_project)
        toolbar.addAction(self.action_save_project_as)
        toolbar.addSeparator()
        toolbar.addAction(self.action_configure_map)
        toolbar.addSeparator()
        toolbar.addAction(self.action_validate_pipeline)
        toolbar.addAction(self.action_generate)
        toolbar.addAction(self.action_open_result)
        self.addToolBar(toolbar)

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

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

        self.pipeline_state_label = QLabel("Pipeline: inactivo")
        root_layout.addWidget(self.pipeline_state_label)

        self.latest_output_label = QLabel("Último resultado: ninguno")
        self.latest_output_label.setWordWrap(True)
        root_layout.addWidget(self.latest_output_label)

        self.step_title_label = QLabel("Paso 1 de 3: Selección y configuración")
        step_font = QFont()
        step_font.setBold(True)
        self.step_title_label.setFont(step_font)
        root_layout.addWidget(self.step_title_label)

        self.content_splitter = QSplitter(Qt.Orientation.Vertical)
        self.content_splitter.setChildrenCollapsible(False)
        root_layout.addWidget(self.content_splitter, stretch=1)

        self.workflow_stack = QStackedWidget()
        self.content_splitter.addWidget(self.workflow_stack)

        self._build_setup_step()
        self._build_paint_step()
        self._build_generate_step()

        self.log_panel = QPlainTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumBlockCount(700)
        self.log_panel.setPlaceholderText("Logs básicos de ejecución...")
        self.log_panel.setMinimumHeight(90)
        self.content_splitter.addWidget(self.log_panel)
        self.content_splitter.setStretchFactor(0, 5)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setSizes([780, 110])

        self.statusBar().showMessage("Listo.")

    def _build_setup_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        intro = QLabel(
            "Selecciona el archivo .blend, configura Blender y define el tamaño del mapa antes de continuar."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls_layout = QHBoxLayout()
        self.select_blend_button = QPushButton("Seleccionar .blend")
        self.select_blend_button.clicked.connect(self._on_select_blend)
        controls_layout.addWidget(self.select_blend_button)

        self.configure_blender_button = QPushButton("Configurar Blender")
        self.configure_blender_button.clicked.connect(self._on_configure_blender)
        controls_layout.addWidget(self.configure_blender_button)
        controls_layout.addStretch(1)
        layout.addLayout(controls_layout)

        form_layout = QFormLayout()

        self.setup_map_width_spin = QDoubleSpinBox()
        self.setup_map_width_spin.setRange(1.0, 100000.0)
        self.setup_map_width_spin.setDecimals(2)
        self.setup_map_width_spin.editingFinished.connect(self._on_setup_map_changed)
        form_layout.addRow("Ancho mapa", self.setup_map_width_spin)

        self.setup_map_height_spin = QDoubleSpinBox()
        self.setup_map_height_spin.setRange(1.0, 100000.0)
        self.setup_map_height_spin.setDecimals(2)
        self.setup_map_height_spin.editingFinished.connect(self._on_setup_map_changed)
        form_layout.addRow("Alto mapa", self.setup_map_height_spin)

        self.setup_mask_width_spin = QSpinBox()
        self.setup_mask_width_spin.setRange(1, 8192)
        self.setup_mask_width_spin.editingFinished.connect(self._on_setup_map_changed)
        form_layout.addRow("Mask width", self.setup_mask_width_spin)

        self.setup_mask_height_spin = QSpinBox()
        self.setup_mask_height_spin.setRange(1, 8192)
        self.setup_mask_height_spin.editingFinished.connect(self._on_setup_map_changed)
        form_layout.addRow("Mask height", self.setup_mask_height_spin)

        self.terrain_material_combo = QComboBox()
        self.terrain_material_combo.currentIndexChanged.connect(self._on_terrain_material_changed)
        form_layout.addRow("Terrain texture", self.terrain_material_combo)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Ruta de salida/resultados")
        self.output_path_edit.editingFinished.connect(self._on_output_path_changed)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_path_edit)
        self.browse_output_button = QPushButton("...")
        self.browse_output_button.clicked.connect(self._browse_output_path)
        output_layout.addWidget(self.browse_output_button)
        output_widget = QWidget()
        output_widget.setLayout(output_layout)
        form_layout.addRow("Ruta salida", output_widget)

        layout.addLayout(form_layout)
        layout.addStretch(1)

        nav_layout = QHBoxLayout()
        nav_layout.addStretch(1)
        self.setup_next_button = QPushButton("Next")
        self.setup_next_button.clicked.connect(self._go_to_paint_step)
        nav_layout.addWidget(self.setup_next_button)
        layout.addLayout(nav_layout)

        self.workflow_stack.addWidget(page)

    def _build_paint_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        intro = QLabel(
            "Pinta las subcollections que quieres generar. Al continuar solo aparecerán las capas que tengan pintura."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        splitter = QSplitter()
        layout.addWidget(splitter, stretch=1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        left_splitter = QSplitter(Qt.Orientation.Vertical)
        left_splitter.setChildrenCollapsible(False)
        left_layout.addWidget(left_splitter, stretch=1)

        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(6)

        layer_title = QLabel("Capas pintables")
        layer_font = QFont()
        layer_font.setBold(True)
        layer_title.setFont(layer_font)
        tree_layout.addWidget(layer_title)

        self.layer_tree = QTreeWidget()
        self.layer_tree.setHeaderLabels(["Layer"])
        self.layer_tree.setAlternatingRowColors(True)
        self.layer_tree.setMinimumWidth(300)
        self.layer_tree.setIndentation(20)
        self.layer_tree.setUniformRowHeights(False)
        tree_font = self.layer_tree.font()
        tree_font.setPointSize(tree_font.pointSize() + 2)
        self.layer_tree.setFont(tree_font)
        self.layer_tree.header().setDefaultSectionSize(270)
        self.layer_tree.itemChanged.connect(self._on_layer_item_changed)
        self.layer_tree.itemSelectionChanged.connect(self._on_layer_selection_changed)
        tree_layout.addWidget(self.layer_tree, stretch=1)

        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        self.roads_hint_label = QLabel(
            "Road aparece en este árbol aunque no exista en el .blend. Selecciona 'Road > Nueva road' para dibujar carreteras procedurales."
        )
        self.roads_hint_label.setWordWrap(True)
        controls_layout.addWidget(self.roads_hint_label)

        self.active_layer_label = QLabel("Capa activa: ninguna")
        controls_layout.addWidget(self.active_layer_label)

        self.brush_size_label = QLabel(f"Tamaño pincel: {self._brush_tool.radius_px}px")
        controls_layout.addWidget(self.brush_size_label)
        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setRange(1, 256)
        self.brush_size_slider.setValue(self._brush_tool.radius_px)
        self.brush_size_slider.valueChanged.connect(self._on_brush_size_changed)
        controls_layout.addWidget(self.brush_size_slider)

        self.brush_intensity_label = QLabel(f"Intensidad: {int(self._brush_tool.intensity * 100)}%")
        controls_layout.addWidget(self.brush_intensity_label)
        self.brush_intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_intensity_slider.setRange(1, 100)
        self.brush_intensity_slider.setValue(int(self._brush_tool.intensity * 100))
        self.brush_intensity_slider.valueChanged.connect(self._on_brush_intensity_changed)
        controls_layout.addWidget(self.brush_intensity_slider)

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

        controls_layout.addLayout(mode_layout)

        self.road_width_label = QLabel(f"Ancho road: {self._brush_tool.radius_px:.0f}")
        controls_layout.addWidget(self.road_width_label)
        self.road_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.road_width_slider.setRange(1, 128)
        self.road_width_slider.setValue(self._brush_tool.radius_px)
        self.road_width_slider.valueChanged.connect(self._on_road_width_changed)
        controls_layout.addWidget(self.road_width_slider)

        self.road_profile_label = QLabel("Perfil road")
        controls_layout.addWidget(self.road_profile_label)
        self.road_profile_combo = QComboBox()
        self.road_profile_combo.addItem("Single", "single")
        self.road_profile_combo.addItem("Double", "double")
        self.road_profile_combo.setCurrentIndex(0)
        self.road_profile_combo.currentIndexChanged.connect(self._on_road_profile_changed)
        controls_layout.addWidget(self.road_profile_combo)

        self.clear_layer_button = QPushButton("Limpiar capa activa")
        self.clear_layer_button.clicked.connect(self._clear_active_layer)
        controls_layout.addWidget(self.clear_layer_button)

        self.remove_last_road_button = QPushButton("Eliminar última road")
        self.remove_last_road_button.clicked.connect(self._remove_last_road)
        controls_layout.addWidget(self.remove_last_road_button)
        controls_layout.addStretch(1)

        left_splitter.addWidget(tree_panel)
        left_splitter.addWidget(controls_panel)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 1)
        left_splitter.setSizes([560, 220])

        splitter.addWidget(left_panel)

        self.paint_tab_widget = QTabWidget()
        self.canvas_view = CanvasView()
        self.paint_tab_widget.addTab(self.canvas_view, "Masks")
        self._terrain_tab = self._build_terrain_tab_placeholder()
        if self._terrain_available and TerrainTab is not None:
            self._terrain_tab = TerrainTab(
                terrain_settings=self._project_state.terrain_settings,
                map_width=self._project_state.map_settings.logical_width,
                map_height=self._project_state.map_settings.logical_height,
                project_dir=str(self._project_file_path.parent) if self._project_file_path else "",
            )
            self._terrain_tab.terrain_state_changed.connect(self._on_terrain_state_changed)
        self.paint_tab_widget.addTab(self._terrain_tab, "Terrain")
        splitter.addWidget(self.paint_tab_widget)
        left_panel.setMinimumWidth(320)
        splitter.setCollapsible(0, False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([360, 1020])

        nav_layout = QHBoxLayout()
        self.paint_back_button = QPushButton("Back")
        self.paint_back_button.clicked.connect(lambda: self._set_workflow_step(0))
        nav_layout.addWidget(self.paint_back_button)
        nav_layout.addStretch(1)
        self.paint_next_button = QPushButton("Next")
        self.paint_next_button.clicked.connect(self._go_to_generate_step)
        nav_layout.addWidget(self.paint_next_button)
        layout.addLayout(nav_layout)

        self.workflow_stack.addWidget(page)

    def _build_generate_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        intro = QLabel(
            "Ajusta los parámetros solo para las capas pintadas y genera el mapa. Las capas no pintadas no aparecen aquí."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        top_layout.addWidget(self.backend_combo)
        top_layout.addStretch(1)
        layout.addLayout(top_layout)

        body_splitter = QSplitter()
        layout.addWidget(body_splitter, stretch=1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(QLabel("Capas pintadas"))

        self.painted_layers_list = QListWidget()
        self.painted_layers_list.currentItemChanged.connect(self._on_parameter_layer_changed)
        left_layout.addWidget(self.painted_layers_list, stretch=1)

        self.painted_layers_summary = QLabel("Sin capas pintadas todavía.")
        self.painted_layers_summary.setWordWrap(True)
        left_layout.addWidget(self.painted_layers_summary)
        body_splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.parameter_layer_label = QLabel("Capa: ninguna")
        right_layout.addWidget(self.parameter_layer_label)

        form_layout = QFormLayout()

        self.param_enabled_check = QCheckBox("Generar esta capa")
        self.param_enabled_check.toggled.connect(self._apply_parameter_form)
        form_layout.addRow("Habilitada", self.param_enabled_check)

        self.param_density_spin = QDoubleSpinBox()
        self.param_density_spin.setRange(0.0, 100000.0)
        self.param_density_spin.setDecimals(3)
        self.param_density_spin.valueChanged.connect(self._apply_parameter_form)
        form_layout.addRow("Density", self.param_density_spin)

        self.param_allow_overlap_check = QCheckBox("Permitir solape")
        self.param_allow_overlap_check.toggled.connect(self._apply_parameter_form)
        form_layout.addRow("Allow overlap", self.param_allow_overlap_check)

        self.param_min_distance_spin = QDoubleSpinBox()
        self.param_min_distance_spin.setRange(0.0, 100000.0)
        self.param_min_distance_spin.setDecimals(3)
        self.param_min_distance_spin.valueChanged.connect(self._apply_parameter_form)
        form_layout.addRow("Min distance", self.param_min_distance_spin)

        self.param_scale_min_spin = QDoubleSpinBox()
        self.param_scale_min_spin.setRange(0.0, 1000.0)
        self.param_scale_min_spin.setDecimals(3)
        self.param_scale_min_spin.valueChanged.connect(self._apply_parameter_form)
        form_layout.addRow("Scale min", self.param_scale_min_spin)

        self.param_scale_max_spin = QDoubleSpinBox()
        self.param_scale_max_spin.setRange(0.0, 1000.0)
        self.param_scale_max_spin.setDecimals(3)
        self.param_scale_max_spin.valueChanged.connect(self._apply_parameter_form)
        form_layout.addRow("Scale max", self.param_scale_max_spin)

        self.param_rotation_spin = QDoubleSpinBox()
        self.param_rotation_spin.setRange(0.0, 360.0)
        self.param_rotation_spin.setDecimals(2)
        self.param_rotation_spin.valueChanged.connect(self._apply_parameter_form)
        form_layout.addRow("Rotation Z", self.param_rotation_spin)

        self.param_seed_spin = QSpinBox()
        self.param_seed_spin.setRange(0, 2_147_483_647)
        self.param_seed_spin.valueChanged.connect(self._apply_parameter_form)
        form_layout.addRow("Seed", self.param_seed_spin)

        self.param_priority_spin = QSpinBox()
        self.param_priority_spin.setRange(-1000, 1000)
        self.param_priority_spin.valueChanged.connect(self._apply_parameter_form)
        form_layout.addRow("Priority", self.param_priority_spin)

        right_layout.addLayout(form_layout)

        self.painted_layers_table = QTableWidget(0, 4)
        self.painted_layers_table.setHorizontalHeaderLabels(["Layer", "Density", "Overlap", "Min dist"])
        self.painted_layers_table.verticalHeader().setVisible(False)
        self.painted_layers_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.painted_layers_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        right_layout.addWidget(self.painted_layers_table, stretch=1)

        body_splitter.addWidget(right_panel)
        body_splitter.setSizes([300, 700])

        nav_layout = QHBoxLayout()
        self.generate_back_button = QPushButton("Back")
        self.generate_back_button.clicked.connect(lambda: self._set_workflow_step(1))
        nav_layout.addWidget(self.generate_back_button)
        nav_layout.addStretch(1)
        self.generate_button = QPushButton("Generate")
        self.generate_button.clicked.connect(self._generate_pipeline)
        nav_layout.addWidget(self.generate_button)
        layout.addLayout(nav_layout)

        self.workflow_stack.addWidget(page)

    def _wire_canvas(self) -> None:
        self.canvas_view.set_brush_tool(self._brush_tool)
        self.canvas_view.set_mask_manager(self._layer_manager)
        self.canvas_view.set_road_manager(self._road_manager)
        self.canvas_view.set_map_settings(self._project_state.map_settings)
        self.canvas_view.set_road_width(float(self.road_width_slider.value()))
        self.canvas_view.set_road_profile(str(self.road_profile_combo.currentData()))
        self.canvas_view.mask_modified.connect(self._on_mask_modified)
        self.canvas_view.road_modified.connect(self._on_road_modified)

    def _populate_backend_choices(self) -> None:
        self.backend_combo.blockSignals(True)
        self.backend_combo.clear()
        for backend in self._pipeline_service.list_backends():
            self.backend_combo.addItem(backend.display_name, backend.backend_id)
        self.backend_combo.blockSignals(False)
        self._refresh_pipeline_actions()

    def _selected_backend_id(self) -> str:
        backend_id = self.backend_combo.currentData()
        if isinstance(backend_id, str) and backend_id:
            return backend_id
        return "python_batch"

    def _set_workflow_step(self, index: int) -> None:
        index = max(0, min(2, index))
        self.workflow_stack.setCurrentIndex(index)
        titles = {
            0: "Paso 1 de 3: Selección y configuración",
            1: "Paso 2 de 3: Pintado por colección",
            2: "Paso 3 de 3: Parámetros y generación",
        }
        self.step_title_label.setText(titles.get(index, "Workflow"))

    def _go_to_paint_step(self) -> None:
        if not self._project_state.source_blend.strip():
            QMessageBox.information(self, "Falta .blend", "Selecciona primero un archivo .blend.")
            return
        if not self._project_state.blender_executable.strip():
            QMessageBox.information(self, "Falta Blender", "Configura primero el ejecutable de Blender.")
            return
        if not self._project_state.collection_tree:
            QMessageBox.information(self, "Falta inspección", "Espera a que termine la inspección del .blend.")
            return
        self._set_workflow_step(1)

    def _go_to_generate_step(self) -> None:
        painted_layer_ids = self._layer_manager.painted_layer_ids()
        if not painted_layer_ids and not self._road_manager.has_roads():
            QMessageBox.information(
                self,
                "Sin contenido",
                "Pinta al menos una capa o dibuja una road antes de continuar al paso de generación.",
            )
            return
        self._refresh_painted_layers_ui()
        self._set_workflow_step(2)

    def _on_setup_map_changed(self) -> None:
        self._project_state.map_settings.logical_width = float(self.setup_map_width_spin.value())
        self._project_state.map_settings.logical_height = float(self.setup_map_height_spin.value())
        self._project_state.map_settings.mask_width = int(self.setup_mask_width_spin.value())
        self._project_state.map_settings.mask_height = int(self.setup_mask_height_spin.value())
        self._project_state.touch()
        self._layer_manager.set_map_settings(self._project_state.map_settings)
        self._road_manager.set_map_settings(self._project_state.map_settings)
        self.canvas_view.set_map_settings(self._project_state.map_settings)
        self.canvas_view.refresh_overlay()
        self._refresh_map_summary_label()

    def _refresh_painted_layers_ui(self) -> None:
        painted_ids = self._layer_manager.painted_layer_ids()
        self.painted_layers_list.blockSignals(True)
        self.painted_layers_list.clear()
        for layer_id in painted_ids:
            item = QListWidgetItem(layer_id)
            item.setData(Qt.ItemDataRole.UserRole, layer_id)
            self.painted_layers_list.addItem(item)
        self.painted_layers_list.blockSignals(False)

        self.painted_layers_summary.setText(
            f"Capas pintadas: {len(painted_ids)}" if painted_ids else "Sin capas pintadas todavía."
        )
        self._refresh_painted_layers_table(painted_ids)

        if painted_ids:
            selected_id = self._parameter_layer_id if self._parameter_layer_id in painted_ids else painted_ids[0]
            for row in range(self.painted_layers_list.count()):
                item = self.painted_layers_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == selected_id:
                    self.painted_layers_list.setCurrentItem(item)
                    break
        else:
            self._set_parameter_layer(None)

    def _refresh_painted_layers_table(self, painted_ids: list[str]) -> None:
        self.painted_layers_table.setRowCount(len(painted_ids))
        for row, layer_id in enumerate(painted_ids):
            layer = self._layer_manager.get_layer(layer_id)
            settings = layer.generation_settings if layer is not None else None
            values = [
                layer_id,
                f"{settings.density:.3f}" if settings is not None else "-",
                "yes" if settings and settings.allow_overlap else "no",
                f"{settings.min_distance:.3f}" if settings is not None else "-",
            ]
            for column, value in enumerate(values):
                self.painted_layers_table.setItem(row, column, QTableWidgetItem(value))
        self.painted_layers_table.resizeColumnsToContents()

    def _on_parameter_layer_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        layer_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        if not isinstance(layer_id, str):
            self._set_parameter_layer(None)
            return
        self._set_parameter_layer(layer_id)

    def _set_parameter_layer(self, layer_id: str | None) -> None:
        self._parameter_layer_id = layer_id
        self._updating_parameter_form = True
        enabled = layer_id is not None
        widgets = [
            self.param_enabled_check,
            self.param_density_spin,
            self.param_allow_overlap_check,
            self.param_min_distance_spin,
            self.param_scale_min_spin,
            self.param_scale_max_spin,
            self.param_rotation_spin,
            self.param_seed_spin,
            self.param_priority_spin,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)

        if not enabled:
            self.parameter_layer_label.setText("Capa: ninguna")
            self._updating_parameter_form = False
            return

        layer = self._layer_manager.get_layer(layer_id)
        if layer is None:
            self.parameter_layer_label.setText("Capa: ninguna")
            self._updating_parameter_form = False
            return

        settings = layer.generation_settings
        self.parameter_layer_label.setText(f"Capa: {layer_id}")
        self.param_enabled_check.setChecked(settings.enabled)
        self.param_density_spin.setValue(settings.density)
        self.param_allow_overlap_check.setChecked(settings.allow_overlap)
        self.param_min_distance_spin.setValue(settings.min_distance)
        self.param_scale_min_spin.setValue(settings.scale_min)
        self.param_scale_max_spin.setValue(settings.scale_max)
        self.param_rotation_spin.setValue(settings.rotation_random_z)
        self.param_seed_spin.setValue(settings.seed or 0)
        self.param_priority_spin.setValue(settings.priority)
        self._updating_parameter_form = False

    def _apply_parameter_form(self) -> None:
        if self._updating_parameter_form or self._parameter_layer_id is None:
            return
        layer = self._layer_manager.get_layer(self._parameter_layer_id)
        if layer is None:
            return

        settings = layer.generation_settings
        settings.enabled = self.param_enabled_check.isChecked()
        settings.density = float(self.param_density_spin.value())
        settings.allow_overlap = self.param_allow_overlap_check.isChecked()
        settings.min_distance = float(self.param_min_distance_spin.value())
        settings.scale_min = float(self.param_scale_min_spin.value())
        settings.scale_max = float(self.param_scale_max_spin.value())
        settings.rotation_random_z = float(self.param_rotation_spin.value())
        settings.seed = int(self.param_seed_spin.value())
        settings.priority = int(self.param_priority_spin.value())
        settings.validate()
        self._project_state.touch()
        self._refresh_painted_layers_table(self._layer_manager.painted_layer_ids())

    def _new_project(self) -> None:
        if self._load_state.is_busy:
            QMessageBox.information(self, "Inspección en curso", "Espera a que termine la inspección actual.")
            return

        blender_exec = self._settings.get_blender_executable() or ""
        self._project_state = self._project_service.create_new_project(blender_executable=blender_exec)
        self._project_file_path = None
        self._current_blend = None
        self._active_layer_id = None
        self._pipeline_state.current_stage = "idle"
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
        self._pipeline_state.current_stage = "idle"

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
        self._terrain_tab.set_project_dir(str(project_path.parent))
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
        self._road_manager.set_map_settings(self._project_state.map_settings)
        self.canvas_view.set_map_settings(self._project_state.map_settings)
        if self._terrain_available:
            self._terrain_tab.set_map_dimensions(
                self._project_state.map_settings.logical_width,
                self._project_state.map_settings.logical_height,
            )
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

    def _validate_pipeline(self) -> None:
        self._refresh_painted_layers_ui()
        self._start_pipeline_operation("validate")

    def _generate_pipeline(self) -> None:
        self._refresh_painted_layers_ui()
        self._start_pipeline_operation("generate")

    def _final_export(self) -> None:
        latest_output = self._project_state.latest_output
        if latest_output is None or not latest_output.result_path.strip():
            QMessageBox.information(self, "Sin resultado", "Primero genera un resultado válido.")
            return

        backend_id = latest_output.backend_id or self._selected_backend_id()
        if not self._pipeline_service.supports_final_export(backend_id):
            QMessageBox.information(
                self,
                "Exportación final no disponible",
                "El backend actual no soporta exportación final adicional.",
            )
            return

        default_path = self.output_path_edit.text().strip() or str(Path.home() / "resultado_final")
        destination_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportación final",
            default_path,
            "All Files (*)",
        )
        if not destination_path:
            return

        self._start_pipeline_operation(
            "final_export",
            latest_output=latest_output,
            destination_path=Path(destination_path),
        )

    def _open_result(self) -> None:
        latest_output = self._project_state.latest_output
        if latest_output is None:
            QMessageBox.information(self, "Sin resultado", "Todavía no hay resultados para abrir.")
            return

        candidate = (
            latest_output.final_output_path
            or latest_output.result_path
        )
        if not candidate:
            QMessageBox.information(self, "Sin resultado", "Todavía no hay una ruta de resultado disponible.")
            return

        target = Path(candidate).expanduser()
        if not target.exists():
            QMessageBox.warning(self, "Resultado no encontrado", f"No existe la ruta: {target}")
            return

        try:
            self._pipeline_service.open_result_in_blender(target)
        except GenerationPipelineError as exc:
            QMessageBox.warning(self, "No se pudo abrir", str(exc))

    def _browse_output_path(self) -> None:
        current = self.output_path_edit.text().strip() or str(Path.home() / "result.blend")
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Seleccionar ruta de salida",
            current,
            "Blender Files (*.blend);;All Files (*)",
        )
        if not output_path:
            return
        self.output_path_edit.setText(output_path)
        self._on_output_path_changed()

    def _on_output_path_changed(self) -> None:
        normalized = self._normalize_output_path(self.output_path_edit.text().strip())
        self.output_path_edit.setText(normalized)
        self._project_state.output_blend = normalized
        self._project_state.touch()

    def _normalize_output_path(self, raw_path: str) -> str:
        path_text = raw_path.strip()
        if not path_text:
            return ""

        candidate = Path(path_text).expanduser()
        if candidate.exists() and candidate.is_dir():
            return str((candidate / "working_map.blend").resolve())
        if candidate.suffix.lower() == ".blend":
            return str(candidate.resolve())
        if candidate.suffix:
            return str(candidate.resolve())
        return str(candidate.with_suffix(".blend").resolve())

    def _on_terrain_material_changed(self, _index: int) -> None:
        material_id = self.terrain_material_combo.currentData()
        if not isinstance(material_id, str) or not material_id:
            return
        self._project_state.map_settings.terrain_material_id = material_id
        self._project_state.touch()
        self._refresh_map_summary_label()

    def _on_backend_changed(self) -> None:
        self._refresh_pipeline_actions()

    def _start_pipeline_operation(
        self,
        operation: str,
        latest_output: LatestOutputInfo | None = None,
        destination_path: Path | None = None,
    ) -> None:
        if self._load_state.is_busy:
            QMessageBox.information(self, "Inspección en curso", "Espera a que termine la inspección actual.")
            return
        if self._pipeline_state.is_busy:
            QMessageBox.information(self, "Pipeline en curso", "Espera a que termine el pipeline actual.")
            return

        self._sync_project_runtime_data()
        layer_order = [layer.layer_id for layer in self._layer_manager.all_layers()]
        painted_ids = set(self._layer_manager.painted_layer_ids())
        current_layers = [
            layer_state
            for layer_state in self._layer_manager.snapshot_layer_states()
            if layer_state.layer_id in painted_ids
        ]
        current_roads = self._road_manager.snapshot_road_states()
        if not current_layers and not current_roads:
            QMessageBox.information(
                self,
                "Sin contenido",
                "Pinta al menos una capa o dibuja una road antes de validar o generar.",
            )
            return
        self._project_state.layers = current_layers
        self._project_state.roads = current_roads
        project_snapshot = ProjectState.from_dict(self._project_state.to_dict())
        mask_snapshots = self._layer_manager.capture_mask_snapshots([layer.layer_id for layer in current_layers])
        package_dir = self._build_pipeline_package_dir()
        backend_id = latest_output.backend_id if latest_output else self._selected_backend_id()

        def mask_exporter(export_root: Path, ordered_layer_ids: list[str]) -> dict[str, str]:
            return LayerMaskManager.export_grayscale_mask_snapshots(
                package_dir=export_root,
                layer_order=list(ordered_layer_ids),
                mask_snapshots=mask_snapshots,
                map_settings=project_snapshot.map_settings,
            )

        worker = PipelineWorker(
            pipeline_service=self._pipeline_service,
            operation=operation,
            project_state=project_snapshot,
            package_dir=package_dir,
            backend_id=backend_id,
            mask_exporter=mask_exporter,
            latest_output=latest_output,
            destination_path=destination_path,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.state_changed.connect(self._on_pipeline_state_changed)
        worker.finished.connect(self._on_pipeline_success)
        worker.failed.connect(self._on_pipeline_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_pipeline_thread_finished)

        self._pipeline_thread = thread
        self._pipeline_worker = worker
        self._set_pipeline_running(True, "exporting")
        self._append_log(f"Pipeline iniciado ({operation}) con backend '{backend_id}'.")
        thread.start()

    def _build_pipeline_package_dir(self) -> Path:
        if self._project_file_path is not None:
            base_dir = self._project_file_path.parent / "exports"
        else:
            output_path = self.output_path_edit.text().strip()
            if output_path:
                base_dir = Path(output_path).expanduser().parent / "exports"
            else:
                base_dir = Path.home() / ".proc_map_designer" / "exports"

        project_name = self._project_state.project_name.strip() or "project"
        safe_name = "_".join(part for part in project_name.replace("/", " ").split() if part) or "project"
        return base_dir / f"{safe_name}_latest"

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
        self._refresh_painted_layers_ui()
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

        if not self._project_state.map_settings.base_plane_object and result.base_plane_candidates:
            suggested_plane = result.base_plane_candidates[0]
            self._project_state.map_settings.base_plane_object = suggested_plane
            self._refresh_map_summary_label()
            self._append_log(f"Plano base sugerido: {suggested_plane}")

        self.statusBar().showMessage("Inspección finalizada correctamente.")

    def _on_inspection_failed(self, message: str) -> None:
        self.statusBar().showMessage("Error durante la inspección del archivo.")
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Error al inspeccionar .blend", message)

    @Slot(str)
    def _on_pipeline_state_changed(self, state: str) -> None:
        self._pipeline_state.current_stage = state
        self._refresh_pipeline_state_label()
        status_map = {
            "exporting": "Exportando...",
            "validating": "Validando...",
            "generating": "Generando...",
            "finalizing": "Exportando final...",
            "validated": "Validación completada.",
            "completed": "Generación completada.",
            "failed": "Pipeline falló.",
        }
        message = status_map.get(state)
        if message:
            self.statusBar().showMessage(message)

    @Slot(object)
    def _on_pipeline_success(self, latest_output: LatestOutputInfo) -> None:
        self._project_state.latest_output = latest_output
        self._project_state.touch()
        self._refresh_latest_output_label()
        self._refresh_pipeline_actions()
        if latest_output.status == "validated":
            self._append_log("Pipeline validado correctamente.")
        else:
            self._append_log("Pipeline completado correctamente.")

    @Slot(str, object)
    def _on_pipeline_failed(self, message: str, latest_output: LatestOutputInfo) -> None:
        self._project_state.latest_output = latest_output
        self._project_state.touch()
        self._refresh_latest_output_label()
        self._refresh_pipeline_actions()
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Error de pipeline", message)

    def _on_pipeline_thread_finished(self) -> None:
        self._set_pipeline_running(False, self._pipeline_state.current_stage)
        self._pipeline_thread = None
        self._pipeline_worker = None
        if self.statusBar().currentMessage() in {
                "Exportando...",
                "Validando...",
                "Generando...",
                "Exportando final...",
                "Validación completada.",
                "Generación completada.",
        }:
            self.statusBar().showMessage("Listo.")

    def _set_pipeline_running(self, is_busy: bool, stage: str) -> None:
        self._pipeline_state.is_busy = is_busy
        self._pipeline_state.current_stage = stage
        self.backend_combo.setEnabled(not is_busy)
        self.output_path_edit.setEnabled(not is_busy)
        self.browse_output_button.setEnabled(not is_busy)
        self.action_validate_pipeline.setEnabled(not is_busy)
        self.action_generate.setEnabled(not is_busy)
        self._refresh_pipeline_actions()
        self._refresh_pipeline_state_label()

    def _set_loading_state(self, is_busy: bool) -> None:
        self._load_state.is_busy = is_busy
        self.select_blend_button.setEnabled(not is_busy)
        self.configure_blender_button.setEnabled(not is_busy)
        self.action_new_project.setEnabled(not is_busy)
        self.action_open_project.setEnabled(not is_busy)
        self.action_configure_map.setEnabled(not is_busy)
        self.action_validate_pipeline.setEnabled(not is_busy and not self._pipeline_state.is_busy)
        self.action_generate.setEnabled(not is_busy and not self._pipeline_state.is_busy)
        self._refresh_pipeline_actions()
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
            f"máscaras {settings.mask_width}x{settings.mask_height} | "
            f"terrain: {settings.terrain_material_id}"
        )

    def _refresh_pipeline_state_label(self) -> None:
        labels = {
            "idle": "inactivo",
            "exporting": "exportando",
            "validating": "validando",
            "generating": "generando",
            "finalizing": "exportando final",
            "validated": "validado",
            "completed": "completado",
            "failed": "fallido",
        }
        state = labels.get(self._pipeline_state.current_stage, self._pipeline_state.current_stage)
        self.pipeline_state_label.setText(f"Pipeline: {state}")

    def _refresh_latest_output_label(self) -> None:
        latest_output = self._project_state.latest_output
        if latest_output is None:
            self.latest_output_label.setText("Último resultado: ninguno")
            return

        parts = [f"estado={latest_output.status or '-'}"]
        if latest_output.backend_id:
            parts.append(f"backend={latest_output.backend_id}")
        result_path = latest_output.final_output_path or latest_output.result_path or latest_output.export_manifest_path
        if result_path:
            parts.append(result_path)
        if latest_output.completed_at:
            parts.append(latest_output.completed_at)
        if latest_output.used_layer_ids:
            parts.append(f"capas={len(latest_output.used_layer_ids)}")
        if latest_output.error_message:
            parts.append(f"error={latest_output.error_message}")
        self.latest_output_label.setText("Último resultado: " + " | ".join(parts))

    def _refresh_pipeline_actions(self) -> None:
        latest_output = self._project_state.latest_output
        has_output = latest_output is not None and bool(latest_output.final_output_path or latest_output.result_path)
        backend_id = latest_output.backend_id if latest_output and latest_output.backend_id else self._selected_backend_id()
        try:
            supports_final_export = self._pipeline_service.supports_final_export(backend_id)
        except GenerationPipelineError:
            supports_final_export = False
        can_start = not self._pipeline_state.is_busy and not self._load_state.is_busy
        self.action_validate_pipeline.setEnabled(can_start)
        self.action_generate.setEnabled(can_start)
        self.action_open_result.setEnabled(has_output)
        self.action_final_export.setEnabled(
            can_start
            and latest_output is not None
            and bool(latest_output.result_path)
            and supports_final_export
        )

    def _refresh_layer_tree(self) -> None:
        self._updating_layer_tree = True
        self.layer_tree.clear()
        if self._project_state.collection_tree:
            for root in self._project_state.collection_tree:
                self._add_collection_tree_item(root, None, None)
        else:
            for layer in self._layer_manager.all_layers():
                parts = layer.layer_id.split("/")
                parent_item: QTreeWidgetItem | None = None
                prefix: str | None = None
                for index, part in enumerate(parts):
                    path = part if prefix is None else f"{prefix}/{part}"
                    is_leaf = index == len(parts) - 1
                    item = self._create_group_or_layer_item(part, path, parent_item, is_leaf)
                    parent_item = item
                    prefix = path

        self._add_road_tree_section()

        self.layer_tree.expandAll()
        self._updating_layer_tree = False

        if self._active_layer_id and self._select_layer_item(self._active_layer_id):
            return
        if self._editing_target == "road" and self._select_layer_item(ROAD_TOOL_TREE_ID):
            return
        self._select_first_layer()

    def _add_collection_tree_item(
        self,
        node,
        parent_item: QTreeWidgetItem | None,
        prefix: str | None,
    ) -> None:
        path = node.name if prefix is None else f"{prefix}/{node.name}"
        is_leaf = not node.children
        item = self._create_group_or_layer_item(node.name, path, parent_item, is_leaf)
        if not is_leaf:
            for child in node.children:
                self._add_collection_tree_item(child, item, path)

    def _create_group_or_layer_item(
        self,
        label: str,
        path: str,
        parent_item: QTreeWidgetItem | None,
        is_leaf: bool,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        if parent_item is None:
            self.layer_tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
        if is_leaf:
            layer = self._layer_manager.get_layer(path)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "layer", "id": path})
            item.setCheckState(
                0,
                Qt.CheckState.Checked if layer and layer.visible else Qt.CheckState.Unchecked,
            )
            if layer is not None:
                item.setForeground(0, QColor(layer.color_hex))
        else:
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            group_font = QFont()
            group_font.setBold(True)
            item.setFont(0, group_font)
        return item

    def _add_road_tree_section(self) -> None:
        road_root = QTreeWidgetItem(["Road"])
        road_root.setFlags(Qt.ItemFlag.ItemIsEnabled)
        root_font = QFont()
        root_font.setBold(True)
        road_root.setFont(0, root_font)
        self.layer_tree.addTopLevelItem(road_root)

        tool_item = QTreeWidgetItem(["Nueva road"])
        tool_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        tool_item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "road_tool", "id": ROAD_TOOL_TREE_ID})
        road_root.addChild(tool_item)

        for road in self._road_manager.all_roads():
            road_item = QTreeWidgetItem([road.name])
            road_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            road_item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "road", "id": road.road_id})
            road_item.setCheckState(0, Qt.CheckState.Checked if road.visible else Qt.CheckState.Unchecked)
            road_root.addChild(road_item)

    def _select_layer_item(self, layer_id: str) -> bool:
        for item in self._iter_leaf_items():
            payload = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(payload, dict) and payload.get("id") == layer_id:
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
            payload = current.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(payload, dict) and isinstance(payload.get("id"), str):
                yield current
            for idx in range(current.childCount()):
                stack.append(current.child(idx))

    def _on_layer_selection_changed(self) -> None:
        selected = self.layer_tree.selectedItems()
        if not selected:
            self._set_active_layer(None)
            return

        payload = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            self._set_active_layer(None)
            return
        kind = payload.get("kind")
        item_id = payload.get("id")
        if kind == "layer" and isinstance(item_id, str):
            if self._raster_mode == "erase":
                self._set_brush_mode("erase")
            else:
                self._set_brush_mode("paint")
            self._set_active_layer(item_id)
            return
        if kind in {"road_tool", "road"}:
            self._set_brush_mode("road")
            self._set_active_layer(None)
            return
        self._set_active_layer(None)

    def _set_active_layer(self, layer_id: str | None) -> None:
        self._active_layer_id = layer_id
        self.canvas_view.set_active_layer(layer_id)
        if layer_id is None:
            if self._editing_target == "road":
                self.active_layer_label.setText("Herramienta activa: Road")
                self.statusBar().showMessage("Herramienta activa: Road")
            else:
                self.active_layer_label.setText("Capa activa: ninguna")
            return
        self.active_layer_label.setText(f"Capa activa: {layer_id}")
        self.statusBar().showMessage(f"Capa activa: {layer_id}")

    def _on_layer_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating_layer_tree or column != 0:
            return
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return
        kind = payload.get("kind")
        item_id = payload.get("id")

        visible = item.checkState(0) == Qt.CheckState.Checked
        if kind == "layer" and isinstance(item_id, str):
            self._layer_manager.set_layer_visibility(item_id, visible)
        elif kind == "road" and isinstance(item_id, str):
            self._road_manager.set_road_visibility(item_id, visible)
        else:
            return
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
            self._editing_target = "layer"
            self._raster_mode = "paint"
            self.paint_mode_button.setChecked(True)
            self.erase_mode_button.setChecked(False)
            self._brush_tool.set_mode("paint")
            self.canvas_view.set_edit_mode("paint")
            return

        if mode == "road":
            self._editing_target = "road"
            self.paint_mode_button.setChecked(False)
            self.erase_mode_button.setChecked(False)
            self.canvas_view.set_edit_mode("road")
            return

        self._editing_target = "layer"
        self._raster_mode = "erase"
        self.paint_mode_button.setChecked(False)
        self.erase_mode_button.setChecked(True)
        self._brush_tool.set_mode("erase")
        self.canvas_view.set_edit_mode("erase")

    def _on_road_width_changed(self, value: int) -> None:
        self.road_width_label.setText(f"Ancho road: {value}")
        self.canvas_view.set_road_width(float(value))

    def _on_road_profile_changed(self, _index: int) -> None:
        self.canvas_view.set_road_profile(str(self.road_profile_combo.currentData()))

    def _remove_last_road(self) -> None:
        road = self._road_manager.remove_last_road()
        if road is None:
            QMessageBox.information(self, "Sin roads", "No hay roads para eliminar.")
            return
        self.canvas_view.refresh_overlay()
        self._refresh_layer_tree()
        self._project_state.touch()
        self._append_log(f"Road eliminada: {road.road_id}")

    def _clear_active_layer(self) -> None:
        if not self._active_layer_id:
            QMessageBox.information(self, "Sin capa activa", "Selecciona una capa para limpiarla.")
            return
        self._layer_manager.clear_layer(self._active_layer_id)
        self.canvas_view.refresh_overlay()
        self._refresh_painted_layers_ui()
        self._project_state.touch()
        self._append_log(f"Capa limpiada: {self._active_layer_id}")

    def _on_mask_modified(self) -> None:
        self._project_state.touch()
        if self.workflow_stack.currentIndex() == 2:
            self._refresh_painted_layers_ui()

    def _on_road_modified(self) -> None:
        self._project_state.touch()
        self.canvas_view.refresh_overlay()
        self._refresh_layer_tree()
        if self.workflow_stack.currentIndex() == 2:
            self._refresh_painted_layers_ui()

    def _sync_project_runtime_data(self) -> None:
        self._project_state.source_blend = str(self._current_blend) if self._current_blend else ""
        self._project_state.blender_executable = self._settings.get_blender_executable() or ""
        self._project_state.output_blend = self.output_path_edit.text().strip()
        if self._terrain_available:
            self._terrain_tab.save_heightfield()
            self._project_state.terrain_settings = self._terrain_tab.terrain_service.settings
        self._project_state.roads = self._road_manager.snapshot_road_states()
        if self._project_file_path and not self._project_state.project_name.strip():
            self._project_state.project_name = self._project_file_path.stem

    def _rebuild_layer_manager(self, project_dir: Path | None) -> None:
        self._layer_manager = LayerMaskManager(self._project_state.map_settings)
        self._road_manager = RoadManager(self._project_state.map_settings)
        if self._terrain_available:
            self._terrain_tab.set_project_dir(str(project_dir) if project_dir else "")
            self._terrain_tab.set_map_dimensions(
                self._project_state.map_settings.logical_width,
                self._project_state.map_settings.logical_height,
            )
            self._terrain_tab.set_terrain_settings(self._project_state.terrain_settings)
        if project_dir and self._project_state.layers:
            self._layer_manager.load_from_project_layers(self._project_state.layers, project_dir)
        if self._project_state.roads:
            self._road_manager.load_from_project_roads(self._project_state.roads)
        if self._project_state.collection_tree:
            self._layer_manager.ensure_layers_for_collections(self._project_state.collection_tree)

        self.canvas_view.set_mask_manager(self._layer_manager)
        self.canvas_view.set_road_manager(self._road_manager)
        self.canvas_view.set_map_settings(self._project_state.map_settings)
        self.canvas_view.refresh_overlay()
        self._refresh_layer_tree()
        self._refresh_painted_layers_ui()

    def _on_terrain_state_changed(self, settings) -> None:
        self._project_state.terrain_settings = settings
        self._project_state.touch()

    def _build_terrain_tab_placeholder(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(
            "Terrain sculpt tools are unavailable because optional dependencies are missing.\n\n"
            "Install the terrain requirements in your virtualenv:\n"
            "pip install numpy Pillow scipy PyOpenGL PyOpenGL-accelerate"
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        if _TERRAIN_IMPORT_ERROR is not None:
            detail = QLabel(f"Import error: {_TERRAIN_IMPORT_ERROR}")
            detail.setWordWrap(True)
            layout.addWidget(detail)
        layout.addStretch(1)
        return widget

    def _apply_project_to_ui(self) -> None:
        self._refresh_project_label()
        self._refresh_blend_label()
        self._refresh_blender_path_label()
        self.setup_map_width_spin.setValue(self._project_state.map_settings.logical_width)
        self.setup_map_height_spin.setValue(self._project_state.map_settings.logical_height)
        self.setup_mask_width_spin.setValue(self._project_state.map_settings.mask_width)
        self.setup_mask_height_spin.setValue(self._project_state.map_settings.mask_height)
        terrain_index = self.terrain_material_combo.findData(self._project_state.map_settings.terrain_material_id)
        if terrain_index >= 0:
            self.terrain_material_combo.setCurrentIndex(terrain_index)
        self.output_path_edit.setText(self._project_state.output_blend)
        if self._project_state.latest_output and self._project_state.latest_output.backend_id:
            index = self.backend_combo.findData(self._project_state.latest_output.backend_id)
            if index >= 0:
                self.backend_combo.setCurrentIndex(index)
        self._refresh_map_summary_label()
        self._refresh_pipeline_state_label()
        self._refresh_latest_output_label()
        self._refresh_pipeline_actions()
        self._refresh_layer_tree()
        self._refresh_painted_layers_ui()
        self._set_workflow_step(0)
        project_title = self._project_state.project_name or "Proyecto"
        self.setWindowTitle(f"Procedural Map Designer - {project_title}")

    def _load_terrain_material_catalog(self) -> None:
        self.terrain_material_combo.blockSignals(True)
        self.terrain_material_combo.clear()
        try:
            self._terrain_material_catalog = load_terrain_material_catalog()
        except TerrainMaterialCatalogError as exc:
            self._terrain_material_catalog = None
            self.terrain_material_combo.addItem("Catalog unavailable", "")
            self.terrain_material_combo.setEnabled(False)
            self._append_log(f"WARNING terrain materials: {exc}")
        else:
            for entry in self._terrain_material_catalog.entries:
                self.terrain_material_combo.addItem(entry.label, entry.id)
            self.terrain_material_combo.setEnabled(True)
        self.terrain_material_combo.blockSignals(False)

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
