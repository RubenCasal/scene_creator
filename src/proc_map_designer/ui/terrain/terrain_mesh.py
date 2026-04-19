from __future__ import annotations

import ctypes

import numpy as np

try:  # pragma: no cover - runtime dependency
    from OpenGL.GL import (
        GL_ARRAY_BUFFER,
        GL_ELEMENT_ARRAY_BUFFER,
        GL_FALSE,
        GL_FLOAT,
        GL_STATIC_DRAW,
        GL_TRIANGLES,
        GL_UNSIGNED_INT,
        glBindBuffer,
        glBindVertexArray,
        glBufferData,
        glDeleteBuffers,
        glDeleteVertexArrays,
        glDrawElements,
        glEnableVertexAttribArray,
        glGenBuffers,
        glGenVertexArrays,
        glVertexAttribPointer,
    )
except Exception:  # pragma: no cover
    GL_ARRAY_BUFFER = GL_ELEMENT_ARRAY_BUFFER = GL_FALSE = GL_FLOAT = GL_STATIC_DRAW = GL_TRIANGLES = GL_UNSIGNED_INT = 0
    def _missing(*args, **kwargs):
        raise RuntimeError("PyOpenGL no disponible")
    glBindBuffer = glBindVertexArray = glBufferData = glDeleteBuffers = glDeleteVertexArrays = glDrawElements = _missing
    glEnableVertexAttribArray = glGenBuffers = glGenVertexArrays = glVertexAttribPointer = _missing


class TerrainMesh:
    def __init__(self, subdivision: int, map_width: float, map_height: float) -> None:
        self.subdivision = subdivision
        self.map_width = map_width
        self.map_height = map_height
        self.vertex_count_per_axis = (2**subdivision) + 1
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)
        vertices, indices = self._build_grid()
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        stride = 4 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))
        glBindVertexArray(0)
        self._index_count = int(indices.size)

    def _build_grid(self) -> tuple[np.ndarray, np.ndarray]:
        count = self.vertex_count_per_axis
        half_w = self.map_width / 2.0
        half_h = self.map_height / 2.0
        vertices: list[float] = []
        indices: list[int] = []
        for y in range(count):
            v = y / max(count - 1, 1)
            z = -half_h + v * self.map_height
            for x in range(count):
                u = x / max(count - 1, 1)
                world_x = -half_w + u * self.map_width
                vertices.extend([world_x, z, u, v])
        for y in range(count - 1):
            for x in range(count - 1):
                i0 = y * count + x
                i1 = i0 + 1
                i2 = i0 + count
                i3 = i2 + 1
                indices.extend([i0, i2, i1, i1, i2, i3])
        return np.array(vertices, dtype=np.float32), np.array(indices, dtype=np.uint32)

    def draw(self) -> None:
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self._index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def delete(self) -> None:
        glDeleteBuffers(1, [self.vbo])
        glDeleteBuffers(1, [self.ebo])
        glDeleteVertexArrays(1, [self.vao])
