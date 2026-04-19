from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from proc_map_designer.domain.models import CollectionNode
from proc_map_designer.domain.terrain_state import TerrainSettings
from proc_map_designer.domain.validators import (
    require_bool,
    require_float,
    require_int,
    require_list,
    require_mapping,
    require_string,
)

PROJECT_SCHEMA_VERSION = 3


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_iso_timestamp(value: Any, field_name: str) -> str:
    timestamp = require_string(value, field_name)
    try:
        datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValueError(f"'{field_name}' debe estar en formato ISO-8601.") from exc
    return timestamp


@dataclass(slots=True)
class MapSettings:
    logical_width: float = 200.0
    logical_height: float = 200.0
    logical_unit: str = "m"
    mask_width: int = 1024
    mask_height: int = 1024
    base_plane_object: str = ""
    terrain_material_id: str = "terrain_grass"

    def __post_init__(self) -> None:
        self.logical_width = require_float(
            self.logical_width,
            "map_settings.logical_width",
            min_value=0.01,
            max_value=100000.0,
        )
        self.logical_height = require_float(
            self.logical_height,
            "map_settings.logical_height",
            min_value=0.01,
            max_value=100000.0,
        )
        self.logical_unit = require_string(self.logical_unit, "map_settings.logical_unit")
        self.mask_width = require_int(
            self.mask_width,
            "map_settings.mask_width",
            min_value=64,
            max_value=16384,
        )
        self.mask_height = require_int(
            self.mask_height,
            "map_settings.mask_height",
            min_value=64,
            max_value=16384,
        )
        self.base_plane_object = require_string(
            self.base_plane_object,
            "map_settings.base_plane_object",
            allow_empty=True,
        )
        self.terrain_material_id = require_string(
            self.terrain_material_id,
            "map_settings.terrain_material_id",
            allow_empty=False,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MapSettings":
        mapping = require_mapping(data, "map_settings")
        return cls(
            logical_width=mapping.get("logical_width", 200.0),
            logical_height=mapping.get("logical_height", 200.0),
            logical_unit=mapping.get("logical_unit", "m"),
            mask_width=mapping.get("mask_width", 1024),
            mask_height=mapping.get("mask_height", 1024),
            base_plane_object=mapping.get("base_plane_object", ""),
            terrain_material_id=mapping.get("terrain_material_id", "terrain_grass"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_width": self.logical_width,
            "logical_height": self.logical_height,
            "logical_unit": self.logical_unit,
            "mask_width": self.mask_width,
            "mask_height": self.mask_height,
            "base_plane_object": self.base_plane_object,
            "terrain_material_id": self.terrain_material_id,
        }


@dataclass(slots=True)
class LayerGenerationSettings:
    enabled: bool = True
    density: float = 1.0
    seed: int | None = None
    allow_overlap: bool = True
    min_distance: float = 0.0
    scale_min: float = 1.0
    scale_max: float = 1.0
    rotation_random_z: float = 180.0
    priority: int = 0
    bounding_radius: float | None = None
    slope_limit_deg: float | None = None
    max_count: int | None = None
    align_to_surface_normal: bool | None = None

    def __post_init__(self) -> None:
        self.enabled = require_bool(self.enabled, "layers[].generation_settings.enabled")
        self.density = require_float(
            self.density,
            "layers[].generation_settings.density",
            min_value=0.0,
        )

        if self.seed is None:
            seed = None
        else:
            seed = require_int(self.seed, "layers[].generation_settings.seed")
        self.seed = seed

        self.allow_overlap = require_bool(
            self.allow_overlap,
            "layers[].generation_settings.allow_overlap",
        )
        self.min_distance = require_float(
            self.min_distance,
            "layers[].generation_settings.min_distance",
            min_value=0.0,
        )
        self.scale_min = require_float(self.scale_min, "layers[].generation_settings.scale_min")
        self.scale_max = require_float(self.scale_max, "layers[].generation_settings.scale_max")
        if self.scale_min > self.scale_max:
            raise ValueError("'layers[].generation_settings.scale_min' debe ser <= 'scale_max'.")
        self.rotation_random_z = require_float(
            self.rotation_random_z,
            "layers[].generation_settings.rotation_random_z",
        )
        self.priority = require_int(self.priority, "layers[].generation_settings.priority")

        if self.bounding_radius is None:
            bounding_radius = None
        else:
            bounding_radius = require_float(
                self.bounding_radius,
                "layers[].generation_settings.bounding_radius",
                min_value=0.0,
            )
        self.bounding_radius = bounding_radius

        if self.slope_limit_deg is None:
            slope_limit_deg = None
        else:
            slope_limit_deg = require_float(
                self.slope_limit_deg,
                "layers[].generation_settings.slope_limit_deg",
                min_value=0.0,
            )
        self.slope_limit_deg = slope_limit_deg

        if self.max_count is None:
            max_count = None
        else:
            max_count = require_int(self.max_count, "layers[].generation_settings.max_count", min_value=0)
        self.max_count = max_count

        if self.align_to_surface_normal is None:
            align_to_surface_normal = None
        else:
            align_to_surface_normal = require_bool(
                self.align_to_surface_normal,
                "layers[].generation_settings.align_to_surface_normal",
            )
        self.align_to_surface_normal = align_to_surface_normal

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LayerGenerationSettings":
        mapping = require_mapping(data, "layers[].generation_settings")
        return cls(
            enabled=mapping.get("enabled", True),
            density=mapping.get("density", 1.0),
            seed=mapping.get("seed"),
            allow_overlap=mapping.get("allow_overlap", True),
            min_distance=mapping.get("min_distance", 0.0),
            scale_min=mapping.get("scale_min", 1.0),
            scale_max=mapping.get("scale_max", 1.0),
            rotation_random_z=mapping.get("rotation_random_z", 180.0),
            priority=mapping.get("priority", 0),
            bounding_radius=mapping.get("bounding_radius"),
            slope_limit_deg=mapping.get("slope_limit_deg"),
            max_count=mapping.get("max_count"),
            align_to_surface_normal=mapping.get("align_to_surface_normal"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "density": self.density,
            "seed": self.seed,
            "allow_overlap": self.allow_overlap,
            "min_distance": self.min_distance,
            "scale_min": self.scale_min,
            "scale_max": self.scale_max,
            "rotation_random_z": self.rotation_random_z,
            "priority": self.priority,
            "bounding_radius": self.bounding_radius,
            "slope_limit_deg": self.slope_limit_deg,
            "max_count": self.max_count,
            "align_to_surface_normal": self.align_to_surface_normal,
        }


@dataclass(slots=True)
class LayerState:
    layer_id: str
    name: str
    visible: bool = True
    opacity: float = 1.0
    mask_data_path: str | None = None
    color_hex: str = ""
    generation_settings: LayerGenerationSettings = field(default_factory=LayerGenerationSettings)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LayerState":
        mapping = require_mapping(data, "layers[]")
        layer_id = require_string(mapping.get("layer_id"), "layers[].layer_id")
        name = require_string(mapping.get("name"), "layers[].name")
        visible = require_bool(mapping.get("visible", True), "layers[].visible")
        opacity = require_float(mapping.get("opacity", 1.0), "layers[].opacity", min_value=0.0, max_value=1.0)

        mask_path_raw = mapping.get("mask_data_path", None)
        if mask_path_raw is None:
            mask_data_path = None
        else:
            mask_data_path = require_string(mask_path_raw, "layers[].mask_data_path", allow_empty=True)

        raw_color = mapping.get("color_hex", "")
        if raw_color is None:
            color_hex = ""
        else:
            color_hex = require_string(raw_color, "layers[].color_hex", allow_empty=True)

        raw_generation_settings = mapping.get("generation_settings", {})
        if raw_generation_settings is None:
            generation_settings = LayerGenerationSettings()
        else:
            generation_settings = LayerGenerationSettings.from_dict(
                require_mapping(raw_generation_settings, "layers[].generation_settings")
            )

        return cls(
            layer_id=layer_id,
            name=name,
            visible=visible,
            opacity=opacity,
            mask_data_path=mask_data_path,
            color_hex=color_hex,
            generation_settings=generation_settings,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "name": self.name,
            "visible": self.visible,
            "opacity": self.opacity,
            "mask_data_path": self.mask_data_path,
            "color_hex": self.color_hex,
            "generation_settings": self.generation_settings.to_dict(),
        }


@dataclass(slots=True)
class RoadPoint:
    x: float
    y: float

    def __post_init__(self) -> None:
        self.x = require_float(self.x, "roads[].points[].x")
        self.y = require_float(self.y, "roads[].points[].y")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoadPoint":
        mapping = require_mapping(data, "roads[].points[]")
        return cls(
            x=mapping.get("x", 0.0),
            y=mapping.get("y", 0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
        }


@dataclass(slots=True)
class RoadStyleSettings:
    width: float = 6.0
    resolution: int = 24
    profile: str = "single"

    def __post_init__(self) -> None:
        self.width = require_float(self.width, "roads[].style.width", min_value=0.01)
        self.resolution = require_int(self.resolution, "roads[].style.resolution", min_value=1, max_value=4096)
        self.profile = require_string(self.profile, "roads[].style.profile")
        if self.profile not in {"single", "double"}:
            raise ValueError("roads[].style.profile debe ser 'single' o 'double'.")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoadStyleSettings":
        mapping = require_mapping(data, "roads[].style")
        return cls(
            width=mapping.get("width", 6.0),
            resolution=mapping.get("resolution", 24),
            profile=mapping.get("profile", "single"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "resolution": self.resolution,
            "profile": self.profile,
        }


@dataclass(slots=True)
class RoadGeneratorSettings:
    enabled: bool = True
    seed: int | None = None
    geometry_nodes_asset_path: str = "geometry_nodes_procedural_road.json"
    material_library_blend_path: str = "blender_defaults/road.blend"

    def __post_init__(self) -> None:
        self.enabled = require_bool(self.enabled, "roads[].generator.enabled")
        if self.seed is None:
            seed = None
        else:
            seed = require_int(self.seed, "roads[].generator.seed")
        self.seed = seed
        self.geometry_nodes_asset_path = require_string(
            self.geometry_nodes_asset_path,
            "roads[].generator.geometry_nodes_asset_path",
        )
        self.material_library_blend_path = require_string(
            self.material_library_blend_path,
            "roads[].generator.material_library_blend_path",
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoadGeneratorSettings":
        mapping = require_mapping(data, "roads[].generator")
        return cls(
            enabled=mapping.get("enabled", True),
            seed=mapping.get("seed"),
            geometry_nodes_asset_path=mapping.get(
                "geometry_nodes_asset_path",
                "geometry_nodes_procedural_road.json",
            ),
            material_library_blend_path=mapping.get(
                "material_library_blend_path",
                "blender_defaults/road.blend",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "seed": self.seed,
            "geometry_nodes_asset_path": self.geometry_nodes_asset_path,
            "material_library_blend_path": self.material_library_blend_path,
        }


@dataclass(slots=True)
class RoadState:
    road_id: str
    name: str
    visible: bool = True
    closed: bool = False
    points: list[RoadPoint] = field(default_factory=list)
    style: RoadStyleSettings = field(default_factory=RoadStyleSettings)
    generator: RoadGeneratorSettings = field(default_factory=RoadGeneratorSettings)

    def __post_init__(self) -> None:
        self.road_id = require_string(self.road_id, "roads[].road_id")
        self.name = require_string(self.name, "roads[].name", allow_empty=True) or self.road_id
        self.visible = require_bool(self.visible, "roads[].visible")
        self.closed = require_bool(self.closed, "roads[].closed")
        self.points = [
            point if isinstance(point, RoadPoint) else RoadPoint.from_dict(require_mapping(point, "roads[].points[]"))
            for point in require_list(self.points, "roads[].points")
        ]
        if len(self.points) < 2:
            raise ValueError("Cada road debe tener al menos 2 puntos.")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoadState":
        mapping = require_mapping(data, "roads[]")
        raw_style = mapping.get("style", {})
        raw_generator = mapping.get("generator", {})
        return cls(
            road_id=require_string(mapping.get("road_id"), "roads[].road_id"),
            name=require_string(mapping.get("name", ""), "roads[].name", allow_empty=True),
            visible=require_bool(mapping.get("visible", True), "roads[].visible"),
            closed=require_bool(mapping.get("closed", False), "roads[].closed"),
            points=[RoadPoint.from_dict(require_mapping(item, "roads[].points[]")) for item in require_list(mapping.get("points", []), "roads[].points")],
            style=RoadStyleSettings.from_dict(require_mapping(raw_style, "roads[].style")),
            generator=RoadGeneratorSettings.from_dict(require_mapping(raw_generator, "roads[].generator")),
        )

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
class GenerationSettings:
    seed: int | None = None
    randomize_seed: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GenerationSettings":
        mapping = require_mapping(data, "generation_settings")
        randomize_seed = require_bool(
            mapping.get("randomize_seed", True),
            "generation_settings.randomize_seed",
        )
        raw_seed = mapping.get("seed")
        if raw_seed is None:
            seed = None
        else:
            seed = require_int(raw_seed, "generation_settings.seed")

        return cls(seed=seed, randomize_seed=randomize_seed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "randomize_seed": self.randomize_seed,
        }


@dataclass(slots=True)
class LatestOutputInfo:
    backend_id: str = ""
    status: str = ""
    export_manifest_path: str = ""
    result_path: str = ""
    final_output_path: str = ""
    completed_at: str = ""
    error_message: str = ""
    used_layer_ids: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.backend_id = require_string(self.backend_id, "latest_output.backend_id", allow_empty=True)
        self.status = require_string(self.status, "latest_output.status", allow_empty=True)
        self.export_manifest_path = require_string(
            self.export_manifest_path,
            "latest_output.export_manifest_path",
            allow_empty=True,
        )
        self.result_path = require_string(self.result_path, "latest_output.result_path", allow_empty=True)
        self.final_output_path = require_string(
            self.final_output_path,
            "latest_output.final_output_path",
            allow_empty=True,
        )
        self.error_message = require_string(
            self.error_message,
            "latest_output.error_message",
            allow_empty=True,
        )
        self.used_layer_ids = [
            require_string(item, "latest_output.used_layer_ids[]") for item in require_list(self.used_layer_ids, "latest_output.used_layer_ids")
        ]
        self.validation_warnings = [
            require_string(item, "latest_output.validation_warnings[]", allow_empty=True)
            for item in require_list(self.validation_warnings, "latest_output.validation_warnings")
        ]

        if self.completed_at:
            self.completed_at = _validate_iso_timestamp(self.completed_at, "latest_output.completed_at")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LatestOutputInfo":
        mapping = require_mapping(data, "latest_output")
        return cls(
            backend_id=mapping.get("backend_id", ""),
            status=mapping.get("status", ""),
            export_manifest_path=mapping.get("export_manifest_path", ""),
            result_path=mapping.get("result_path", ""),
            final_output_path=mapping.get("final_output_path", ""),
            completed_at=mapping.get("completed_at", ""),
            error_message=mapping.get("error_message", ""),
            used_layer_ids=mapping.get("used_layer_ids", []),
            validation_warnings=mapping.get("validation_warnings", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "status": self.status,
            "export_manifest_path": self.export_manifest_path,
            "result_path": self.result_path,
            "final_output_path": self.final_output_path,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "used_layer_ids": list(self.used_layer_ids),
            "validation_warnings": list(self.validation_warnings),
        }


@dataclass(slots=True)
class ProjectState:
    schema_version: int
    project_id: str
    project_name: str
    source_blend: str
    blender_executable: str
    created_at: str
    updated_at: str
    output_blend: str = ""
    collection_tree: list[CollectionNode] = field(default_factory=list)
    map_settings: MapSettings = field(default_factory=MapSettings)
    terrain_settings: TerrainSettings = field(default_factory=TerrainSettings)
    layers: list[LayerState] = field(default_factory=list)
    roads: list[RoadState] = field(default_factory=list)
    generation_settings: GenerationSettings = field(default_factory=GenerationSettings)
    latest_output: LatestOutputInfo | None = None

    @classmethod
    def create_new(
        cls,
        project_name: str = "Nuevo proyecto",
        source_blend: str = "",
        blender_executable: str = "",
        output_blend: str = "",
    ) -> "ProjectState":
        now = utc_now_iso()
        return cls(
            schema_version=PROJECT_SCHEMA_VERSION,
            project_id=str(uuid4()),
            project_name=project_name,
            source_blend=source_blend,
            blender_executable=blender_executable,
            output_blend=output_blend,
            created_at=now,
            updated_at=now,
            collection_tree=[],
            map_settings=MapSettings(),
            terrain_settings=TerrainSettings(),
            layers=[],
            roads=[],
            generation_settings=GenerationSettings(),
            latest_output=None,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProjectState":
        mapping = require_mapping(data, "project_state")

        schema_version = require_int(mapping.get("schema_version"), "schema_version", min_value=1)
        if schema_version not in {1, 2, PROJECT_SCHEMA_VERSION}:
            raise ValueError(
                f"schema_version={schema_version} no soportada. Esperada: {PROJECT_SCHEMA_VERSION}."
            )

        raw_collections = require_list(mapping.get("collection_tree", []), "collection_tree")
        collection_tree: list[CollectionNode] = []
        for item in raw_collections:
            collection_tree.append(CollectionNode.from_dict(require_mapping(item, "collection_tree[]")))

        raw_layers = require_list(mapping.get("layers", []), "layers")
        layers = [LayerState.from_dict(require_mapping(item, "layers[]")) for item in raw_layers]

        raw_roads = require_list(mapping.get("roads", []), "roads")
        roads = [RoadState.from_dict(require_mapping(item, "roads[]")) for item in raw_roads]

        raw_map_settings = mapping.get("map_settings", {})
        map_settings = MapSettings.from_dict(require_mapping(raw_map_settings, "map_settings"))

        raw_terrain_settings = mapping.get("terrain_settings", {})
        terrain_settings = TerrainSettings.from_dict(require_mapping(raw_terrain_settings, "terrain_settings"))

        raw_generation_settings = mapping.get("generation_settings", {})
        generation_settings = GenerationSettings.from_dict(
            require_mapping(raw_generation_settings, "generation_settings")
        )

        raw_latest_output = mapping.get("latest_output")
        if raw_latest_output is None:
            latest_output = None
        else:
            latest_output = LatestOutputInfo.from_dict(require_mapping(raw_latest_output, "latest_output"))

        project_id = require_string(mapping.get("project_id"), "project_id")
        project_name = require_string(mapping.get("project_name", "Proyecto sin nombre"), "project_name")
        source_blend = require_string(mapping.get("source_blend", ""), "source_blend", allow_empty=True)
        blender_executable = require_string(
            mapping.get("blender_executable", ""),
            "blender_executable",
            allow_empty=True,
        )
        output_blend = require_string(mapping.get("output_blend", ""), "output_blend", allow_empty=True)
        created_at = _validate_iso_timestamp(mapping.get("created_at"), "created_at")
        updated_at = _validate_iso_timestamp(mapping.get("updated_at"), "updated_at")

        return cls(
            schema_version=schema_version,
            project_id=project_id,
            project_name=project_name,
            source_blend=source_blend,
            blender_executable=blender_executable,
            output_blend=output_blend,
            created_at=created_at,
            updated_at=updated_at,
            collection_tree=collection_tree,
            map_settings=map_settings,
            terrain_settings=terrain_settings,
            layers=layers,
            roads=roads,
            generation_settings=generation_settings,
            latest_output=latest_output,
        )

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "source_blend": self.source_blend,
            "blender_executable": self.blender_executable,
            "output_blend": self.output_blend,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "collection_tree": [node.to_dict() for node in self.collection_tree],
            "map_settings": self.map_settings.to_dict(),
            "terrain_settings": self.terrain_settings.to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
            "roads": [road.to_dict() for road in self.roads],
            "generation_settings": self.generation_settings.to_dict(),
            "latest_output": self.latest_output.to_dict() if self.latest_output else None,
        }
