from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from proc_map_designer.domain.models import BlendInspectionResult, CollectionNode
from proc_map_designer.infrastructure.settings import AppSettings
from proc_map_designer.services.inspection_service import BlendInspectionError, BlendInspectionService


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
        except Exception as exc:  # pragma: no cover - fallback defensivo
            self.failed.emit(f"Error inesperado: {exc}")
            return

        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self, inspection_service: BlendInspectionService, settings: AppSettings) -> None:
        super().__init__()
        self._inspection_service = inspection_service
        self._settings = settings
        self._load_state = LoadState()
        self._active_thread: QThread | None = None
        self._active_worker: InspectionWorker | None = None
        self._current_blend: Path | None = None

        self.setWindowTitle("Procedural Map Designer - Milestone 1")
        self.resize(1100, 700)
        self._build_ui()
        self._refresh_blender_path_label()

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

        self.blend_file_label = QLabel("Archivo actual: ninguno")
        self.blend_file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        controls_layout.addWidget(self.blend_file_label)

        root_layout.addLayout(controls_layout)

        self.blender_path_label = QLabel()
        root_layout.addWidget(self.blender_path_label)

        splitter = QSplitter()
        root_layout.addWidget(splitter, stretch=1)

        self.collections_tree = QTreeWidget()
        self.collections_tree.setHeaderLabels(["Collection", "Subcollections", "Objetos"])
        self.collections_tree.setAlternatingRowColors(True)
        splitter.addWidget(self.collections_tree)

        placeholder_panel = QFrame()
        placeholder_panel.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        placeholder_layout = QVBoxLayout(placeholder_panel)
        placeholder_label = QLabel("Canvas 2D Placeholder\n(Milestone siguiente)")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet(
            "font-size: 22px; color: #7a7a7a; border: 2px dashed #b0b0b0; padding: 24px;"
        )
        placeholder_layout.addWidget(placeholder_label)
        splitter.addWidget(placeholder_panel)
        splitter.setSizes([320, 780])

        self.log_panel = QPlainTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumBlockCount(500)
        self.log_panel.setPlaceholderText("Logs básicos de ejecución...")
        self.log_panel.setFixedHeight(160)
        root_layout.addWidget(self.log_panel)

        self.statusBar().showMessage("Listo.")

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
        self.blend_file_label.setText(f"Archivo actual: {self._current_blend}")
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
        self._refresh_blender_path_label()
        self._append_log(f"Ruta de Blender guardada: {blender_path}")

    def _refresh_blender_path_label(self) -> None:
        blender_path, source = self._settings.get_blender_path_and_source()
        if blender_path and source == "settings":
            self.blender_path_label.setText(f"Blender: {blender_path} (configurado en la app)")
            return
        if blender_path and source == "env":
            self.blender_path_label.setText(f"Blender: {blender_path} (BLENDER_EXECUTABLE)")
            return
        self.blender_path_label.setText(
            "Blender: no configurado. Usa 'Configurar Blender' o define BLENDER_EXECUTABLE."
        )

    def _set_loading_state(self, is_busy: bool) -> None:
        self._load_state.is_busy = is_busy
        self.select_blend_button.setEnabled(not is_busy)
        self.configure_blender_button.setEnabled(not is_busy)
        if is_busy:
            self.statusBar().showMessage("Inspeccionando .blend...")

    def _start_inspection(self, blend_file: Path) -> None:
        if self._load_state.is_busy:
            self._append_log("Ya hay una inspección en curso. Espera a que finalice.")
            return

        self.collections_tree.clear()
        self._set_loading_state(True)
        self._append_log(f"Iniciando inspección de {blend_file}")

        thread = QThread(self)
        worker = InspectionWorker(self._inspection_service, blend_file)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._on_inspection_success)
        worker.failed.connect(self._on_inspection_failed)

        # Patrón seguro de finalización Qt: el worker termina, pide cerrar el thread y se autodestruye.
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

        if result.warnings:
            for warning in result.warnings:
                self._append_log(f"Warning: {warning}")

        self._populate_tree(result)

        if not result.roots:
            self.statusBar().showMessage("No se encontraron collections útiles en el .blend.")
            self._append_log("No se detectaron collections raíz para mostrar.")
            return

        missing_roots = result.missing_expected_roots(EXPECTED_ROOTS)
        if missing_roots:
            self._append_log(
                "Collections principales esperadas no encontradas: "
                + ", ".join(sorted(missing_roots))
            )
        else:
            self._append_log("Se encontraron collections principales esperadas: vegetation, building.")

        self.statusBar().showMessage("Inspección finalizada correctamente.")

    def _on_inspection_failed(self, message: str) -> None:
        self.collections_tree.clear()
        self.statusBar().showMessage("Error durante la inspección del archivo.")
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Error al inspeccionar .blend", message)

    def _populate_tree(self, result: BlendInspectionResult) -> None:
        self.collections_tree.clear()

        if result.total_collections <= 0 or not result.roots:
            placeholder = QTreeWidgetItem(["(sin collections detectadas)", "0", "0"])
            self.collections_tree.addTopLevelItem(placeholder)
            return

        for root_node in result.roots:
            root_item = self._build_tree_item(root_node, is_root=True)
            self.collections_tree.addTopLevelItem(root_item)

        self.collections_tree.expandToDepth(1)

    def _build_tree_item(self, node: CollectionNode, is_root: bool) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.name, str(len(node.children)), str(node.object_count)])

        if is_root and node.name.lower() in EXPECTED_ROOTS:
            bold_font = QFont()
            bold_font.setBold(True)
            item.setFont(0, bold_font)
            item.setForeground(0, QColor("#1f7a1f"))

        for child in node.children:
            item.addChild(self._build_tree_item(child, is_root=False))

        return item

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
