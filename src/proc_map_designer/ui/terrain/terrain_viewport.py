from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QSurfaceFormat, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from proc_map_designer.services.terrain_service import TerrainService
from proc_map_designer.ui.terrain.terrain_camera import OrbitCamera
from proc_map_designer.ui.terrain.terrain_mesh import TerrainMesh

try:  # pragma: no cover - runtime dependency
    from OpenGL.GL import *  # type: ignore # noqa: F401,F403
except Exception:  # pragma: no cover
    pass


class TerrainViewport(QOpenGLWidget):
    heightfield_modified = Signal()
    stroke_begun = Signal()

    def __init__(self, terrain_service: TerrainService, map_width: float, map_height: float, parent=None) -> None:
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setSamples(4)
        super().__init__(parent)
        self.setFormat(fmt)
        self._service = terrain_service
        self._map_width = map_width
        self._map_height = map_height
        self._camera = OrbitCamera()
        self._camera.frame_terrain(map_width, map_height, terrain_service.settings.max_height)
        self._mesh: TerrainMesh | None = None
        self._program = None
        self._cursor_program = None
        self._height_texture = None
        self._tool = "raise"
        self._brush_radius_uv = 0.1
        self._brush_strength = 0.25
        self._falloff = "smooth"
        self._cursor_world = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self._is_sculpting = False
        self._is_orbiting = False
        self._is_panning = False
        self._last_pos = QPoint()

    def set_tool(self, tool: str) -> None:
        self._tool = tool

    def set_brush_radius(self, radius_uv: float) -> None:
        self._brush_radius_uv = radius_uv

    def set_brush_strength(self, strength: float) -> None:
        self._brush_strength = strength

    def set_falloff(self, falloff: str) -> None:
        self._falloff = falloff

    def refresh_heightfield(self) -> None:
        if self.context() is None:
            return
        self.makeCurrent()
        self._upload_heightfield()
        self.doneCurrent()
        self.update()

    def initializeGL(self) -> None:  # pragma: no cover - GL runtime
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_MULTISAMPLE)
        self._program = self._create_program("terrain.vert", "terrain.frag")
        self._cursor_program = self._create_program("brush_cursor.vert", "brush_cursor.frag")
        self._mesh = TerrainMesh(self._service.settings.viewport_subdivision, self._map_width, self._map_height)
        self._height_texture = glGenTextures(1)
        self._upload_heightfield()

    def resizeGL(self, width: int, height: int) -> None:  # pragma: no cover - GL runtime
        glViewport(0, 0, width, height)

    def paintGL(self) -> None:  # pragma: no cover - GL runtime
        glClearColor(0.067, 0.094, 0.153, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._mesh is None or self._program is None:
            return
        aspect = max(self.width(), 1) / max(self.height(), 1)
        mvp = self._camera.mvp(aspect).T.astype(np.float32)
        glUseProgram(self._program)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self._height_texture)
        glUniform1i(glGetUniformLocation(self._program, "u_heightfield"), 0)
        glUniform1f(glGetUniformLocation(self._program, "u_max_height"), float(self._service.settings.max_height))
        glUniformMatrix4fv(glGetUniformLocation(self._program, "u_mvp"), 1, GL_FALSE, mvp)
        res = self._service.settings.heightfield_resolution
        glUniform2f(glGetUniformLocation(self._program, "u_texel"), 1.0 / res, 1.0 / res)
        glUniform1i(glGetUniformLocation(self._program, "u_show_grid"), 1)
        glUniform1f(glGetUniformLocation(self._program, "u_grid_spacing"), 5.0)
        self._mesh.draw()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.RightButton:
            self._is_orbiting = True
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_sculpting = True
            self._service.begin_stroke()
            self.stroke_begun.emit()
            self._apply_brush_at_mouse(event.position().x(), event.position().y())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        delta = pos - self._last_pos
        self._last_pos = pos
        if self._is_orbiting:
            self._camera.orbit(delta.x() * 0.4, -delta.y() * 0.3)
            self.update()
            return
        if self._is_panning:
            self._camera.pan(-delta.x() * 0.1, delta.y() * 0.1)
            self.update()
            return
        self._update_cursor(event.position().x(), event.position().y())
        if self._is_sculpting:
            self._apply_brush_at_mouse(event.position().x(), event.position().y())
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_sculpting = False
        if event.button() == Qt.MouseButton.RightButton:
            self._is_orbiting = False
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = 0.01 if event.angleDelta().y() > 0 else -0.01
            self._brush_radius_uv = max(0.01, min(0.5, self._brush_radius_uv + delta))
        else:
            self._camera.zoom(0.9 if event.angleDelta().y() > 0 else 1.1)
        self.update()

    def _apply_brush_at_mouse(self, mouse_x: float, mouse_y: float) -> None:
        hit = self._ray_intersect(mouse_x, mouse_y)
        if hit is None:
            return
        x, z, u, v = hit
        self._cursor_world = np.array([x, self._service.heightfield[int(v * (self._service.settings.heightfield_resolution - 1)), int(u * (self._service.settings.heightfield_resolution - 1))] * self._service.settings.max_height + 0.05, z], dtype=np.float32)
        if self._tool == "ramp":
            return
        self._service.apply_brush((u, v), self._brush_radius_uv, self._brush_strength, self._tool, self._falloff, 1.0)
        self.refresh_heightfield()
        self.heightfield_modified.emit()

    def _update_cursor(self, mouse_x: float, mouse_y: float) -> None:
        hit = self._ray_intersect(mouse_x, mouse_y)
        if hit is None:
            return
        x, z, u, v = hit
        height = self._service.heightfield[int(v * (self._service.settings.heightfield_resolution - 1)), int(u * (self._service.settings.heightfield_resolution - 1))] * self._service.settings.max_height
        self._cursor_world = np.array([x, height + 0.05, z], dtype=np.float32)

    def _ray_intersect(self, mouse_x: float, mouse_y: float) -> tuple[float, float, float, float] | None:
        aspect = max(self.width(), 1) / max(self.height(), 1)
        ndc_x = (2.0 * mouse_x / max(self.width(), 1)) - 1.0
        ndc_y = 1.0 - (2.0 * mouse_y / max(self.height(), 1))
        origin, direction = self._camera.unproject_ray(ndc_x, ndc_y, aspect)
        step = max(self._map_width, self._map_height) / 64.0
        previous_sign = None
        previous_t = 0.0
        for index in range(1, 65):
            t = index * step
            pos = origin + direction * t
            if not (-self._map_width / 2.0 <= pos[0] <= self._map_width / 2.0 and -self._map_height / 2.0 <= pos[2] <= self._map_height / 2.0):
                continue
            u = (pos[0] + self._map_width / 2.0) / self._map_width
            v = (pos[2] + self._map_height / 2.0) / self._map_height
            height = self._sample_height(u, v)
            sign = pos[1] - height
            if previous_sign is not None and previous_sign >= 0.0 and sign <= 0.0:
                low = previous_t
                high = t
                for _ in range(8):
                    mid = (low + high) * 0.5
                    mid_pos = origin + direction * mid
                    u_mid = (mid_pos[0] + self._map_width / 2.0) / self._map_width
                    v_mid = (mid_pos[2] + self._map_height / 2.0) / self._map_height
                    mid_height = self._sample_height(u_mid, v_mid)
                    if mid_pos[1] - mid_height > 0.0:
                        low = mid
                    else:
                        high = mid
                hit_pos = origin + direction * high
                u_hit = (hit_pos[0] + self._map_width / 2.0) / self._map_width
                v_hit = (hit_pos[2] + self._map_height / 2.0) / self._map_height
                return float(hit_pos[0]), float(hit_pos[2]), float(np.clip(u_hit, 0.0, 1.0)), float(np.clip(v_hit, 0.0, 1.0))
            previous_sign = sign
            previous_t = t
        return None

    def _sample_height(self, u: float, v: float) -> float:
        arr = self._service.heightfield
        h, w = arr.shape
        x = np.clip(u, 0.0, 1.0) * (w - 1)
        y = np.clip(v, 0.0, 1.0) * (h - 1)
        x0 = int(np.floor(x))
        y0 = int(np.floor(y))
        x1 = min(w - 1, x0 + 1)
        y1 = min(h - 1, y0 + 1)
        tx = x - x0
        ty = y - y0
        top = (1.0 - tx) * arr[y0, x0] + tx * arr[y0, x1]
        bottom = (1.0 - tx) * arr[y1, x0] + tx * arr[y1, x1]
        return float(((1.0 - ty) * top + ty * bottom) * self._service.settings.max_height)

    def _upload_heightfield(self) -> None:  # pragma: no cover - GL runtime
        glBindTexture(GL_TEXTURE_2D, self._height_texture)
        data = self._service.heightfield.astype(np.float32)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, data.shape[1], data.shape[0], 0, GL_RED, GL_FLOAT, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    def _create_program(self, vertex_name: str, fragment_name: str):  # pragma: no cover - GL runtime
        shader_dir = Path(__file__).resolve().parent / "shaders"
        with (shader_dir / vertex_name).open("r", encoding="utf-8") as fh:
            vertex_src = fh.read()
        with (shader_dir / fragment_name).open("r", encoding="utf-8") as fh:
            fragment_src = fh.read()
        vertex = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vertex, vertex_src)
        glCompileShader(vertex)
        fragment = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fragment, fragment_src)
        glCompileShader(fragment)
        program = glCreateProgram()
        glAttachShader(program, vertex)
        glAttachShader(program, fragment)
        glLinkProgram(program)
        glDeleteShader(vertex)
        glDeleteShader(fragment)
        return program
