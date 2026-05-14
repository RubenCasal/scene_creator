from __future__ import annotations

from dataclasses import dataclass
from math import ceil, hypot
from typing import Literal

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen


MASK_BRUSH_BASELINE_RESOLUTION = 1024.0


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

        effective_radius = self._effective_radius(mask)

        distance = hypot(end.x() - start.x(), end.y() - start.y())
        step = max(1.0, effective_radius * 0.35)
        points = max(1, ceil(distance / step))

        for i in range(points + 1):
            t = i / points
            x = start.x() + (end.x() - start.x()) * t
            y = start.y() + (end.y() - start.y()) * t
            painter.drawEllipse(QPointF(x, y), effective_radius, effective_radius)

        painter.end()

    def _effective_radius(self, mask: QImage) -> float:
        reference = max(mask.width(), mask.height(), 1)
        scale = reference / MASK_BRUSH_BASELINE_RESOLUTION
        return max(1.0, float(self.radius_px) * scale)

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
