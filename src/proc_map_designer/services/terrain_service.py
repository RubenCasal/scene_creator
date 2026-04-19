from __future__ import annotations

import zlib
from pathlib import Path

try:  # pragma: no cover - optional dependency in test environment
    import numpy as np
except Exception:  # pragma: no cover
    np = None

from proc_map_designer.domain.terrain_state import TerrainSettings
from proc_map_designer.services._terrain_noise import generate_fbm_noise

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency in test environment
    Image = None

try:
    from scipy.ndimage import uniform_filter  # type: ignore
except Exception:  # pragma: no cover - optional dependency in test environment
    uniform_filter = None


class TerrainServiceError(RuntimeError):
    pass


class TerrainService:
    _MAX_UNDO = 30

    def __init__(self, settings: TerrainSettings) -> None:
        if np is None:
            raise TerrainServiceError("numpy no está disponible para TerrainService.")
        self.settings = settings
        self._heightfield = np.zeros(
            (self.settings.heightfield_resolution, self.settings.heightfield_resolution),
            dtype=np.float32,
        )
        self._undo_stack: list[bytes] = []
        self._redo_stack: list[bytes] = []
        self._dirty = False

    @property
    def heightfield(self) -> np.ndarray:
        return self._heightfield

    @property
    def dirty(self) -> bool:
        return self._dirty

    def update_settings(self, settings: TerrainSettings) -> None:
        resolution_changed = settings.heightfield_resolution != self.settings.heightfield_resolution
        self.settings = settings
        if resolution_changed:
            self._heightfield = np.zeros((settings.heightfield_resolution, settings.heightfield_resolution), dtype=np.float32)
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._dirty = True

    def load_from_path(self, path: str | Path) -> None:
        resolved = Path(path)
        if Image is None:
            raise TerrainServiceError("Pillow no está disponible para cargar el heightfield.")
        if not resolved.exists():
            raise TerrainServiceError(f"No existe el heightfield: {resolved}")
        image = Image.open(resolved)
        image = image.convert("I;16")
        if image.size != (self.settings.heightfield_resolution, self.settings.heightfield_resolution):
            image = image.resize((self.settings.heightfield_resolution, self.settings.heightfield_resolution))
        values = np.array(image, dtype=np.uint16).astype(np.float32) / 65535.0
        self._heightfield = np.clip(values, 0.0, 1.0).astype(np.float32)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._dirty = False

    def save_to_path(self, path: str | Path) -> None:
        resolved = Path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        if Image is None:
            raise TerrainServiceError("Pillow no está disponible para guardar el heightfield.")
        image = Image.fromarray(np.clip(self._heightfield * 65535.0, 0, 65535).astype(np.uint16), mode="I;16")
        image.save(resolved)
        self._dirty = False

    def reset_flat(self) -> None:
        self.begin_stroke()
        self._heightfield.fill(0.0)
        self._redo_stack.clear()
        self._dirty = True

    def apply_base_noise(self) -> None:
        self.begin_stroke()
        noise = generate_fbm_noise(
            self.settings.heightfield_resolution,
            scale=self.settings.noise.scale,
            strength=self.settings.noise.strength,
            octaves=self.settings.noise.octaves,
            roughness=self.settings.noise.roughness,
            seed=self.settings.noise.seed,
        )
        self._heightfield = np.clip(self._heightfield + noise, 0.0, 1.0).astype(np.float32)
        self._redo_stack.clear()
        self._dirty = True

    def begin_stroke(self) -> None:
        snapshot = self._compress_heightfield(self._heightfield)
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def apply_brush(self, uv, radius_uv: float, strength: float, tool: str, falloff: str, dt: float) -> None:
        u = float(uv[0])
        v = float(uv[1])
        resolution = self.settings.heightfield_resolution
        center_x = u * (resolution - 1)
        center_y = v * (resolution - 1)
        radius_px = max(1.0, radius_uv * resolution)
        min_x = max(0, int(center_x - radius_px - 1))
        max_x = min(resolution, int(center_x + radius_px + 2))
        min_y = max(0, int(center_y - radius_px - 1))
        max_y = min(resolution, int(center_y + radius_px + 2))
        patch = self._heightfield[min_y:max_y, min_x:max_x]
        if patch.size == 0:
            return
        ys, xs = np.mgrid[min_y:max_y, min_x:max_x].astype(np.float32)
        dist = np.sqrt((xs - center_x) ** 2 + (ys - center_y) ** 2) / radius_px
        mask = np.clip(1.0 - dist, 0.0, 1.0)
        falloff_values = _compute_falloff(mask, falloff)
        delta = falloff_values * max(0.0, float(strength)) * max(0.0, float(dt))
        if tool == "raise":
            patch += delta
        elif tool == "lower":
            patch -= delta
        elif tool == "flatten":
            center_height = float(self._heightfield[int(round(center_y)), int(round(center_x))])
            patch[:] = patch + (center_height - patch) * delta
        elif tool == "noise":
            rng = np.random.default_rng(self.settings.noise.seed)
            patch += (rng.uniform(-1.0, 1.0, size=patch.shape).astype(np.float32) * delta)
        elif tool == "smooth":
            smoothed = _smooth_patch(patch)
            patch[:] = patch + (smoothed - patch) * delta
        else:
            raise TerrainServiceError(f"Herramienta de terreno no soportada: {tool}")
        self._heightfield[min_y:max_y, min_x:max_x] = np.clip(patch, 0.0, 1.0)
        self._dirty = True

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._compress_heightfield(self._heightfield))
        self._heightfield = self._decompress_heightfield(self._undo_stack.pop())
        self._dirty = True
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._compress_heightfield(self._heightfield))
        self._heightfield = self._decompress_heightfield(self._redo_stack.pop())
        self._dirty = True
        return True

    def _compress_heightfield(self, array: np.ndarray) -> bytes:
        return zlib.compress(array.astype(np.float32).tobytes())

    def _decompress_heightfield(self, payload: bytes) -> np.ndarray:
        raw = zlib.decompress(payload)
        array = np.frombuffer(raw, dtype=np.float32)
        resolution = self.settings.heightfield_resolution
        return array.reshape((resolution, resolution)).copy()


def _compute_falloff(mask: np.ndarray, falloff: str) -> np.ndarray:
    if np is None:
        raise RuntimeError("numpy no está disponible para el brush de terreno.")
    if falloff == "linear":
        return mask
    if falloff == "sharp":
        return np.where(mask >= 0.5, 1.0, np.clip(mask * 2.0, 0.0, 1.0)).astype(np.float32)
    if falloff == "flat":
        return np.where(mask >= 0.8, 1.0, np.clip(mask * 5.0, 0.0, 1.0)).astype(np.float32)
    return np.square(np.square(mask))


def _smooth_patch(patch: np.ndarray) -> np.ndarray:
    if np is None:
        raise RuntimeError("numpy no está disponible para suavizado de terreno.")
    if uniform_filter is not None:
        return uniform_filter(patch, size=3, mode="nearest").astype(np.float32)
    padded = np.pad(patch, 1, mode="edge")
    result = np.zeros_like(patch)
    for offset_y in range(3):
        for offset_x in range(3):
            result += padded[offset_y:offset_y + patch.shape[0], offset_x:offset_x + patch.shape[1]]
    return (result / 9.0).astype(np.float32)
