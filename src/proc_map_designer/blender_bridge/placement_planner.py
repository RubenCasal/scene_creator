from __future__ import annotations

import hashlib
import bisect
import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


@dataclass(slots=True)
class MapDimensions:
    width: float
    height: float
    mask_width: int
    mask_height: int


@dataclass(slots=True)
class MaskField:
    width: int
    height: int
    values: Sequence[float]

    def __post_init__(self) -> None:
        expected = self.width * self.height
        if len(self.values) < expected:
            raise ValueError("MaskField no tiene datos suficientes para la resolución declarada.")

    def value_at(self, x: int, y: int) -> float:
        index = y * self.width + x
        return float(self.values[index])


@dataclass(slots=True)
class Placement:
    x: float
    y: float
    rotation_z_deg: float
    scale: float
    weight: float


@dataclass(slots=True)
class LayerPlanInput:
    layer_id: str
    category: str
    enabled: bool
    settings: Any
    mask: MaskField


@dataclass(slots=True)
class LayerPlacementPlan:
    layer_id: str
    category: str
    placements: list[Placement] = field(default_factory=list)


# v1 tuning: density=1 should be sparse on a 200x200 logical map instead of exploding into
# tens of thousands of instances. We treat density as instances per 100 logical square units.
DENSITY_AREA_UNIT = 100.0


@dataclass(slots=True)
class SpatialIndex:
    cell_size: float
    _cells: dict[tuple[int, int], list[tuple[float, float]]] = field(default_factory=dict)

    def has_conflict(self, x: float, y: float, min_distance_sq: float) -> bool:
        if min_distance_sq <= 0.0:
            return False
        cell_x, cell_y = self._cell_key(x, y)
        for neighbor_x in range(cell_x - 1, cell_x + 2):
            for neighbor_y in range(cell_y - 1, cell_y + 2):
                for existing_x, existing_y in self._cells.get((neighbor_x, neighbor_y), []):
                    dx = x - existing_x
                    dy = y - existing_y
                    if dx * dx + dy * dy < min_distance_sq:
                        return True
        return False

    def add(self, x: float, y: float) -> None:
        key = self._cell_key(x, y)
        self._cells.setdefault(key, []).append((x, y))

    def extend(self, points: Iterable[tuple[float, float]]) -> None:
        for x, y in points:
            self.add(x, y)

    def _cell_key(self, x: float, y: float) -> tuple[int, int]:
        if self.cell_size <= 0.0:
            return (0, 0)
        return (math.floor(x / self.cell_size), math.floor(y / self.cell_size))


def derive_layer_seed(project_id: str, layer_id: str, layer_seed: int) -> int:
    seed_text = f"{project_id}:{layer_id}:{layer_seed}"
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def plan_generation(
    project_id: str,
    map_dims: MapDimensions,
    layers: Sequence[LayerPlanInput],
) -> list[LayerPlacementPlan]:
    if map_dims.mask_width <= 0 or map_dims.mask_height <= 0:
        raise ValueError("La resolución de máscara del mapa debe ser positiva.")

    sorted_layers = sorted(
        layers,
        key=lambda layer: (-getattr(layer.settings, "priority", 0), layer.layer_id.lower()),
    )
    global_points: list[tuple[float, float]] = []
    plans: list[LayerPlacementPlan] = []

    for layer in sorted_layers:
        plan = LayerPlacementPlan(layer_id=layer.layer_id, category=layer.category)
        plans.append(plan)
        if not layer.enabled:
            continue
        if layer.mask.width != map_dims.mask_width or layer.mask.height != map_dims.mask_height:
            raise ValueError(
                f"La máscara de '{layer.layer_id}' no coincide con la resolución del mapa."
            )

        rng = random.Random(derive_layer_seed(project_id, layer.layer_id, layer.settings.seed))
        placements = _plan_single_layer(layer, map_dims, rng, global_points)
        plan.placements.extend(placements)
        if not layer.settings.allow_overlap and placements:
            global_points.extend((placement.x, placement.y) for placement in placements)

    return plans


