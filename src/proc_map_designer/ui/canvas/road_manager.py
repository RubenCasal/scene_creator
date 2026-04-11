from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF

from proc_map_designer.domain.project_state import (
    MapSettings,
    RoadGeneratorSettings,
    RoadPoint,
    RoadState,
    RoadStyleSettings,
)


@dataclass(slots=True)
class RoadDraft:
    road_id: str
    name: str
    points: list[RoadPoint]
    width: float
    profile: str


class RoadManager:
    _MIN_POINT_DISTANCE = 1.5
    _SIMPLIFY_EPSILON = 1.25
    _SMOOTHING_ITERATIONS = 1

    def __init__(self, map_settings: MapSettings) -> None:
        self._map_settings = map_settings
        self._roads: list[RoadState] = []
        self._draft: RoadDraft | None = None
        self._next_index = 1

    @property
    def map_settings(self) -> MapSettings:
        return self._map_settings

    def set_map_settings(self, map_settings: MapSettings) -> None:
        self._map_settings = map_settings

    def all_roads(self) -> list[RoadState]:
        return list(self._roads)

    def has_roads(self) -> bool:
        return bool(self._roads)

    def get_road(self, road_id: str) -> RoadState | None:
        for road in self._roads:
            if road.road_id == road_id:
                return road
        return None

    def set_road_visibility(self, road_id: str, visible: bool) -> None:
        road = self.get_road(road_id)
        if road is None:
            return
        road.visible = bool(visible)

    def load_from_project_roads(self, roads: list[RoadState]) -> None:
        self._roads = list(roads)
        self._draft = None
        self._next_index = len(self._roads) + 1

    def snapshot_road_states(self) -> list[RoadState]:
        return [
            RoadState(
                road_id=road.road_id,
                name=road.name,
                visible=road.visible,
                closed=road.closed,
                points=[RoadPoint(x=point.x, y=point.y) for point in road.points],
                style=RoadStyleSettings(
                    width=road.style.width,
                    resolution=road.style.resolution,
                    profile=road.style.profile,
                ),
                generator=RoadGeneratorSettings(
                    enabled=road.generator.enabled,
                    seed=road.generator.seed,
                    geometry_nodes_asset_path=road.generator.geometry_nodes_asset_path,
                    material_library_blend_path=road.generator.material_library_blend_path,
                ),
            )
            for road in self._roads
        ]

    def clear(self) -> None:
        self._roads.clear()
        self._draft = None
        self._next_index = 1

    def begin_stroke(self, scene_point: QPointF, width: float, profile: str) -> None:
        road_id = f"road/{self._next_index:03d}"
        self._next_index += 1
        point = self._scene_to_road_point(scene_point)
        self._draft = RoadDraft(
            road_id=road_id,
            name=road_id,
            points=[point],
            width=max(0.01, float(width)),
            profile=profile,
        )

    def extend_stroke(self, scene_point: QPointF) -> bool:
        if self._draft is None:
            return False
        point = self._scene_to_road_point(scene_point)
        previous = self._draft.points[-1]
        if _point_distance(previous, point) < self._MIN_POINT_DISTANCE:
            return False
        self._draft.points.append(point)
        return True

    def end_stroke(self, scene_point: QPointF) -> RoadState | None:
        if self._draft is None:
            return None
        self.extend_stroke(scene_point)
        draft = self._draft
        self._draft = None
        if len(draft.points) < 2:
            return None
        processed_points = _process_stroke_points(
            draft.points,
            simplify_epsilon=self._SIMPLIFY_EPSILON,
            smoothing_iterations=self._SMOOTHING_ITERATIONS,
        )
        if len(processed_points) < 2:
            return None
        road = RoadState(
            road_id=draft.road_id,
            name=draft.name,
            points=processed_points,
            style=RoadStyleSettings(width=draft.width, profile=draft.profile),
        )
        self._roads.append(road)
        return road

    def cancel_draft(self) -> None:
        self._draft = None

    def remove_last_road(self) -> RoadState | None:
        if not self._roads:
            return None
        return self._roads.pop()

    def road_scene_paths(self) -> list[tuple[RoadState, list[QPointF]]]:
        return [(road, [self._road_point_to_scene(point) for point in road.points]) for road in self._roads if road.visible]

    def draft_scene_path(self) -> tuple[RoadDraft, list[QPointF]] | None:
        if self._draft is None:
            return None
        return self._draft, [self._road_point_to_scene(point) for point in self._draft.points]

    def _scene_to_road_point(self, scene_point: QPointF) -> RoadPoint:
        return RoadPoint(x=float(scene_point.x()), y=float(-scene_point.y()))

    def _road_point_to_scene(self, point: RoadPoint) -> QPointF:
        return QPointF(float(point.x), float(-point.y))


def _process_stroke_points(
    points: list[RoadPoint],
    *,
    simplify_epsilon: float,
    smoothing_iterations: int,
) -> list[RoadPoint]:
    if len(points) < 3:
        return points
    simplified = _ramer_douglas_peucker(points, simplify_epsilon)
    smoothed = simplified
    for _ in range(max(0, smoothing_iterations)):
        smoothed = _chaikin_smooth(smoothed)
    return _dedupe_points(smoothed)


def _ramer_douglas_peucker(points: list[RoadPoint], epsilon: float) -> list[RoadPoint]:
    if len(points) < 3:
        return points

    max_distance = -1.0
    split_index = -1
    start = points[0]
    end = points[-1]
    for index in range(1, len(points) - 1):
        distance = _perpendicular_distance(points[index], start, end)
        if distance > max_distance:
            max_distance = distance
            split_index = index

    if max_distance <= epsilon or split_index < 0:
        return [start, end]

    left = _ramer_douglas_peucker(points[: split_index + 1], epsilon)
    right = _ramer_douglas_peucker(points[split_index:], epsilon)
    return left[:-1] + right


def _chaikin_smooth(points: list[RoadPoint]) -> list[RoadPoint]:
    if len(points) < 3:
        return points
    result = [points[0]]
    for index in range(len(points) - 1):
        current = points[index]
        nxt = points[index + 1]
        q = RoadPoint(x=0.75 * current.x + 0.25 * nxt.x, y=0.75 * current.y + 0.25 * nxt.y)
        r = RoadPoint(x=0.25 * current.x + 0.75 * nxt.x, y=0.25 * current.y + 0.75 * nxt.y)
        result.extend((q, r))
    result.append(points[-1])
    return result


def _dedupe_points(points: list[RoadPoint]) -> list[RoadPoint]:
    if not points:
        return []
    unique = [points[0]]
    for point in points[1:]:
        if _point_distance(unique[-1], point) < 0.001:
            continue
        unique.append(point)
    return unique


def _point_distance(first: RoadPoint, second: RoadPoint) -> float:
    return math.hypot(second.x - first.x, second.y - first.y)


def _perpendicular_distance(point: RoadPoint, line_start: RoadPoint, line_end: RoadPoint) -> float:
    if line_start.x == line_end.x and line_start.y == line_end.y:
        return _point_distance(point, line_start)
    numerator = abs(
        (line_end.y - line_start.y) * point.x
        - (line_end.x - line_start.x) * point.y
        + line_end.x * line_start.y
        - line_end.y * line_start.x
    )
    denominator = math.hypot(line_end.y - line_start.y, line_end.x - line_start.x)
    return numerator / denominator
