from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from proc_map_designer.domain.models import CollectionNode
from proc_map_designer.domain.validators import (
    require_bool,
    require_float,
    require_int,
    require_list,
    require_mapping,
    require_string,
)

PROJECT_SCHEMA_VERSION = 1


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

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MapSettings":
        mapping = require_mapping(data, "map_settings")
        return cls(
            logical_width=mapping.get("logical_width", 200.0),
            logical_height=mapping.get("logical_height", 200.0),
            logical_unit=mapping.get("logical_unit", "m"),
            mask_width=mapping.get("mask_width", 1024),
            mask_height=mapping.get("mask_height", 1024),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_width": self.logical_width,
            "logical_height": self.logical_height,
            "logical_unit": self.logical_unit,
            "mask_width": self.mask_width,
            "mask_height": self.mask_height,
        }


@dataclass(slots=True)
class LayerState:
    layer_id: str
    name: str
    visible: bool = True
    opacity: float = 1.0
    mask_data_path: str | None = None
    color_hex: str = ""

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

        return cls(
            layer_id=layer_id,
            name=name,
            visible=visible,
            opacity=opacity,
            mask_data_path=mask_data_path,
            color_hex=color_hex,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "name": self.name,
            "visible": self.visible,
            "opacity": self.opacity,
            "mask_data_path": self.mask_data_path,
            "color_hex": self.color_hex,
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
class ProjectState:
    schema_version: int
    project_id: str
    project_name: str
    source_blend: str
    blender_executable: str
    created_at: str
    updated_at: str
    collection_tree: list[CollectionNode] = field(default_factory=list)
    map_settings: MapSettings = field(default_factory=MapSettings)
    layers: list[LayerState] = field(default_factory=list)
    generation_settings: GenerationSettings = field(default_factory=GenerationSettings)

    @classmethod
    def create_new(
        cls,
        project_name: str = "Nuevo proyecto",
        source_blend: str = "",
        blender_executable: str = "",
    ) -> "ProjectState":
        now = utc_now_iso()
        return cls(
            schema_version=PROJECT_SCHEMA_VERSION,
            project_id=str(uuid4()),
            project_name=project_name,
            source_blend=source_blend,
            blender_executable=blender_executable,
            created_at=now,
            updated_at=now,
            collection_tree=[],
            map_settings=MapSettings(),
            layers=[],
            generation_settings=GenerationSettings(),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProjectState":
        mapping = require_mapping(data, "project_state")

        schema_version = require_int(mapping.get("schema_version"), "schema_version", min_value=1)
        if schema_version != PROJECT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version={schema_version} no soportada. Esperada: {PROJECT_SCHEMA_VERSION}."
            )

        raw_collections = require_list(mapping.get("collection_tree", []), "collection_tree")
        collection_tree: list[CollectionNode] = []
        for item in raw_collections:
            collection_tree.append(CollectionNode.from_dict(require_mapping(item, "collection_tree[]")))

        raw_layers = require_list(mapping.get("layers", []), "layers")
        layers = [LayerState.from_dict(require_mapping(item, "layers[]")) for item in raw_layers]

        raw_map_settings = mapping.get("map_settings", {})
        map_settings = MapSettings.from_dict(require_mapping(raw_map_settings, "map_settings"))

        raw_generation_settings = mapping.get("generation_settings", {})
        generation_settings = GenerationSettings.from_dict(
            require_mapping(raw_generation_settings, "generation_settings")
        )

        project_id = require_string(mapping.get("project_id"), "project_id")
        project_name = require_string(mapping.get("project_name", "Proyecto sin nombre"), "project_name")
        source_blend = require_string(mapping.get("source_blend", ""), "source_blend", allow_empty=True)
        blender_executable = require_string(
            mapping.get("blender_executable", ""),
            "blender_executable",
            allow_empty=True,
        )
        created_at = _validate_iso_timestamp(mapping.get("created_at"), "created_at")
        updated_at = _validate_iso_timestamp(mapping.get("updated_at"), "updated_at")

        return cls(
            schema_version=schema_version,
            project_id=project_id,
            project_name=project_name,
            source_blend=source_blend,
            blender_executable=blender_executable,
            created_at=created_at,
            updated_at=updated_at,
            collection_tree=collection_tree,
            map_settings=map_settings,
            layers=layers,
            generation_settings=generation_settings,
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
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "collection_tree": [node.to_dict() for node in self.collection_tree],
            "map_settings": self.map_settings.to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
            "generation_settings": self.generation_settings.to_dict(),
        }
