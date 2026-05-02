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
        self.setFixedWidth(112)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._tool_buttons: list[QPushButton] = []
        labels = {
            "raise": "R+",
            "lower": "R-",
            "smooth": "Sm",
            "flatten": "Fl",
            "noise": "Ns",
            "ramp": "Rp",
        }
        for index, tool in enumerate(["raise", "lower", "smooth", "flatten", "noise", "ramp"]):
            button = QPushButton(labels[tool])
            button.setCheckable(True)
            button.setFixedSize(36, 36)
            button.setToolTip(tool.title())
            button.setProperty("tool", True)
            if index == 0:
                button.setChecked(True)
            button.clicked.connect(lambda checked=False, t=tool: self._on_tool_clicked(t))
            self._group.addButton(button)
            self._tool_buttons.append(button)
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
        self._refresh_tool_button_state()

    def _on_tool_clicked(self, tool: str) -> None:
        self._refresh_tool_button_state()
        self.tool_changed.emit(tool)

    def _refresh_tool_button_state(self) -> None:
        for button in self._tool_buttons:
            button.setProperty("accent", button.isChecked())
            button.style().unpolish(button)
            button.style().polish(button)
