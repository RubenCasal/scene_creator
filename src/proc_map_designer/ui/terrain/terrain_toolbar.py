from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QComboBox, QSlider, QVBoxLayout, QWidget, QPushButton


class TerrainToolbar(QWidget):
    tool_changed = Signal(str)
    radius_changed = Signal(float)
    strength_changed = Signal(float)
    falloff_changed = Signal(str)
    undo_requested = Signal()
    redo_requested = Signal()
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(120)
        layout = QVBoxLayout(self)
        self._group = QButtonGroup(self)
        for index, tool in enumerate(["raise", "lower", "smooth", "flatten", "noise", "ramp"]):
            button = QPushButton(tool.title())
            button.setCheckable(True)
            if index == 0:
                button.setChecked(True)
            button.clicked.connect(lambda checked=False, t=tool: self.tool_changed.emit(t))
            self._group.addButton(button)
            layout.addWidget(button)

        self.radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.radius_slider.setRange(1, 50)
        self.radius_slider.setValue(10)
        self.radius_slider.valueChanged.connect(lambda v: self.radius_changed.emit(v / 100.0))
        layout.addWidget(self.radius_slider)

        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setRange(1, 100)
        self.strength_slider.setValue(25)
        self.strength_slider.valueChanged.connect(lambda v: self.strength_changed.emit(v / 100.0))
        layout.addWidget(self.strength_slider)

        self.falloff_combo = QComboBox()
        for value in ["smooth", "linear", "sharp", "flat"]:
            self.falloff_combo.addItem(value.title(), value)
        self.falloff_combo.currentIndexChanged.connect(lambda _: self.falloff_changed.emit(str(self.falloff_combo.currentData())))
        layout.addWidget(self.falloff_combo)

        undo_button = QPushButton("Undo")
        undo_button.clicked.connect(self.undo_requested.emit)
        layout.addWidget(undo_button)
        redo_button = QPushButton("Redo")
        redo_button.clicked.connect(self.redo_requested.emit)
        layout.addWidget(redo_button)
        reset_button = QPushButton("Reset Flat")
        reset_button.clicked.connect(self.reset_requested.emit)
        layout.addWidget(reset_button)
        layout.addStretch(1)
