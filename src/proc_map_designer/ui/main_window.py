from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import html
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QSlider,
    QStackedWidget,
    QSplitter,
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
from proc_map_designer.ui.stepper_bar import StepperBar
from proc_map_designer.ui.style.icons import load_svg_icon

try:
    from proc_map_designer.ui.terrain import TerrainTab
    _TERRAIN_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - optional runtime dependency path
    TerrainTab = None  # type: ignore[assignment]
    _TERRAIN_IMPORT_ERROR = exc

EXPECTED_ROOTS = {"vegetation", "building"}
ROAD_TOOL_TREE_ID = "__road_tool__"
DEFAULT_ROAD_SCALE = 6


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
        self.log.emit(f"Inspecting: {self._blend_file}")
        try:
            result = self._service.inspect(self._blend_file)
        except BlendInspectionError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"Unexpected error: {exc}")
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
                    raise GenerationPipelineError("Missing data for final export.")
                self.log.emit(f"Exporting final result to: {self._destination_path}")
                result = self._pipeline_service.final_export(
                    self._latest_output,
                    self._destination_path,
                    log=self.log.emit,
                    state=self.state_changed.emit,
                )
            else:
                raise GenerationPipelineError(f"Unsupported pipeline operation: {self._operation}")
        except GenerationPipelineError as exc:
            self.state_changed.emit("failed")
            self.failed.emit(str(exc), self._build_failed_metadata(str(exc)))
            return
        except Exception as exc:  # pragma: no cover
            message = f"Unexpected pipeline error: {exc}"
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
        self._apply_stylesheet(Path(__file__).parent / "style" / "theme.qss")
        self.setWindowIcon(self._load_svg_icon(Path(__file__).resolve().parents[3] / "logo" / "icon_logo_white.svg", 32))
        self.resize(1380, 860)
        self._build_actions()
        self._build_menu_and_toolbar()
        self._build_ui()
        self._load_terrain_material_catalog()
        self._populate_backend_choices()
        self._wire_canvas()
        self._apply_project_to_ui()
        self._append_log("New project initialized.")

    def _build_actions(self) -> None:
        self.action_new_project = QAction("New Project", self)
        self.action_new_project.triggered.connect(self._new_project)

        self.action_open_project = QAction("Open Project", self)
        self.action_open_project.triggered.connect(self._open_project)

        self.action_save_project = QAction("Save Project", self)
        self.action_save_project.triggered.connect(self._save_project)

        self.action_save_project_as = QAction("Save As...", self)
        self.action_save_project_as.triggered.connect(self._save_project_as)

        self.action_configure_map = QAction("Map Settings", self)
        self.action_configure_map.triggered.connect(self._configure_map)

        self.action_validate_pipeline = QAction("Validate", self)
        self.action_validate_pipeline.triggered.connect(self._validate_pipeline)

        self.action_generate = QAction("Generate", self)
        self.action_generate.triggered.connect(self._generate_pipeline)

        self.action_open_result = QAction("Open Result", self)
        self.action_open_result.triggered.connect(self._open_result)

        self.action_final_export = QAction("Final Export", self)
        self.action_final_export.triggered.connect(self._final_export)

    def _build_menu_and_toolbar(self) -> None:
        project_menu = self.menuBar().addMenu("Project")
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

        toolbar = QToolBar("Project", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.action_new_project.setIcon(load_svg_icon("new"))
        self.action_open_project.setIcon(load_svg_icon("open"))
        self.action_save_project.setIcon(load_svg_icon("save"))
        self.action_configure_map.setIcon(load_svg_icon("settings"))
        self.action_validate_pipeline.setIcon(load_svg_icon("validate"))
        self.action_generate.setIcon(load_svg_icon("generate"))
        self.action_open_result.setIcon(load_svg_icon("open_result"))
        self.action_final_export.setIcon(load_svg_icon("export"))
        self.action_save_project_as.setIcon(load_svg_icon("save"))
        for action in [
            self.action_new_project,
            self.action_open_project,
            self.action_save_project,
            self.action_save_project_as,
            self.action_configure_map,
            self.action_validate_pipeline,
            self.action_generate,
            self.action_open_result,
            self.action_final_export,
        ]:
            action.setToolTip(action.text())
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
        toolbar.addAction(self.action_final_export)
        self.addToolBar(toolbar)

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        self._header_bar = QWidget()
        self._header_bar.setFixedHeight(60)
        header_layout = QHBoxLayout(self._header_bar)
        header_layout.setContentsMargins(4, 0, 10, 0)
        header_layout.setSpacing(4)
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(0, 0, 10, 0)
        logo_layout.setSpacing(10)
        self._header_icon_logo = QLabel()
        self._header_icon_logo.setPixmap(
            self._load_svg_pixmap(
                Path(__file__).resolve().parents[3] / "logo" / "icon_logo_white.svg",
                80,
                80,
                preserve_aspect=True,
            )
        )
        logo_layout.addWidget(self._header_icon_logo)
        self._header_name_logo = QLabel()
        self._header_name_logo.setPixmap(
            self._load_svg_pixmap(
                Path(__file__).resolve().parents[3] / "logo" / "name_logo_white.svg",
                180,
                180,
                preserve_aspect=False,
            )
        )
        logo_layout.addWidget(self._header_name_logo)
        header_layout.addLayout(logo_layout)
        self._header_project_name = QLabel()
        self._header_project_name.setProperty("title", True)
        header_font = QFont()
        header_font.setBold(True)
        self._header_project_name.setFont(header_font)
        self._header_project_name.setMaximumWidth(220)
        header_layout.addWidget(self._header_project_name)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet("color:#4b5563;")
        header_layout.addWidget(separator)
        self._header_map_info = QLabel()
        self._header_map_info.setProperty("secondary", True)
        header_layout.addWidget(self._header_map_info)
        header_layout.addStretch(1)
        self._header_pipeline_pill = QLabel()
        self._header_pipeline_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._header_pipeline_pill.setFixedHeight(24)
        self._header_pipeline_pill.setMinimumWidth(96)
        header_layout.addWidget(self._header_pipeline_pill)
        self._header_output_chip = QLabel()
        self._header_output_chip.setProperty("secondary", True)
        self._header_output_chip.setMaximumWidth(340)
        header_layout.addWidget(self._header_output_chip)
        root_layout.addWidget(self._header_bar)

        self._stepper_bar = StepperBar(["Setup", "Paint", "Generate"])
        self._stepper_bar.step_clicked.connect(self._on_stepper_clicked)
        root_layout.addWidget(self._stepper_bar)

        self.content_splitter = QSplitter(Qt.Orientation.Vertical)
        self.content_splitter.setChildrenCollapsible(False)
        root_layout.addWidget(self.content_splitter, stretch=1)

        self.workflow_stack = QStackedWidget()
        self.content_splitter.addWidget(self.workflow_stack)

        self._build_setup_step()
        self._build_paint_step()
        self._build_generate_step()

        self.log_header_label = QLabel("Output Log")
        self.log_header_label.setProperty("secondary", True)
        self.content_splitter.addWidget(self.log_header_label)
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.document().setMaximumBlockCount(700)
        self.log_panel.setPlaceholderText("Execution logs...")
        self.log_panel.setMinimumHeight(90)
        self.content_splitter.addWidget(self.log_panel)
        self.content_splitter.setStretchFactor(0, 5)
        self.content_splitter.setStretchFactor(1, 0)
        self.content_splitter.setStretchFactor(2, 1)
        self.content_splitter.setSizes([760, 24, 180])

        self.statusBar().showMessage("Ready.")

    def _build_setup_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(10)
        cards_layout.setVerticalSpacing(10)

        scene_card = QGroupBox("Scene Source")
        scene_layout = QVBoxLayout(scene_card)
        scene_layout.setSpacing(8)
        self.select_blend_button = QPushButton("📁 Select .blend file")
        self.select_blend_button.setProperty("accent", True)
        self.select_blend_button.clicked.connect(self._on_select_blend)
        scene_layout.addWidget(self.select_blend_button)
        self.setup_blend_info_label = QLabel("No .blend selected")
        self.setup_blend_info_label.setProperty("secondary", True)
        self.setup_blend_info_label.setWordWrap(True)
        scene_layout.addWidget(self.setup_blend_info_label)
        self.configure_blender_button = QPushButton("⚙ Configure Blender executable")
        self.configure_blender_button.clicked.connect(self._on_configure_blender)
        scene_layout.addWidget(self.configure_blender_button)
        self.setup_blender_info_label = QLabel("Blender not configured")
        self.setup_blender_info_label.setProperty("secondary", True)
        self.setup_blender_info_label.setWordWrap(True)
        scene_layout.addWidget(self.setup_blender_info_label)
        scene_layout.addStretch(1)

        settings_card = QGroupBox("Map Settings")
        form_layout = QFormLayout(settings_card)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(8)
        form_layout.setContentsMargins(12, 14, 12, 12)

        self.setup_map_width_spin = QDoubleSpinBox()
        self.setup_map_width_spin.setRange(1.0, 100000.0)
        self.setup_map_width_spin.setDecimals(2)
        self.setup_map_width_spin.editingFinished.connect(self._on_setup_map_changed)
        form_layout.addRow("Map Width", self.setup_map_width_spin)

        self.setup_map_height_spin = QDoubleSpinBox()
        self.setup_map_height_spin.setRange(1.0, 100000.0)
        self.setup_map_height_spin.setDecimals(2)
        self.setup_map_height_spin.editingFinished.connect(self._on_setup_map_changed)
        form_layout.addRow("Map Height", self.setup_map_height_spin)

        self.setup_mask_width_spin = QSpinBox()
        self.setup_mask_width_spin.setRange(1, 8192)
        self.setup_mask_width_spin.editingFinished.connect(self._on_setup_map_changed)
        form_layout.addRow("Mask width", self.setup_mask_width_spin)

        self.setup_mask_height_spin = QSpinBox()
        self.setup_mask_height_spin.setRange(1, 8192)
        self.setup_mask_height_spin.editingFinished.connect(self._on_setup_map_changed)
        form_layout.addRow("Mask height", self.setup_mask_height_spin)

        self.advanced_map_button = QPushButton("⚙ Advanced map config...")
        self.advanced_map_button.clicked.connect(self._configure_map)
        form_layout.addRow(self.advanced_map_button)

        cards_layout.addWidget(scene_card, 0, 0)
        cards_layout.addWidget(settings_card, 0, 1)
        layout.addLayout(cards_layout)

        output_card = QGroupBox("Output")
        output_layout = QFormLayout(output_card)
        output_layout.setHorizontalSpacing(10)
        output_layout.setVerticalSpacing(8)
        output_layout.setContentsMargins(12, 14, 12, 12)

        self.terrain_material_combo = QComboBox()
        self.terrain_material_combo.currentIndexChanged.connect(self._on_terrain_material_changed)
        output_layout.addRow("Terrain texture", self.terrain_material_combo)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Output/result path")
        self.output_path_edit.editingFinished.connect(self._on_output_path_changed)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_path_edit)
        self.browse_output_button = QPushButton("...")
        self.browse_output_button.clicked.connect(self._browse_output_path)
        output_layout.addWidget(self.browse_output_button)
        output_widget = QWidget()
        output_widget.setLayout(output_layout)
        output_card_layout = output_card.layout()
        assert isinstance(output_card_layout, QFormLayout)
        output_card_layout.addRow("Path", output_widget)

        self.backend_combo = QComboBox()
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        output_card_layout.addRow("Backend", self.backend_combo)

        layout.addWidget(output_card)
        layout.addStretch(1)

        nav_layout = QHBoxLayout()
        nav_layout.addStretch(1)
        self.setup_next_button = QPushButton("→ Paint")
        self.setup_next_button.setProperty("accent", True)
        self.setup_next_button.clicked.connect(self._go_to_paint_step)
        nav_layout.addWidget(self.setup_next_button)
        layout.addLayout(nav_layout)

        self.workflow_stack.addWidget(page)

    def _build_paint_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        splitter = QSplitter()
        layout.addWidget(splitter, stretch=1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        layer_group = QGroupBox("Layers")
        tree_layout = QVBoxLayout(layer_group)
        tree_layout.setSpacing(8)
        header_layout = QHBoxLayout()
        header_layout.addStretch(1)
        self.clear_layer_button = QPushButton()
        self.clear_layer_button.setIcon(load_svg_icon("clear"))
        self.clear_layer_button.setToolTip("Clear active layer")
        self.clear_layer_button.clicked.connect(self._clear_active_layer)
        header_layout.addWidget(self.clear_layer_button)
        tree_layout.addLayout(header_layout)

        self.layer_tree = QTreeWidget()
        self.layer_tree.setHeaderLabels(["Layer"])
        self.layer_tree.setAlternatingRowColors(True)
        self.layer_tree.setMinimumWidth(240)
        self.layer_tree.setIndentation(20)
        self.layer_tree.setUniformRowHeights(False)
        tree_font = self.layer_tree.font()
        tree_font.setPointSize(tree_font.pointSize() + 2)
        self.layer_tree.setFont(tree_font)
        self.layer_tree.header().setDefaultSectionSize(270)
        self.layer_tree.itemChanged.connect(self._on_layer_item_changed)
        self.layer_tree.itemSelectionChanged.connect(self._on_layer_selection_changed)
        tree_layout.addWidget(self.layer_tree, stretch=1)

        brush_group = QGroupBox("Brush")
        controls_layout = QVBoxLayout(brush_group)
        controls_layout.setSpacing(8)

        self.brush_size_label = QLabel(f"Size  {self._brush_tool.radius_px}px")
        self.brush_size_label.setProperty("secondary", True)
        controls_layout.addWidget(self.brush_size_label)
        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setRange(1, 256)
        self.brush_size_slider.setValue(self._brush_tool.radius_px)
        self.brush_size_slider.valueChanged.connect(self._on_brush_size_changed)
        controls_layout.addWidget(self.brush_size_slider)

        self.brush_intensity_label = QLabel(f"Intensity  {int(self._brush_tool.intensity * 100)}%")
        self.brush_intensity_label.setProperty("secondary", True)
        controls_layout.addWidget(self.brush_intensity_label)
        self.brush_intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_intensity_slider.setRange(1, 100)
        self.brush_intensity_slider.setValue(int(self._brush_tool.intensity * 100))
        self.brush_intensity_slider.valueChanged.connect(self._on_brush_intensity_changed)
        controls_layout.addWidget(self.brush_intensity_slider)

        mode_layout = QHBoxLayout()
        self.paint_mode_button = QPushButton("Paint")
        self.paint_mode_button.setCheckable(True)
        self.paint_mode_button.setChecked(True)
        self.paint_mode_button.clicked.connect(lambda: self._set_brush_mode("paint"))
        mode_layout.addWidget(self.paint_mode_button)

        self.erase_mode_button = QPushButton("Erase")
        self.erase_mode_button.setCheckable(True)
        self.erase_mode_button.setChecked(False)
        self.erase_mode_button.clicked.connect(lambda: self._set_brush_mode("erase"))
        mode_layout.addWidget(self.erase_mode_button)

        controls_layout.addLayout(mode_layout)

        self.road_group = QGroupBox("Road")
        road_layout = QVBoxLayout(self.road_group)
        road_layout.setSpacing(8)
        self.road_width_label = QLabel(f"Road Scale  {DEFAULT_ROAD_SCALE}")
        self.road_width_label.setProperty("secondary", True)
        road_layout.addWidget(self.road_width_label)
        self.road_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.road_width_slider.setRange(1, 128)
        self.road_width_slider.setValue(DEFAULT_ROAD_SCALE)
        self.road_width_slider.valueChanged.connect(self._on_road_width_changed)
        road_layout.addWidget(self.road_width_slider)

        self.road_profile_label = QLabel("Profile")
        self.road_profile_label.setProperty("secondary", True)
        road_layout.addWidget(self.road_profile_label)
        self.road_profile_combo = QComboBox()
        self.road_profile_combo.addItem("Single", "single")
        self.road_profile_combo.addItem("Double", "double")
        self.road_profile_combo.setCurrentIndex(0)
        self.road_profile_combo.currentIndexChanged.connect(self._on_road_profile_changed)
        road_layout.addWidget(self.road_profile_combo)

        self.remove_last_road_button = QPushButton("Delete Last Road")
        self.remove_last_road_button.clicked.connect(self._remove_last_road)
        self.remove_last_road_button.setProperty("danger", True)
        road_layout.addWidget(self.remove_last_road_button)

        left_layout.addWidget(layer_group, stretch=1)
        left_layout.addWidget(brush_group, stretch=0)
        left_layout.addWidget(self.road_group, stretch=0)
        self.road_group.setVisible(False)

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
        left_panel.setMinimumWidth(270)
        splitter.setCollapsible(0, False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([320, 1060])

        nav_layout = QHBoxLayout()
        self.paint_back_button = QPushButton("← Setup")
        self.paint_back_button.clicked.connect(lambda: self._set_workflow_step(0))
        nav_layout.addWidget(self.paint_back_button)
        nav_layout.addStretch(1)
        self.paint_next_button = QPushButton("→ Generate")
        self.paint_next_button.clicked.connect(self._go_to_generate_step)
        nav_layout.addWidget(self.paint_next_button)
        layout.addLayout(nav_layout)

        self.workflow_stack.addWidget(page)

    def _build_generate_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        body_splitter = QSplitter()
        layout.addWidget(body_splitter, stretch=1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(QLabel("Painted Layers"))

        self.painted_layers_list = QListWidget()
        self.painted_layers_list.currentItemChanged.connect(self._on_parameter_layer_changed)
        left_layout.addWidget(self.painted_layers_list, stretch=1)

        self.painted_layers_summary = QLabel("No painted layers yet.")
        self.painted_layers_summary.setWordWrap(True)
        left_layout.addWidget(self.painted_layers_summary)
        body_splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self.parameter_layer_label = QLabel("Layer: none")
        right_layout.addWidget(self.parameter_layer_label)

        form_layout = QFormLayout()

        self.param_enabled_check = QCheckBox("Generate this layer")
        self.param_enabled_check.toggled.connect(self._apply_parameter_form)
        form_layout.addRow("Enabled", self.param_enabled_check)

        self.param_density_spin = QDoubleSpinBox()
        self.param_density_spin.setRange(0.0, 100000.0)
        self.param_density_spin.setDecimals(3)
        self.param_density_spin.valueChanged.connect(self._apply_parameter_form)
        form_layout.addRow("Density", self.param_density_spin)

        self.param_allow_overlap_check = QCheckBox("Allow overlap")
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

        body_splitter.addWidget(right_panel)
        body_splitter.setSizes([260, 740])

        nav_layout = QHBoxLayout()
        self.generate_back_button = QPushButton("← Paint")
        self.generate_back_button.clicked.connect(lambda: self._set_workflow_step(1))
        nav_layout.addWidget(self.generate_back_button)
        nav_layout.addStretch(1)
        self.validate_button = QPushButton("🔍 Validate")
        self.validate_button.clicked.connect(self._validate_pipeline)
        nav_layout.addWidget(self.validate_button)
        self.generate_button = QPushButton("▶ Generate")
        self.generate_button.setProperty("accent", True)
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
        self._stepper_bar.set_active_step(index)
        for step_index in range(3):
            self._stepper_bar.set_step_completed(step_index, step_index < index)

    def _on_stepper_clicked(self, index: int) -> None:
        current = self.workflow_stack.currentIndex()
        if index <= current:
            self._set_workflow_step(index)
            return
        if index == 1:
            self._go_to_paint_step()
            return
        if index == 2:
            self._go_to_generate_step()
            return

    def _go_to_paint_step(self) -> None:
        if not self._project_state.source_blend.strip():
            QMessageBox.information(self, "Missing .blend", "Select a .blend file first.")
            return
        if not self._project_state.blender_executable.strip():
            QMessageBox.information(self, "Missing Blender", "Configure the Blender executable first.")
            return
        if not self._project_state.collection_tree:
            QMessageBox.information(self, "Inspection Required", "Wait until the .blend inspection finishes.")
            return
        self._set_workflow_step(1)

    def _go_to_generate_step(self) -> None:
        if not self._project_state.source_blend.strip():
            QMessageBox.information(self, "Missing .blend", "Select a .blend file first.")
            return
        if not self._project_state.blender_executable.strip():
            QMessageBox.information(self, "Missing Blender", "Configure the Blender executable first.")
            return
        if not self._project_state.collection_tree:
            QMessageBox.information(self, "Inspection Required", "Wait until the .blend inspection finishes.")
            return
        painted_layer_ids = self._layer_manager.painted_layer_ids()
        if not painted_layer_ids and not self._road_manager.has_roads():
            QMessageBox.information(
                self,
                "No Content",
                "Paint at least one layer or draw a road before continuing to the Generate step.",
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
        disabled_count = 0
        for layer_id in painted_ids:
            layer = self._layer_manager.get_layer(layer_id)
            settings = layer.generation_settings if layer is not None else None
            enabled = bool(settings.enabled) if settings is not None else False
            if not enabled:
                disabled_count += 1
            density_text = f"density: {settings.density:.3f}" if settings is not None else "density: -"
            prefix = "✓" if enabled else "✗"
            item = QListWidgetItem(f"{prefix} {layer_id}    {density_text}")
            item.setData(Qt.ItemDataRole.UserRole, layer_id)
            self.painted_layers_list.addItem(item)
        self.painted_layers_list.blockSignals(False)

        self.painted_layers_summary.setText(
            (f"{len(painted_ids)} layers · {disabled_count} disabled" if painted_ids else "No painted layers yet.")
        )

        if painted_ids:
            selected_id = self._parameter_layer_id if self._parameter_layer_id in painted_ids else painted_ids[0]
            for row in range(self.painted_layers_list.count()):
                item = self.painted_layers_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == selected_id:
                    self.painted_layers_list.setCurrentItem(item)
                    break
        else:
            self._set_parameter_layer(None)

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
            self.parameter_layer_label.setText("Layer: none")
            self._updating_parameter_form = False
            return

        layer = self._layer_manager.get_layer(layer_id)
        if layer is None:
            self.parameter_layer_label.setText("Layer: none")
            self._updating_parameter_form = False
            return

        settings = layer.generation_settings
        self.parameter_layer_label.setText(f"Layer: {layer_id}")
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
        self._refresh_painted_layers_ui()

    def _new_project(self) -> None:
        if self._load_state.is_busy:
            QMessageBox.information(self, "Inspection In Progress", "Wait until the current inspection finishes.")
            return

        blender_exec = self._settings.get_blender_executable() or ""
        self._project_state = self._project_service.create_new_project(blender_executable=blender_exec)
        self._project_file_path = None
        self._current_blend = None
        self._active_layer_id = None
        self._pipeline_state.current_stage = "idle"
        self._rebuild_layer_manager(project_dir=None)
        self._apply_project_to_ui()
        self._append_log("New project created.")

    def _open_project(self) -> None:
        if self._load_state.is_busy:
            QMessageBox.information(self, "Inspection In Progress", "Wait until the current inspection finishes.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(Path.home()),
            "Project JSON (*.json)",
        )
        if not file_path:
            return

        project_path = Path(file_path)
        try:
            project_state = self._project_service.load_project(project_path)
        except ProjectServiceError as exc:
            QMessageBox.critical(self, "Error Opening Project", str(exc))
            self._append_log(f"ERROR opening project: {exc}")
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
        self.statusBar().showMessage("Project loaded.")
        self._append_log(f"Project opened: {project_path}")

    def _save_project(self) -> None:
        if self._project_file_path is None:
            self._save_project_as()
            return
        self._persist_project(self._project_file_path)

    def _save_project_as(self) -> None:
        suggested = self._project_file_path or (Path.home() / "procedural_project.json")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
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
        current_step = self.workflow_stack.currentIndex()
        if self._terrain_available:
            self._terrain_tab.set_project_dir(str(project_path.parent))
        self._sync_project_runtime_data()
        try:
            self._project_state.layers = self._layer_manager.to_layer_states(project_path.parent)
            self._project_service.save_project(self._project_state, project_path)
        except (ProjectServiceError, RuntimeError) as exc:
            QMessageBox.critical(self, "Error Saving Project", str(exc))
            self._append_log(f"ERROR saving project: {exc}")
            return

        self._project_file_path = project_path
        self._apply_project_to_ui()
        self._set_workflow_step(current_step)
        self.statusBar().showMessage("Project saved.")
        self._append_log(f"Project saved: {project_path}")

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
            "Map configured: "
            f"{self._project_state.map_settings.logical_width:.2f} x "
            f"{self._project_state.map_settings.logical_height:.2f} "
            f"{self._project_state.map_settings.logical_unit} | "
            f"raster {self._project_state.map_settings.mask_width}x"
            f"{self._project_state.map_settings.mask_height}"
        )

    def _on_select_blend(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select .blend file",
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
            "Select Blender executable",
            str(Path.home()),
            "All Files (*)",
        )
        if not blender_path:
            return

        self._settings.set_blender_executable(blender_path)
        self._project_state.blender_executable = blender_path
        self._project_state.touch()
        self._refresh_blender_path_label()
        self._append_log(f"Saved Blender path: {blender_path}")

    def _validate_pipeline(self) -> None:
        self._refresh_painted_layers_ui()
        self._start_pipeline_operation("validate")

    def _generate_pipeline(self) -> None:
        self._refresh_painted_layers_ui()
        self._start_pipeline_operation("generate")

    def _final_export(self) -> None:
        latest_output = self._project_state.latest_output
        if latest_output is None or not latest_output.result_path.strip():
            QMessageBox.information(self, "No Result", "Generate a valid result first.")
            return

        backend_id = latest_output.backend_id or self._selected_backend_id()
        if not self._pipeline_service.supports_final_export(backend_id):
            QMessageBox.information(
                self,
                "Final Export Unavailable",
                "The current backend does not support additional final export.",
            )
            return

        default_path = self.output_path_edit.text().strip() or str(Path.home() / "resultado_final")
        destination_path, _ = QFileDialog.getSaveFileName(
            self,
            "Final Export",
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
            QMessageBox.information(self, "No Result", "There is no result to open yet.")
            return

        candidate = (
            latest_output.final_output_path
            or latest_output.result_path
        )
        if not candidate:
            QMessageBox.information(self, "No Result", "There is no result path available yet.")
            return

        target = Path(candidate).expanduser()
        if not target.exists():
            QMessageBox.warning(self, "Result Not Found", f"The path does not exist: {target}")
            return

        try:
            self._pipeline_service.open_result_in_blender(target)
        except GenerationPipelineError as exc:
            QMessageBox.warning(self, "Could Not Open", str(exc))

    def _browse_output_path(self) -> None:
        current = self.output_path_edit.text().strip() or str(Path.home() / "result.blend")
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select output path",
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
        if not path_text or len(path_text) > 4096:
            return ""

        candidate = Path(path_text).expanduser()
        try:
            is_dir = candidate.exists() and candidate.is_dir()
        except OSError:
            return ""
        if is_dir:
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
            QMessageBox.information(self, "Inspection In Progress", "Wait until the current inspection finishes.")
            return
        if self._pipeline_state.is_busy:
            QMessageBox.information(self, "Pipeline In Progress", "Wait until the current pipeline finishes.")
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
                "No Content",
                "Paint at least one layer or draw a road before validating or generating.",
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
        self._append_log(f"Pipeline started ({operation}) with backend '{backend_id}'.")
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
            self._append_log("An inspection is already running. Wait until it finishes.")
            return

        self._set_loading_state(True)
        self._append_log(f"Starting inspection of {blend_file}")

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
        if self.statusBar().currentMessage() == "Inspecting .blend...":
            self.statusBar().showMessage("Ready.")

    def _on_inspection_success(self, result: BlendInspectionResult) -> None:
        self._append_log(
            f"Inspection completed: {result.total_collections} collections found."
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
            self.statusBar().showMessage("No useful collections were found in the .blend.")
            self._append_log("No root collections were detected for layer creation.")
            return

        missing_roots = result.missing_expected_roots(EXPECTED_ROOTS)
        if missing_roots:
            self._append_log(
                "Expected top-level collections not found: "
                + ", ".join(sorted(missing_roots))
            )
        else:
            self._append_log("Expected top-level collections found: vegetation, building.")

        if self._active_layer_id is None:
            self._select_first_layer()

        if not self._project_state.map_settings.base_plane_object and result.base_plane_candidates:
            suggested_plane = result.base_plane_candidates[0]
            self._project_state.map_settings.base_plane_object = suggested_plane
            self._refresh_map_summary_label()
            self._append_log(f"Suggested base plane: {suggested_plane}")

        self.statusBar().showMessage("Inspection finished successfully.")

    def _on_inspection_failed(self, message: str) -> None:
        self.statusBar().showMessage("Error during file inspection.")
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Error Inspecting .blend", message)

    @Slot(str)
    def _on_pipeline_state_changed(self, state: str) -> None:
        self._pipeline_state.current_stage = state
        self._refresh_pipeline_state_label()
        status_map = {
            "exporting": "Exporting...",
            "validating": "Validating...",
            "generating": "Generating...",
            "finalizing": "Final export...",
            "validated": "Validation completed.",
            "completed": "Generation completed.",
            "failed": "Pipeline failed.",
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
            self._append_log("Pipeline validated successfully.")
        else:
            self._append_log("Pipeline completed successfully.")

    @Slot(str, object)
    def _on_pipeline_failed(self, message: str, latest_output: LatestOutputInfo) -> None:
        self._project_state.latest_output = latest_output
        self._project_state.touch()
        self._refresh_latest_output_label()
        self._refresh_pipeline_actions()
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Pipeline Error", message)

    def _on_pipeline_thread_finished(self) -> None:
        self._set_pipeline_running(False, self._pipeline_state.current_stage)
        self._pipeline_thread = None
        self._pipeline_worker = None
        if self.statusBar().currentMessage() in {
                "Exporting...",
                "Validating...",
                "Generating...",
                "Final export...",
                "Validation completed.",
                "Generation completed.",
        }:
            self.statusBar().showMessage("Ready.")

    def _set_pipeline_running(self, is_busy: bool, stage: str) -> None:
        self._pipeline_state.is_busy = is_busy
        self._pipeline_state.current_stage = stage
        self.backend_combo.setEnabled(not is_busy)
        self.output_path_edit.setEnabled(not is_busy)
        self.browse_output_button.setEnabled(not is_busy)
        self.action_validate_pipeline.setEnabled(not is_busy)
        self.action_generate.setEnabled(not is_busy)
        self._stepper_bar.setEnabled(not is_busy and not self._load_state.is_busy)
        self.setup_next_button.setEnabled(not is_busy)
        self.paint_back_button.setEnabled(not is_busy)
        self.paint_next_button.setEnabled(not is_busy)
        self.generate_back_button.setEnabled(not is_busy)
        self.validate_button.setEnabled(not is_busy)
        self.generate_button.setEnabled(not is_busy)
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
        self._stepper_bar.setEnabled(not is_busy and not self._pipeline_state.is_busy)
        self.setup_next_button.setEnabled(not is_busy)
        self.paint_back_button.setEnabled(not is_busy)
        self.paint_next_button.setEnabled(not is_busy)
        self.generate_back_button.setEnabled(not is_busy)
        self.validate_button.setEnabled(not is_busy and not self._pipeline_state.is_busy)
        self.generate_button.setEnabled(not is_busy and not self._pipeline_state.is_busy)
        self._refresh_pipeline_actions()
        if is_busy:
            self.statusBar().showMessage("Inspecting .blend...")

    def _refresh_project_label(self) -> None:
        self._refresh_header_bar()

    def _refresh_blend_label(self) -> None:
        self.setup_blend_info_label.setText(self._project_state.source_blend or "No .blend selected")
        self._refresh_header_bar()

    def _refresh_blender_path_label(self) -> None:
        blender_path, source = self._settings.get_blender_path_and_source()
        label_text = "Blender not configured"
        if blender_path and source == "settings":
            label_text = f"{blender_path} (app/project)"
        elif blender_path and source == "env":
            label_text = f"{blender_path} (BLENDER_EXECUTABLE)"
        self.setup_blender_info_label.setText(label_text)
        self._refresh_header_bar()

    def _refresh_map_summary_label(self) -> None:
        self._refresh_header_bar()

    def _refresh_pipeline_state_label(self) -> None:
        self._refresh_header_bar()

    def _refresh_latest_output_label(self) -> None:
        self._refresh_header_bar()

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

        tool_item = QTreeWidgetItem(["New Road"])
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
                self.statusBar().showMessage("Active Tool: Road")
            return
        self.statusBar().showMessage(f"Active Layer: {layer_id}")

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
        self.brush_size_label.setText(f"Size  {self._brush_tool.radius_px}px")

    def _on_brush_intensity_changed(self, value: int) -> None:
        intensity = value / 100.0
        self._brush_tool.set_intensity(intensity)
        self.brush_intensity_label.setText(f"Intensity  {value}%")

    def _set_brush_mode(self, mode: str) -> None:
        if mode == "paint":
            self._editing_target = "layer"
            self._raster_mode = "paint"
            self.paint_mode_button.setChecked(True)
            self.erase_mode_button.setChecked(False)
            self._brush_tool.set_mode("paint")
            self.canvas_view.set_edit_mode("paint")
            self.road_group.setVisible(False)
            return

        if mode == "road":
            self._editing_target = "road"
            self.paint_mode_button.setChecked(False)
            self.erase_mode_button.setChecked(False)
            self.canvas_view.set_edit_mode("road")
            self.road_group.setVisible(True)
            return

        self._editing_target = "layer"
        self._raster_mode = "erase"
        self.paint_mode_button.setChecked(False)
        self.erase_mode_button.setChecked(True)
        self._brush_tool.set_mode("erase")
        self.canvas_view.set_edit_mode("erase")
        self.road_group.setVisible(False)

    def _on_road_width_changed(self, value: int) -> None:
        self.road_width_label.setText(f"Road Scale  {value}")
        self.canvas_view.set_road_width(float(value))

    def _on_road_profile_changed(self, _index: int) -> None:
        self.canvas_view.set_road_profile(str(self.road_profile_combo.currentData()))

    def _remove_last_road(self) -> None:
        road = self._road_manager.remove_last_road()
        if road is None:
            QMessageBox.information(self, "No Roads", "There are no roads to delete.")
            return
        self.canvas_view.refresh_overlay()
        self._refresh_layer_tree()
        self._project_state.touch()
        self._append_log(f"Road deleted: {road.road_id}")

    def _clear_active_layer(self) -> None:
        if not self._active_layer_id:
            QMessageBox.information(self, "No Active Layer", "Select a layer to clear.")
            return
        self._layer_manager.clear_layer(self._active_layer_id)
        self.canvas_view.refresh_overlay()
        self._refresh_painted_layers_ui()
        self._project_state.touch()
        self._append_log(f"Layer cleared: {self._active_layer_id}")

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
        project_title = self._project_state.project_name or "Project"
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

    def _apply_stylesheet(self, path: Path) -> None:
        if path.exists() and QApplication.instance() is not None:
            QApplication.instance().setStyleSheet(path.read_text(encoding="utf-8"))

    def _load_svg_pixmap(self, svg_path: Path, width: int, height: int, preserve_aspect: bool = False) -> QPixmap:
        renderer = QSvgRenderer(str(svg_path))
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        default_size = renderer.defaultSize()
        if preserve_aspect and default_size.isValid() and default_size.width() > 0 and default_size.height() > 0:
            source_aspect = default_size.width() / default_size.height()
            target_aspect = width / max(height, 1)
            if source_aspect > target_aspect:
                render_width = float(width)
                render_height = render_width / source_aspect
                render_x = 0.0
                render_y = (height - render_height) / 2.0
            else:
                render_height = float(height)
                render_width = render_height * source_aspect
                render_x = (width - render_width) / 2.0
                render_y = 0.0
            renderer.render(painter, QRectF(render_x, render_y, render_width, render_height))
        else:
            renderer.render(painter, QRectF(0, 0, float(width), float(height)))
        painter.end()
        return self._trim_transparent_pixmap(pixmap)

    def _trim_transparent_pixmap(self, pixmap: QPixmap) -> QPixmap:
        image = pixmap.toImage()
        rect = image.rect()
        left = rect.right()
        right = rect.left()
        top = rect.bottom()
        bottom = rect.top()

        found = False
        for y in range(rect.top(), rect.bottom() + 1):
            for x in range(rect.left(), rect.right() + 1):
                if image.pixelColor(x, y).alpha() > 0:
                    left = min(left, x)
                    right = max(right, x)
                    top = min(top, y)
                    bottom = max(bottom, y)
                    found = True

        if not found:
            return pixmap

        cropped = image.copy(left, top, right - left + 1, bottom - top + 1)
        return QPixmap.fromImage(cropped)

    def _load_svg_icon(self, svg_path: Path, size: int) -> QIcon:
        return QIcon(self._load_svg_pixmap(svg_path, size, size))

    def _refresh_header_bar(self) -> None:
        project_name = self._project_file_path.name if self._project_file_path else "Unsaved project"
        self._header_project_name.setText(project_name)
        settings = self._project_state.map_settings
        self._header_map_info.setText(
            f"{settings.logical_width:.0f}×{settings.logical_height:.0f}{settings.logical_unit} · {settings.mask_width}px · {settings.terrain_material_id}"
        )
        labels = {
            "idle": "Idle",
            "exporting": "Exporting",
            "validating": "Validating",
            "generating": "Generating",
            "finalizing": "Finalizing",
            "validated": "Validated",
            "completed": "Success",
            "failed": "Failed",
        }
        pill_styles = {
            "idle": "background:#374151; color:#9ca3af; border-radius:10px; padding:2px 8px;",
            "exporting": "background:#1d4ed8; color:#bfdbfe; border-radius:10px; padding:2px 8px;",
            "validating": "background:#1d4ed8; color:#bfdbfe; border-radius:10px; padding:2px 8px;",
            "generating": "background:#1d4ed8; color:#bfdbfe; border-radius:10px; padding:2px 8px;",
            "finalizing": "background:#1d4ed8; color:#bfdbfe; border-radius:10px; padding:2px 8px;",
            "validated": "background:#14532d; color:#86efac; border-radius:10px; padding:2px 8px;",
            "completed": "background:#14532d; color:#86efac; border-radius:10px; padding:2px 8px;",
            "failed": "background:#7f1d1d; color:#fca5a5; border-radius:10px; padding:2px 8px;",
        }
        stage = self._pipeline_state.current_stage
        self._header_pipeline_pill.setText(labels.get(stage, stage))
        self._header_pipeline_pill.setStyleSheet(pill_styles.get(stage, pill_styles["idle"]))
        latest_output = self._project_state.latest_output
        if latest_output is None:
            output_text = "No output yet"
        else:
            result_path = latest_output.final_output_path or latest_output.result_path or latest_output.export_manifest_path
            output_text = result_path or latest_output.status or "No output yet"
        self._header_output_chip.setText(output_text)

    @Slot(str)
    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        if "ERROR" in message:
            prefix_color = "#ef4444"
        elif "Warning" in message or "WARNING" in message:
            prefix_color = "#f59e0b"
        elif "completed" in message.lower() or "success" in message.lower() or "validated" in message.lower():
            prefix_color = "#22c55e"
        else:
            prefix_color = "#9ca3af"
        line = (
            f'<span style="color:{prefix_color}">[{timestamp}]</span> '
            f'<span style="color:#d1fae5">{html.escape(message)}</span>'
        )
        self.log_panel.append(line)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._active_thread and self._active_thread.isRunning():
            self._append_log("Closing running inspection before exit...")
            self._active_thread.quit()
            self._active_thread.wait(3000)
        super().closeEvent(event)
