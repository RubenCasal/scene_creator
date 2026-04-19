from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

try:  # pragma: no cover - optional dependency in test environment
    import numpy as np
except Exception:  # pragma: no cover
    np = None

if TYPE_CHECKING:  # pragma: no cover
    import bpy  # noqa: F401

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


class TerrainSampler:
    def __init__(self, heightfield_path, max_height: float, map_width: float, map_height: float):
        if np is None:
            raise RuntimeError("numpy no está disponible para TerrainSampler.")
        self.heightfield_path = Path(heightfield_path)
        self.max_height = float(max_height)
        self.map_width = float(map_width)
        self.map_height = float(map_height)
        self._values = self._load_heightfield(self.heightfield_path)
        self._height, self._width = self._values.shape

    def sample_at(self, world_x: float, world_y: float) -> float:
        u = np.clip((world_x + self.map_width / 2.0) / max(self.map_width, 0.0001), 0.0, 1.0)
        v = np.clip((self.map_height / 2.0 - world_y) / max(self.map_height, 0.0001), 0.0, 1.0)
        return float(self._bilinear(u, v) * self.max_height)

    def sample_normal_at(self, world_x: float, world_y: float) -> tuple[float, float, float]:
        eps_x = max(self.map_width / max(self._width, 1), 0.001)
        eps_y = max(self.map_height / max(self._height, 1), 0.001)
        left = self.sample_at(world_x - eps_x, world_y)
        right = self.sample_at(world_x + eps_x, world_y)
        down = self.sample_at(world_x, world_y - eps_y)
        up = self.sample_at(world_x, world_y + eps_y)
        normal = np.array([left - right, 2.0 * max(eps_x, eps_y), down - up], dtype=np.float32)
        length = float(np.linalg.norm(normal))
        if length <= 1e-6:
            return (0.0, 1.0, 0.0)
        normal /= length
        return (float(normal[0]), float(normal[1]), float(normal[2]))

    def _bilinear(self, u: float, v: float) -> float:
        x = u * (self._width - 1)
        y = v * (self._height - 1)
        x0 = int(np.floor(x))
        y0 = int(np.floor(y))
        x1 = min(self._width - 1, x0 + 1)
        y1 = min(self._height - 1, y0 + 1)
        tx = x - x0
        ty = y - y0
        top = (1.0 - tx) * self._values[y0, x0] + tx * self._values[y0, x1]
        bottom = (1.0 - tx) * self._values[y1, x0] + tx * self._values[y1, x1]
        return float((1.0 - ty) * top + ty * bottom)

    def _load_heightfield(self, path: Path) -> np.ndarray:
        try:
            import bpy  # type: ignore
        except Exception:
            bpy = None
        if bpy is not None:
            image = bpy.data.images.load(str(path), check_existing=False)
            try:
                pixels = np.array(image.pixels[:], dtype=np.float32)
                width, height = image.size[0], image.size[1]
                rgba = pixels.reshape((height, width, 4))
                return rgba[:, :, 0].astype(np.float32)
            finally:
                bpy.data.images.remove(image)
        if Image is None:
            raise RuntimeError("Pillow no está disponible para cargar el heightfield fuera de Blender.")
        image = Image.open(path).convert("I;16")
        values = np.array(image, dtype=np.uint16).astype(np.float32) / 65535.0
        return values
