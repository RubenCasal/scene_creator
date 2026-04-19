from __future__ import annotations

from math import ceil

try:  # pragma: no cover - optional dependency in test environment
    import numpy as np
except Exception:  # pragma: no cover
    np = None


def generate_fbm_noise(
    resolution: int,
    *,
    scale: float,
    strength: float,
    octaves: int,
    roughness: float,
    seed: int,
) -> np.ndarray:
    if np is None:
        raise RuntimeError("numpy no está disponible para generar ruido de terreno.")
    rng = np.random.default_rng(seed)
    result = np.zeros((resolution, resolution), dtype=np.float32)
    amplitude = 1.0
    total_amplitude = 0.0
    for octave in range(max(1, octaves)):
        frequency = max(1.0, scale * (2**octave))
        grid_size = max(2, int(ceil(resolution / frequency)) + 1)
        coarse = rng.random((grid_size, grid_size), dtype=np.float32)
        upsampled = _bilinear_resize(coarse, resolution)
        result += upsampled * amplitude
        total_amplitude += amplitude
        amplitude *= max(0.0, min(1.0, roughness))
    if total_amplitude > 0.0:
        result /= total_amplitude
    result -= float(result.min())
    max_value = float(result.max())
    if max_value > 0.0:
        result /= max_value
    return np.clip(result * strength, 0.0, 1.0).astype(np.float32)


def _bilinear_resize(source: np.ndarray, resolution: int) -> np.ndarray:
    if np is None:
        raise RuntimeError("numpy no está disponible para reescalar ruido de terreno.")
    src_h, src_w = source.shape
    xs = np.linspace(0.0, src_w - 1, resolution, dtype=np.float32)
    ys = np.linspace(0.0, src_h - 1, resolution, dtype=np.float32)
    x0 = np.floor(xs).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, src_w - 1)
    y0 = np.floor(ys).astype(np.int32)
    y1 = np.clip(y0 + 1, 0, src_h - 1)
    tx = xs - x0
    ty = ys - y0

    top = (1.0 - tx)[None, :] * source[y0][:, x0] + tx[None, :] * source[y0][:, x1]
    bottom = (1.0 - tx)[None, :] * source[y1][:, x0] + tx[None, :] * source[y1][:, x1]
    result = (1.0 - ty)[:, None] * top + ty[:, None] * bottom
    return result.astype(np.float32)
