from __future__ import annotations

from typing import Sequence


def decode_mask_values(
    *,
    width: int,
    height: int,
    channels: int,
    buffer: Sequence[float],
    flip_y: bool = True,
) -> tuple[float, ...]:
    if width <= 0 or height <= 0:
        raise ValueError("La resolución de la máscara debe ser positiva.")
    if channels <= 0:
        raise ValueError("La máscara debe tener al menos un canal.")

    total_values = width * height * channels
    if len(buffer) < total_values:
        raise ValueError("El buffer de máscara no contiene suficientes datos.")

    values: list[float] = []
    for row in range(height):
        src_row = height - 1 - row if flip_y else row
        for col in range(width):
            base_index = (src_row * width + col) * channels
            values.append(_decode_pixel(buffer, base_index, channels))
    return tuple(values)


def _decode_pixel(buffer: Sequence[float], base_index: int, channels: int) -> float:
    if channels == 1:
        luminance = float(buffer[base_index])
        alpha = 1.0
    elif channels == 2:
        luminance = float(buffer[base_index])
        alpha = float(buffer[base_index + 1])
    else:
        red = float(buffer[base_index])
        green = float(buffer[base_index + 1])
        blue = float(buffer[base_index + 2])
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        alpha = float(buffer[base_index + 3]) if channels >= 4 else 1.0

    return max(0.0, min(1.0, luminance * alpha))
