from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proc_map_designer.blender_bridge.terrain_sampler import TerrainSampler


def create_terrain_plane(width: float, height: float, export_subdivision: int, name: str) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    count = (2**export_subdivision) + 1
    half_width = width / 2.0
    half_height = height / 2.0
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for y in range(count):
        v = y / max(count - 1, 1)
        world_y = half_height - v * height
        for x in range(count):
            u = x / max(count - 1, 1)
            world_x = -half_width + u * width
            vertices.append((world_x, world_y, 0.0))
    for y in range(count - 1):
        for x in range(count - 1):
            i0 = y * count + x
            i1 = i0 + 1
            i2 = i0 + count
            i3 = i2 + 1
            faces.append((i0, i1, i3, i2))
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.uv_layers.new(name="UVMap")
    _assign_grid_uvs(mesh, count)
    obj = bpy.data.objects.new(name, mesh)
    obj["pm_runtime_plane"] = True
    obj["pm_category"] = "terrain"
    obj["pm_backend"] = "terrain"
    return obj


def displace_terrain_from_heightfield(
    obj: bpy.types.Object,
    *,
    heightfield_path: Path,
    max_height: float,
    map_width: float,
    map_height: float,
) -> None:
    sampler = TerrainSampler(heightfield_path, max_height, map_width, map_height)
    mesh = obj.data
    for vertex in mesh.vertices:
        vertex.co.z = sampler.sample_at(vertex.co.x, vertex.co.y)
    mesh.update()


def _assign_grid_uvs(mesh: bpy.types.Mesh, count: int) -> None:
    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        return
    vertex_uvs = []
    for y in range(count):
        v = y / max(count - 1, 1)
        for x in range(count):
            u = x / max(count - 1, 1)
            vertex_uvs.append((u, 1.0 - v))
    for loop in mesh.loops:
        uv_layer.data[loop.index].uv = Vector(vertex_uvs[loop.vertex_index])
