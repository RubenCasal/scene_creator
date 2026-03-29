from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from proc_map_designer.domain.coordinates import map_rect_in_viewport
from proc_map_designer.domain.project_state import MapSettings


class MapPreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._map_settings = MapSettings()
        self.setMinimumSize(320, 320)

    def set_map_settings(self, map_settings: MapSettings) -> None:
        self._map_settings = map_settings
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.fillRect(self.rect(), QColor("#f4f4f4"))

        margin = 20
        viewport_width = max(self.width() - margin * 2, 1)
        viewport_height = max(self.height() - margin * 2, 1)
        viewport_x = margin
        viewport_y = margin

        painter.setPen(QPen(QColor("#d0d0d0"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(viewport_x, viewport_y, viewport_width, viewport_height)

        rect = map_rect_in_viewport(viewport_width, viewport_height, self._map_settings)
        map_x = viewport_x + rect.x
        map_y = viewport_y + rect.y
        map_w = rect.width
        map_h = rect.height

        painter.setPen(QPen(QColor("#255aa8"), 2))
        painter.setBrush(QColor(90, 140, 210, 35))
        painter.drawRect(map_x, map_y, map_w, map_h)

        painter.setPen(QPen(QColor("#255aa8"), 1))
        painter.drawLine(map_x + map_w / 2.0, map_y, map_x + map_w / 2.0, map_y + map_h)
        painter.drawLine(map_x, map_y + map_h / 2.0, map_x + map_w, map_y + map_h / 2.0)

        painter.setPen(QColor("#404040"))
        label = (
            f"Mapa lógico: {self._map_settings.logical_width:.2f} x "
            f"{self._map_settings.logical_height:.2f} {self._map_settings.logical_unit}"
        )
        painter.drawText(self.rect().adjusted(8, 8, -8, -8), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, label)

        raster = (
            f"Raster máscaras: {self._map_settings.mask_width} x {self._map_settings.mask_height}"
        )
        painter.drawText(
            self.rect().adjusted(8, 8, -8, -8),
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
            raster,
        )

