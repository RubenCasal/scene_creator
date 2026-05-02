from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget


class StepperBar(QWidget):
    step_clicked = Signal(int)

    def __init__(self, steps: list[str], parent=None):
        super().__init__(parent)
        self._buttons: list[QPushButton] = []
        self._completed: list[bool] = [False] * len(steps)
        self._active_step = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for index, step in enumerate(steps):
            button = QPushButton(f"{index + 1:02d} {step}")
            button.setFlat(True)
            button.clicked.connect(lambda _checked=False, i=index: self.step_clicked.emit(i))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._buttons.append(button)
            layout.addWidget(button)
            if index < len(steps) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setStyleSheet("color:#4b5563; background:#4b5563; min-height:1px; max-height:1px;")
                layout.addWidget(line, stretch=1)
        self.setFixedHeight(44)
        self._refresh()

    def set_active_step(self, index: int) -> None:
        self._active_step = max(0, min(index, len(self._buttons) - 1))
        self._refresh()

    def set_step_completed(self, index: int, done: bool) -> None:
        if 0 <= index < len(self._completed):
            self._completed[index] = done
            self._refresh()

    def _refresh(self) -> None:
        for index, button in enumerate(self._buttons):
            if index == self._active_step:
                button.setStyleSheet(
                    "text-align:left; color:#f9fafb; font-weight:700; border:none; border-bottom:2px solid #3b82f6; padding:6px 4px;"
                )
            elif self._completed[index]:
                button.setStyleSheet(
                    "text-align:left; color:#9ca3af; font-weight:600; border:none; padding:6px 4px;"
                )
            else:
                button.setStyleSheet(
                    "text-align:left; color:#6b7280; font-weight:500; border:none; padding:6px 4px;"
                )
