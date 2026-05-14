from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


EXPORT_PACKAGE_SCHEMA_VERSION = 5


@dataclass(slots=True)
class ExportLayerSettings:
    mode: str
    density: float
    min_distance: float
    allow_overlap: bool
    scale_min: float
    scale_max: float
    rotation_random_z: float
    seed: int
    priority: int
    bounding_radius: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "density": self.density,
            "min_distance": self.min_distance,
            "allow_overlap": self.allow_overlap,
            "scale_min": self.scale_min,
            "scale_max": self.scale_max,
            "rotation_random_z": self.rotation_random_z,
            "seed": self.seed,
            "priority": self.priority,
            "bounding_radius": self.bounding_radius,
        }


@dataclass(slots=True)
class ExportLayer:
    category: str
    name: str
    blender_collection: str
    enabled: bool
    generation_mode: str
    mask_path: str | None
    single_instances: list["ExportSingleInstancePlacement"]
    settings: ExportLayerSettings

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "name": self.name,
            "blender_collection": self.blender_collection,
            "enabled": self.enabled,
            "generation_mode": self.generation_mode,
            "mask_path": self.mask_path,
            "single_instances": [placement.to_dict() for placement in self.single_instances],
            "settings": self.settings.to_dict(),
        }


@dataclass(slots=True)
class ExportSingleInstancePlacement:
    x: float
    y: float
    rotation_z_deg: float
    scale: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "rotation_z_deg": self.rotation_z_deg,
            "scale": self.scale,
        }


@dataclass(slots=True)
class ExportRoadPoint:
    x: float
    y: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
        }


@dataclass(slots=True)
class ExportRoadStyle:
    width: float
    resolution: int
    profile: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "resolution": self.resolution,
            "profile": self.profile,
        }


@dataclass(slots=True)
class ExportRoadGenerator:
    seed: int
    geometry_nodes_asset_path: str
    material_library_blend_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "geometry_nodes_asset_path": self.geometry_nodes_asset_path,
            "material_library_blend_path": self.material_library_blend_path,
        }


@dataclass(slots=True)
class ExportRoad:
    road_id: str
    name: str
    visible: bool
    closed: bool
    points: list[ExportRoadPoint]
    style: ExportRoadStyle
    generator: ExportRoadGenerator

    def to_dict(self) -> dict[str, Any]:
        return {
            "road_id": self.road_id,
            "name": self.name,
            "visible": self.visible,
            "closed": self.closed,
            "points": [point.to_dict() for point in self.points],
            "style": self.style.to_dict(),
            "generator": self.generator.to_dict(),
        }


@dataclass(slots=True)
class ExportMap:
    width: float
    height: float
    unit: str
    mask_resolution: dict[str, int]
    base_plane_object: str
    terrain_material_id: str
    terrain: "ExportTerrain"

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "unit": self.unit,
            "mask_resolution": {
                "width": self.mask_resolution["width"],
                "height": self.mask_resolution["height"],
            },
            "base_plane_object": self.base_plane_object,
            "terrain_material_id": self.terrain_material_id,
            "terrain": self.terrain.to_dict(),
        }


@dataclass(slots=True)
class ExportTerrain:
    enabled: bool
    max_height: float
    export_subdivision: int
    heightfield_resolution: int
    heightfield_path: str
    noise_enabled: bool
    noise_scale: float
    noise_strength: float
    noise_octaves: int
    noise_roughness: float
    noise_seed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_height": self.max_height,
            "export_subdivision": self.export_subdivision,
            "heightfield_resolution": self.heightfield_resolution,
            "heightfield_path": self.heightfield_path,
            "noise_enabled": self.noise_enabled,
            "noise_scale": self.noise_scale,
            "noise_strength": self.noise_strength,
            "noise_octaves": self.noise_octaves,
            "noise_roughness": self.noise_roughness,
            "noise_seed": self.noise_seed,
        }


@dataclass(slots=True)
class ExportProject:
    project_id: str
    source_blend: str
    blender_executable: str
    output_blend: str
    map: ExportMap
    layers: list[ExportLayer] = field(default_factory=list)
    roads: list[ExportRoad] = field(default_factory=list)
    schema_version: int = EXPORT_PACKAGE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "source_blend": self.source_blend,
            "blender_executable": self.blender_executable,
            "output_blend": self.output_blend,
            "map": self.map.to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
            "roads": [road.to_dict() for road in self.roads],
        }
