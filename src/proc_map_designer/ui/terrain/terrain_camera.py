from __future__ import annotations

import math

import numpy as np


class OrbitCamera:
    def __init__(self) -> None:
        self.azimuth = 45.0
        self.elevation = 45.0
        self.distance = 250.0
        self.target = np.array([0.0, 0.0, 0.0], dtype=np.float32)

    def orbit(self, delta_az: float, delta_el: float) -> None:
        self.azimuth += delta_az
        self.elevation = max(5.0, min(89.0, self.elevation + delta_el))

    def pan(self, delta_x: float, delta_y: float) -> None:
        right = np.array([math.cos(math.radians(self.azimuth)), 0.0, -math.sin(math.radians(self.azimuth))], dtype=np.float32)
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.target += right * float(delta_x) + up * float(delta_y)

    def zoom(self, factor: float) -> None:
        self.distance = max(1.0, float(self.distance * factor))

    def frame_terrain(self, map_width: float, map_height: float, max_height: float) -> None:
        self.target = np.array([0.0, max_height * 0.25, 0.0], dtype=np.float32)
        self.distance = max(map_width, map_height) * 1.6 + max_height * 2.0
        self.azimuth = 45.0
        self.elevation = 35.0

    def view_matrix(self) -> np.ndarray:
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        eye = np.array(
            [
                self.target[0] + self.distance * math.cos(el) * math.cos(az),
                self.target[1] + self.distance * math.sin(el),
                self.target[2] + self.distance * math.cos(el) * math.sin(az),
            ],
            dtype=np.float32,
        )
        return look_at(eye, self.target, np.array([0.0, 1.0, 0.0], dtype=np.float32))

    def projection_matrix(self, aspect: float) -> np.ndarray:
        return perspective(45.0, aspect, 0.1, 5000.0)

    def mvp(self, aspect: float) -> np.ndarray:
        return self.projection_matrix(aspect) @ self.view_matrix()

    def unproject_ray(self, ndc_x: float, ndc_y: float, aspect: float) -> tuple[np.ndarray, np.ndarray]:
        proj = self.projection_matrix(aspect)
        view = self.view_matrix()
        inv = np.linalg.inv(proj @ view)
        near = inv @ np.array([ndc_x, ndc_y, -1.0, 1.0], dtype=np.float32)
        far = inv @ np.array([ndc_x, ndc_y, 1.0, 1.0], dtype=np.float32)
        near /= near[3]
        far /= far[3]
        origin = near[:3]
        direction = far[:3] - near[:3]
        norm = np.linalg.norm(direction)
        if norm > 1e-6:
            direction /= norm
        return origin.astype(np.float32), direction.astype(np.float32)


def perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / math.tan(math.radians(fov_deg) * 0.5)
    matrix = np.zeros((4, 4), dtype=np.float32)
    matrix[0, 0] = f / max(aspect, 1e-6)
    matrix[1, 1] = f
    matrix[2, 2] = (far + near) / (near - far)
    matrix[2, 3] = (2.0 * far * near) / (near - far)
    matrix[3, 2] = -1.0
    return matrix


def look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    forward = target - eye
    forward /= max(np.linalg.norm(forward), 1e-6)
    right = np.cross(forward, up)
    right /= max(np.linalg.norm(right), 1e-6)
    true_up = np.cross(right, forward)
    matrix = np.identity(4, dtype=np.float32)
    matrix[0, :3] = right
    matrix[1, :3] = true_up
    matrix[2, :3] = -forward
    matrix[0, 3] = -float(np.dot(right, eye))
    matrix[1, 3] = -float(np.dot(true_up, eye))
    matrix[2, 3] = float(np.dot(forward, eye))
    return matrix
