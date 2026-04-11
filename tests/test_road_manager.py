from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PySide6.QtCore import QPointF

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from proc_map_designer.domain.project_state import MapSettings, RoadPoint
from proc_map_designer.ui.canvas.road_manager import RoadManager, _process_stroke_points


class RoadManagerTests(unittest.TestCase):
    def test_extend_stroke_filters_nearby_points(self) -> None:
        manager = RoadManager(MapSettings())
        manager.begin_stroke(QPointF(0.0, 0.0), 6.0, "single")

        self.assertFalse(manager.extend_stroke(QPointF(0.5, 0.0)))
        self.assertTrue(manager.extend_stroke(QPointF(3.0, 0.0)))

    def test_end_stroke_simplifies_and_smooths_line(self) -> None:
        manager = RoadManager(MapSettings())
        manager.begin_stroke(QPointF(0.0, 0.0), 6.0, "single")
        manager.extend_stroke(QPointF(3.0, 0.2))
        manager.extend_stroke(QPointF(6.0, -0.1))
        manager.extend_stroke(QPointF(9.0, 0.1))

        road = manager.end_stroke(QPointF(12.0, 0.0))

        assert road is not None
        self.assertGreaterEqual(len(road.points), 2)
        self.assertEqual(road.points[0].x, 0.0)
        self.assertEqual(road.points[-1].x, 12.0)
        self.assertEqual(road.style.profile, "single")

    def test_process_stroke_points_reduces_zigzag_noise(self) -> None:
        raw_points = [
            RoadPoint(x=0.0, y=0.0),
            RoadPoint(x=1.0, y=0.4),
            RoadPoint(x=2.0, y=-0.3),
            RoadPoint(x=3.0, y=0.5),
            RoadPoint(x=4.0, y=-0.2),
            RoadPoint(x=5.0, y=0.0),
        ]

        processed = _process_stroke_points(raw_points, simplify_epsilon=0.6, smoothing_iterations=1)

        self.assertGreaterEqual(len(processed), 2)
        self.assertEqual(processed[0].x, 0.0)
        self.assertEqual(processed[-1].x, 5.0)
        if len(processed) > 2:
            self.assertLess(max(abs(point.y) for point in processed[1:-1]), 0.5)


if __name__ == "__main__":
    unittest.main()
