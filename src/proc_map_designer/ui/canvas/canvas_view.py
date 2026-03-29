from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QPixmap, QTransform, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

from proc_map_designer.domain.project_state import MapSettings
from proc_map_designer.ui.canvas.brush_tool import BrushTool
from proc_map_designer.ui.canvas.layer_mask_manager import LayerMaskManager
from proc_map_designer.ui.canvas.overlay_renderer import OverlayRenderer


class CanvasView(QGraphicsView):
    mask_modified = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self._map_rect_item = QGraphicsRectItem()
        self._map_rect_item.setPen(QPen(Qt.GlobalColor.darkGray, 0))
        self._scene.addItem(self._map_rect_item)

        self._overlay_item = QGraphicsPixmapItem()
        self._overlay_item.setZValue(10)
        self._scene.addItem(self._overlay_item)

        self._mask_manager: LayerMaskManager | None = None
        self._brush_tool = BrushTool()
        self._overlay_renderer = OverlayRenderer()
        self._active_layer_id: str | None = None
        self._map_settings = MapSettings()

        self._is_drawing = False
        self._last_scene_point: QPointF | None = None
        self._is_panning = False
        self._pan_last_pos = QPoint()
        self._zoom_level = 0

        self.set_map_settings(self._map_settings)

    def set_map_settings(self, map_settings: MapSettings) -> None:
        self._map_settings = map_settings
        width = map_settings.logical_width
        height = map_settings.logical_height
        self._scene.setSceneRect(-width / 2.0, -height / 2.0, width, height)
        self._map_rect_item.setRect(-width / 2.0, -height / 2.0, width, height)
        self.fitInView(self._map_rect_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_level = 0
        self._refresh_overlay_pixmap()

    def set_mask_manager(self, manager: LayerMaskManager) -> None:
        self._mask_manager = manager
        self._refresh_overlay_pixmap()

    def set_active_layer(self, layer_id: str | None) -> None:
        self._active_layer_id = layer_id

    def set_brush_tool(self, brush_tool: BrushTool) -> None:
        self._brush_tool = brush_tool

    def refresh_overlay(self) -> None:
        self._refresh_overlay_pixmap()

    def _refresh_overlay_pixmap(self) -> None:
        if self._mask_manager is None:
            self._overlay_item.setPixmap(QPixmap())
            return

        width = self._mask_manager.map_settings.mask_width
        height = self._mask_manager.map_settings.mask_height
        overlay_image = self._overlay_renderer.render(self._mask_manager.all_layers(), width, height)
        pixmap = QPixmap.fromImage(overlay_image)
        self._overlay_item.setPixmap(pixmap)

        self._overlay_item.setOffset(-width / 2.0, -height / 2.0)
        scale_x = self._map_settings.logical_width / max(1, width)
        scale_y = self._map_settings.logical_height / max(1, height)
        self._overlay_item.setTransform(QTransform().scale(scale_x, scale_y))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.angleDelta().y() > 0:
            factor = 1.15
            self._zoom_level += 1
        else:
            factor = 1 / 1.15
            self._zoom_level -= 1

        if self._zoom_level < -20:
            self._zoom_level = -20
            return
        if self._zoom_level > 40:
            self._zoom_level = 40
            return

        self.scale(factor, factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_last_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._can_paint():
            scene_point = self.mapToScene(event.position().toPoint())
            if not self._scene.sceneRect().contains(scene_point):
                return
            self._is_drawing = True
            self._last_scene_point = scene_point
            self._paint_segment(scene_point, scene_point)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_panning:
            delta = event.pos() - self._pan_last_pos
            self._pan_last_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return

        if self._is_drawing and self._can_paint():
            scene_point = self.mapToScene(event.position().toPoint())
            if self._last_scene_point is None:
                self._last_scene_point = scene_point
            self._paint_segment(self._last_scene_point, scene_point)
            self._last_scene_point = scene_point
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._is_drawing:
            self._is_drawing = False
            self._last_scene_point = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def _can_paint(self) -> bool:
        return (
            self._mask_manager is not None
            and self._active_layer_id is not None
            and self._mask_manager.get_layer(self._active_layer_id) is not None
        )

    def _paint_segment(self, start: QPointF, end: QPointF) -> None:
        if not self._can_paint() or self._mask_manager is None or self._active_layer_id is None:
            return

        changed = self._mask_manager.paint_stroke(
            layer_id=self._active_layer_id,
            brush=self._brush_tool,
            start_scene=start,
            end_scene=end,
        )
        if not changed:
            return

        self._refresh_overlay_pixmap()
        self.mask_modified.emit()
