from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


EXPORT_PACKAGE_SCHEMA_VERSION = 1


@dataclass(slots=True)
class ExportLayerSettings:
    density: float
    min_distance: float
    allow_overlap: bool
    scale_min: float
    scale_max: float
    rotation_random_z: float
    seed: int
    priority: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "density": self.density,
            "min_distance": self.min_distance,
            "allow_overlap": self.allow_overlap,
            "scale_min": self.scale_min,
            "scale_max": self.scale_max,
            "rotation_random_z": self.rotation_random_z,
            "seed": self.seed,
            "priority": self.priority,
        }


@dataclass(slots=True)
class ExportLayer:
    category: str
    name: str
    blender_collection: str
    enabled: bool
    mask_path: str
    settings: ExportLayerSettings

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "name": self.name,
            "blender_collection": self.blender_collection,
            "enabled": self.enabled,
            "mask_path": self.mask_path,
            "settings": self.settings.to_dict(),
        }


@dataclass(slots=True)
class ExportMap:
    width: float
    height: float
    unit: str
    mask_resolution: dict[str, int]
    base_plane_object: str

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
        }


@dataclass(slots=True)
class ExportProject:
    project_id: str
    source_blend: str
    blender_executable: str
    output_blend: str
    map: ExportMap
    layers: list[ExportLayer] = field(default_factory=list)
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
        }
