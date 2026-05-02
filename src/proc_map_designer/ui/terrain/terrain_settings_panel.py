from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from proc_map_designer.domain.terrain_state import TerrainSettings


class TerrainSettingsPanel(QWidget):
    settings_changed = Signal(TerrainSettings)
    apply_noise_requested = Signal()
    save_heightfield_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(200)
        layout = QVBoxLayout(self)

        terrain_group = QGroupBox("Terrain Config")
        terrain_form = QFormLayout(terrain_group)
        self.enabled_check = QCheckBox()
        self.enabled_check.setProperty("toggle", True)
        terrain_form.addRow("Enabled", self.enabled_check)
        self.max_height_spin = QDoubleSpinBox()
        self.max_height_spin.setRange(0.0, 1000.0)
        self.max_height_spin.setDecimals(2)
        terrain_form.addRow("Max Height", self.max_height_spin)
        self.preview_subdivision_spin = QSpinBox()
        self.preview_subdivision_spin.setRange(4, 8)
        terrain_form.addRow("Preview Subdiv", self.preview_subdivision_spin)
        self.export_subdivision_spin = QSpinBox()
        self.export_subdivision_spin.setRange(4, 9)
        terrain_form.addRow("Export Subdiv", self.export_subdivision_spin)
        self.heightfield_resolution_spin = QSpinBox()
        self.heightfield_resolution_spin.setRange(64, 4096)
        self.heightfield_resolution_spin.setSingleStep(64)
        terrain_form.addRow("Heightfield Res", self.heightfield_resolution_spin)
        layout.addWidget(terrain_group)

        noise_group = QGroupBox("Procedural Noise")
        noise_form = QFormLayout(noise_group)
        self.noise_enabled_check = QCheckBox()
        self.noise_enabled_check.setProperty("toggle", True)
        noise_form.addRow("Enabled", self.noise_enabled_check)
        self.noise_scale_spin = QDoubleSpinBox()
        self.noise_scale_spin.setRange(0.01, 100.0)
        self.noise_scale_spin.setDecimals(2)
        noise_form.addRow("Scale", self.noise_scale_spin)
        self.noise_strength_spin = QDoubleSpinBox()
        self.noise_strength_spin.setRange(0.0, 1.0)
        self.noise_strength_spin.setDecimals(3)
        noise_form.addRow("Strength", self.noise_strength_spin)
        self.noise_octaves_spin = QSpinBox()
        self.noise_octaves_spin.setRange(1, 8)
        noise_form.addRow("Octaves", self.noise_octaves_spin)
        self.noise_roughness_spin = QDoubleSpinBox()
        self.noise_roughness_spin.setRange(0.0, 1.0)
        self.noise_roughness_spin.setDecimals(3)
        noise_form.addRow("Roughness", self.noise_roughness_spin)
        self.noise_seed_spin = QSpinBox()
        self.noise_seed_spin.setRange(0, 2_147_483_647)
        noise_form.addRow("Seed", self.noise_seed_spin)
        self.apply_noise_button = QPushButton("Apply Noise to Terrain")
        self.apply_noise_button.clicked.connect(self.apply_noise_requested.emit)
        noise_form.addRow(self.apply_noise_button)
        layout.addWidget(noise_group)

        self.save_button = QPushButton("Save Height PNG")
        self.save_button.clicked.connect(self.save_heightfield_requested.emit)
        layout.addWidget(self.save_button)
        layout.addStretch(1)

        for widget in [
            self.enabled_check,
            self.max_height_spin,
            self.preview_subdivision_spin,
            self.export_subdivision_spin,
            self.heightfield_resolution_spin,
            self.noise_enabled_check,
            self.noise_scale_spin,
            self.noise_strength_spin,
            self.noise_octaves_spin,
            self.noise_roughness_spin,
            self.noise_seed_spin,
        ]:
            signal = getattr(widget, "toggled", None) or getattr(widget, "valueChanged", None)
            if signal is not None:
                signal.connect(self._emit_settings)

    def populate_from_settings(self, settings: TerrainSettings) -> None:
        for widget in [
            self.enabled_check,
            self.max_height_spin,
            self.preview_subdivision_spin,
            self.export_subdivision_spin,
            self.heightfield_resolution_spin,
            self.noise_enabled_check,
            self.noise_scale_spin,
            self.noise_strength_spin,
            self.noise_octaves_spin,
            self.noise_seed_spin,
        ]:
            widget.blockSignals(True)
        self.enabled_check.setChecked(settings.enabled)
        self.max_height_spin.setValue(settings.max_height)
        self.preview_subdivision_spin.setValue(settings.viewport_subdivision)
        self.export_subdivision_spin.setValue(settings.export_subdivision)
        self.heightfield_resolution_spin.setValue(settings.heightfield_resolution)
        self.noise_enabled_check.setChecked(settings.noise.enabled)
        self.noise_scale_spin.setValue(settings.noise.scale)
        self.noise_strength_spin.setValue(settings.noise.strength)
        self.noise_octaves_spin.setValue(settings.noise.octaves)
        self.noise_roughness_spin.setValue(settings.noise.roughness)
        self.noise_seed_spin.setValue(settings.noise.seed)
        for widget in [
            self.enabled_check,
            self.max_height_spin,
            self.preview_subdivision_spin,
            self.export_subdivision_spin,
            self.heightfield_resolution_spin,
            self.noise_enabled_check,
            self.noise_scale_spin,
            self.noise_strength_spin,
            self.noise_octaves_spin,
            self.noise_roughness_spin,
            self.noise_seed_spin,
        ]:
            widget.blockSignals(False)

    def _emit_settings(self, *_args) -> None:
        self.settings_changed.emit(
            TerrainSettings(
                enabled=self.enabled_check.isChecked(),
                max_height=float(self.max_height_spin.value()),
                viewport_subdivision=int(self.preview_subdivision_spin.value()),
                export_subdivision=int(self.export_subdivision_spin.value()),
                heightfield_resolution=int(self.heightfield_resolution_spin.value()),
                noise={
                    "enabled": self.noise_enabled_check.isChecked(),
                    "scale": float(self.noise_scale_spin.value()),
                    "strength": float(self.noise_strength_spin.value()),
                    "octaves": int(self.noise_octaves_spin.value()),
                    "roughness": float(self.noise_roughness_spin.value()),
                    "seed": int(self.noise_seed_spin.value()),
                },
            )
        )