def _plan_single_layer(
    layer: LayerPlanInput,
    map_dims: MapDimensions,
    rng: random.Random,
    global_points: list[tuple[float, float]],
) -> list[Placement]:
    mask = layer.mask
    density = max(0.0, float(layer.settings.density))
    if density <= 0.0:
        return []

    min_distance = max(0.0, float(layer.settings.min_distance))
    min_distance_sq = min_distance * min_distance
    local_index = SpatialIndex(cell_size=min_distance if min_distance > 0.0 else 1.0)
    placements: list[Placement] = []

    cell_area = (map_dims.width * map_dims.height) / float(mask.width * mask.height)
    cumulative_weights, weighted_cells = _weighted_cells(mask)
    if not weighted_cells:
        return []

    total_weight = cumulative_weights[-1]
    if total_weight <= 0.0:
        return []

    active_area = cell_area * total_weight
    expected_spawn_total = density * (active_area / DENSITY_AREA_UNIT)
    spawn_count = math.floor(expected_spawn_total)
    if rng.random() < expected_spawn_total - spawn_count:
        spawn_count += 1
    if spawn_count <= 0:
        return []

    for _ in range(spawn_count):
        x, y, intensity = _sample_weighted_cell(cumulative_weights, weighted_cells, total_weight, rng)
        offset_x = rng.uniform(-0.5, 0.5)
        offset_y = rng.uniform(-0.5, 0.5)
        scene_x, scene_y = mask_to_scene(x + offset_x, y + offset_y, map_dims)
        if min_distance_sq > 0.0:
            if not layer.settings.allow_overlap and _has_conflict(scene_x, scene_y, global_points, min_distance_sq):
                continue
            if local_index.has_conflict(scene_x, scene_y, min_distance_sq):
                continue

        rotation_deg = 0.0
        rotation_range = float(layer.settings.rotation_random_z)
        if rotation_range != 0.0:
            rotation_deg = rng.uniform(-rotation_range, rotation_range)

        scale_min = float(layer.settings.scale_min)
        scale_max = float(layer.settings.scale_max)
        if scale_min > scale_max:
            scale_min, scale_max = scale_max, scale_min
        if scale_max == scale_min:
            scale_value = scale_min
        else:
            scale_value = rng.uniform(scale_min, scale_max)

        placements.append(
            Placement(
                x=scene_x,
                y=scene_y,
                rotation_z_deg=rotation_deg,
                scale=max(0.0, scale_value),
                weight=intensity,
            )
        )
        local_index.add(scene_x, scene_y)

    return placements


def mask_to_scene(mask_x: float, mask_y: float, dims: MapDimensions) -> tuple[float, float]:
    max_x = max(dims.mask_width - 1, 1)
    max_y = max(dims.mask_height - 1, 1)
    normalized_x = min(max(mask_x / max_x, 0.0), 1.0)
    normalized_y = min(max(mask_y / max_y, 0.0), 1.0)
    scene_x = normalized_x * dims.width - dims.width / 2.0
    scene_y = dims.height / 2.0 - normalized_y * dims.height
    return scene_x, scene_y


def _weighted_cells(mask: MaskField) -> tuple[list[float], list[tuple[int, int, float]]]:
    cumulative_weights: list[float] = []
    weighted: list[tuple[int, int, float]] = []
    cumulative = 0.0
    for y in range(mask.height):
        for x in range(mask.width):
            intensity = max(0.0, min(1.0, mask.value_at(x, y)))
            if intensity <= 0.0:
                continue
            cumulative += intensity
            cumulative_weights.append(cumulative)
            weighted.append((x, y, intensity))
    return cumulative_weights, weighted


def _sample_weighted_cell(
    cumulative_weights: Sequence[float],
    weighted_cells: Sequence[tuple[int, int, float]],
    total_weight: float,
    rng: random.Random,
) -> tuple[int, int, float]:
    threshold = rng.uniform(0.0, total_weight)
    index = bisect.bisect_left(cumulative_weights, threshold)
    if index >= len(weighted_cells):
        index = len(weighted_cells) - 1
    x, y, intensity = weighted_cells[index]
    return x, y, intensity


def _has_conflict(
    candidate_x: float,
    candidate_y: float,
    points: Iterable[tuple[float, float]],
    min_distance_sq: float,
) -> bool:
    for existing_x, existing_y in points:
        dx = candidate_x - existing_x
        dy = candidate_y - existing_y
        if dx * dx + dy * dy < min_distance_sq:
            return True
    return False
