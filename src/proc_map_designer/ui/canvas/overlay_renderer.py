from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

from proc_map_designer.ui.canvas.layer_mask_manager import LayerMask


class OverlayRenderer:
    def render(self, layers: list[LayerMask], width: int, height: int) -> QImage:
        output = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        output.fill(Qt.GlobalColor.transparent)

        painter = QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        for layer in layers:
            if not layer.visible:
                continue
            mask = layer.mask_image
            if mask is None or mask.isNull():
                continue

            tinted = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            color = QColor(layer.color_hex)
            color.setAlpha(255)
            tinted.fill(color)

            local = QPainter(tinted)
            local.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            local.drawImage(0, 0, mask)
            local.end()

            painter.setOpacity(max(0.0, min(1.0, float(layer.opacity))))
            painter.drawImage(0, 0, tinted)

        painter.end()
        return output

