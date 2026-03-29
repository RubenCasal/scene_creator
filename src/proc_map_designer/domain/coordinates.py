from __future__ import annotations

from dataclasses import dataclass

from proc_map_designer.domain.project_state import MapSettings


@dataclass(slots=True)
class ViewportRect:
    x: float
    y: float
    width: float
    height: float


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def map_rect_in_viewport(
    viewport_width: float,
    viewport_height: float,
    map_settings: MapSettings,
) -> ViewportRect:
    if viewport_width <= 0 or viewport_height <= 0:
        raise ValueError("El viewport debe tener dimensiones positivas.")

    map_width = map_settings.logical_width
    map_height = map_settings.logical_height
    scale = min(viewport_width / map_width, viewport_height / map_height)

    draw_width = map_width * scale
    draw_height = map_height * scale
    offset_x = (viewport_width - draw_width) / 2.0
    offset_y = (viewport_height - draw_height) / 2.0
    return ViewportRect(x=offset_x, y=offset_y, width=draw_width, height=draw_height)


def scene_to_mask(scene_x: float, scene_y: float, map_settings: MapSettings) -> tuple[int, int]:
    map_width = map_settings.logical_width
    map_height = map_settings.logical_height
    mask_width = map_settings.mask_width
    mask_height = map_settings.mask_height

    normalized_x = (scene_x + map_width / 2.0) / map_width
    normalized_y = (map_height / 2.0 - scene_y) / map_height

    normalized_x = _clamp(normalized_x, 0.0, 1.0)
    normalized_y = _clamp(normalized_y, 0.0, 1.0)

    max_x = max(mask_width - 1, 1)
    max_y = max(mask_height - 1, 1)
    mask_x = int(round(normalized_x * max_x))
    mask_y = int(round(normalized_y * max_y))
    return mask_x, mask_y


def mask_to_scene(mask_x: int, mask_y: int, map_settings: MapSettings) -> tuple[float, float]:
    mask_width = map_settings.mask_width
    mask_height = map_settings.mask_height
    max_x = max(mask_width - 1, 1)
    max_y = max(mask_height - 1, 1)

    normalized_x = _clamp(mask_x / max_x, 0.0, 1.0)
    normalized_y = _clamp(mask_y / max_y, 0.0, 1.0)

    scene_x = normalized_x * map_settings.logical_width - map_settings.logical_width / 2.0
    scene_y = map_settings.logical_height / 2.0 - normalized_y * map_settings.logical_height
    return scene_x, scene_y


def viewport_to_scene(
    viewport_x: float,
    viewport_y: float,
    viewport_width: float,
    viewport_height: float,
    map_settings: MapSettings,
) -> tuple[float, float]:
    rect = map_rect_in_viewport(viewport_width, viewport_height, map_settings)

    if rect.width <= 0 or rect.height <= 0:
        return 0.0, 0.0

    normalized_x = (viewport_x - rect.x) / rect.width
    normalized_y = (viewport_y - rect.y) / rect.height
    normalized_x = _clamp(normalized_x, 0.0, 1.0)
    normalized_y = _clamp(normalized_y, 0.0, 1.0)

    scene_x = normalized_x * map_settings.logical_width - map_settings.logical_width / 2.0
    scene_y = map_settings.logical_height / 2.0 - normalized_y * map_settings.logical_height
    return scene_x, scene_y

