from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from proc_map_designer.domain.project_state import MapSettings
from proc_map_designer.ui.map_preview_widget import MapPreviewWidget


class MapSettingsDialog(QDialog):
    def __init__(self, current: MapSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Map Settings")
        self.resize(620, 420)
        self._result = current
        self._base_plane_object = current.base_plane_object

        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Define the logical map size and the internal raster resolution used for masks."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        body = QHBoxLayout()
        layout.addLayout(body, stretch=1)

        form_layout = QFormLayout()
        body.addLayout(form_layout, stretch=0)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.01, 100000.0)
        self.width_spin.setDecimals(2)
        self.width_spin.setValue(current.logical_width)
        self.width_spin.setSuffix(f" {current.logical_unit}")
        form_layout.addRow("Logical Width:", self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0.01, 100000.0)
        self.height_spin.setDecimals(2)
        self.height_spin.setValue(current.logical_height)
        self.height_spin.setSuffix(f" {current.logical_unit}")
        form_layout.addRow("Logical Height:", self.height_spin)

        self.unit_combo = QComboBox()
        self.unit_combo.setEditable(True)
        self.unit_combo.addItems(["m", "cm", "km"])
        current_index = self.unit_combo.findText(current.logical_unit)
        if current_index >= 0:
            self.unit_combo.setCurrentIndex(current_index)
        else:
            self.unit_combo.setCurrentText(current.logical_unit)
        form_layout.addRow("Logical Unit:", self.unit_combo)

        self.mask_width_spin = QSpinBox()
        self.mask_width_spin.setRange(64, 16384)
        self.mask_width_spin.setSingleStep(64)
        self.mask_width_spin.setValue(current.mask_width)
        form_layout.addRow("Mask Resolution X:", self.mask_width_spin)

        self.mask_height_spin = QSpinBox()
        self.mask_height_spin.setRange(64, 16384)
        self.mask_height_spin.setSingleStep(64)
        self.mask_height_spin.setValue(current.mask_height)
        form_layout.addRow("Mask Resolution Y:", self.mask_height_spin)

        self.preview = MapPreviewWidget()
        self.preview.set_map_settings(current)
        body.addWidget(self.preview, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.width_spin.valueChanged.connect(self._update_preview)
        self.height_spin.valueChanged.connect(self._update_preview)
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        self.mask_width_spin.valueChanged.connect(self._update_preview)
        self.mask_height_spin.valueChanged.connect(self._update_preview)

    def _on_unit_changed(self, _: str) -> None:
        unit = self.unit_combo.currentText().strip() or "m"
        self.width_spin.setSuffix(f" {unit}")
        self.height_spin.setSuffix(f" {unit}")
        self._update_preview()

    def _update_preview(self) -> None:
        try:
            self.preview.set_map_settings(self._collect_map_settings())
        except ValueError:
            return

    def _collect_map_settings(self) -> MapSettings:
        return MapSettings(
            logical_width=self.width_spin.value(),
            logical_height=self.height_spin.value(),
            logical_unit=self.unit_combo.currentText().strip() or "m",
            mask_width=self.mask_width_spin.value(),
            mask_height=self.mask_height_spin.value(),
            base_plane_object=self._base_plane_object,
            terrain_material_id=self._result.terrain_material_id,
        )

    def _on_accept(self) -> None:
        try:
            self._result = self._collect_map_settings()
        except ValueError as exc:
            QMessageBox.warning(self, "Valores inválidos", str(exc))
            return
        self.accept()

    def result_settings(self) -> MapSettings:
        return self._result
