from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen


class RoadOverlayRenderer:
    def render(self, painter: QPainter, roads: list[tuple[object, list[QPointF]]], draft: tuple[object, list[QPointF]] | None) -> None:
        pen = QPen(QColor("#f4d35e"))
        pen.setCosmetic(True)
        pen.setWidthF(3.0)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for road, points in roads:
            del road
            self._draw_path(painter, points, QColor("#f4d35e"), 3.0)

        if draft is not None:
            _, points = draft
            self._draw_path(painter, points, QColor("#ff7f50"), 2.0)

    def _draw_path(self, painter: QPainter, points: list[QPointF], color: QColor, width: float) -> None:
        if len(points) < 2:
            return
        pen = QPen(color)
        pen.setCosmetic(True)
        pen.setWidthF(width)
        painter.setPen(pen)
        for index in range(1, len(points)):
            painter.drawLine(points[index - 1], points[index])
        for point in points:
            painter.drawEllipse(point, 3.0, 3.0)
