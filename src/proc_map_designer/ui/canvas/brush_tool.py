from __future__ import annotations

from dataclasses import dataclass
from math import ceil, hypot
from typing import Literal

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen


BrushMode = Literal["paint", "erase"]


@dataclass(slots=True)
class BrushTool:
    radius_px: int = 20
    intensity: float = 1.0
    mode: BrushMode = "paint"

    def set_radius(self, value: int) -> None:
        self.radius_px = max(1, int(value))

    def set_intensity(self, value: float) -> None:
        self.intensity = max(0.0, min(1.0, float(value)))

    def set_mode(self, mode: BrushMode) -> None:
        self.mode = mode

    def paint_segment(self, mask: QImage, start: QPointF, end: QPointF) -> None:
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._configure_painter(painter)

        distance = hypot(end.x() - start.x(), end.y() - start.y())
        step = max(1.0, self.radius_px * 0.35)
        points = max(1, ceil(distance / step))

        for i in range(points + 1):
            t = i / points
            x = start.x() + (end.x() - start.x()) * t
            y = start.y() + (end.y() - start.y()) * t
            painter.drawEllipse(QPointF(x, y), self.radius_px, self.radius_px)

        painter.end()

    def _configure_painter(self, painter: QPainter) -> None:
        alpha = max(1, min(255, int(round(self.intensity * 255.0))))
        if self.mode == "paint":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            brush_color = QColor(255, 255, 255, alpha)
        else:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            brush_color = QColor(255, 255, 255, alpha)

        painter.setBrush(brush_color)
        painter.setPen(QPen(Qt.PenStyle.NoPen))

