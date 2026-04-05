from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from proc_map_designer.domain.export_package import EXPORT_PACKAGE_SCHEMA_VERSION
from proc_map_designer.domain.layer_palette import split_layer_id
from proc_map_designer.domain.validators import (
    require_bool,
    require_float,
    require_int,
    require_list,
    require_mapping,
    require_string,
)


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


@dataclass(slots=True)
class ExportLayerDefinition:
    layer_id: str
    category: str
    name: str
    enabled: bool
    mask_path: Path
    mask_exists: bool
    settings: ExportLayerSettings


@dataclass(slots=True)
class ExportMapInfo:
    width: float
    height: float
    unit: str
    mask_width: int
    mask_height: int
    base_plane_object: str


@dataclass(slots=True)
class ExportPackage:
    project_json: Path
    package_dir: Path
    project_id: str
    source_blend: str
    blender_executable: str
    output_blend: str
    map: ExportMapInfo
    layers: list[ExportLayerDefinition] = field(default_factory=list)


def load_export_package(project_json_path: Path, *, require_mask_files: bool = False) -> ExportPackage:
    absolute_path = project_json_path.resolve()
    package_dir = absolute_path.parent
    try:
        payload = json.loads(absolute_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"No se pudo leer '{absolute_path}': {exc}.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"project.json inválido: {exc}.") from exc

    root = require_mapping(payload, "project.json")
    schema_version = require_int(root.get("schema_version"), "schema_version")
    if schema_version != EXPORT_PACKAGE_SCHEMA_VERSION:
        raise ValueError(
            f"Schema no soportado {schema_version}. Esperado: {EXPORT_PACKAGE_SCHEMA_VERSION}."
        )

    project_id = require_string(root.get("project_id"), "project_id")
    source_blend = require_string(root.get("source_blend", ""), "source_blend")
    blender_executable = require_string(root.get("blender_executable", ""), "blender_executable")
    output_blend = require_string(root.get("output_blend", ""), "output_blend")

    map_payload = require_mapping(root.get("map", {}), "map")
    mask_resolution_payload = require_mapping(
        map_payload.get("mask_resolution", {}),
        "map.mask_resolution",
    )
    map_info = ExportMapInfo(
        width=require_float(map_payload.get("width"), "map.width", min_value=0.01),
        height=require_float(map_payload.get("height"), "map.height", min_value=0.01),
        unit=require_string(map_payload.get("unit", ""), "map.unit", allow_empty=True),
        mask_width=require_int(mask_resolution_payload.get("width"), "map.mask_resolution.width", min_value=1),
        mask_height=require_int(mask_resolution_payload.get("height"), "map.mask_resolution.height", min_value=1),
        base_plane_object=require_string(
            map_payload.get("base_plane_object"),
            "map.base_plane_object",
        ),
    )

    raw_layers = require_list(root.get("layers", []), "layers")
    layers: list[ExportLayerDefinition] = []

    for entry in raw_layers:
        layer_payload = require_mapping(entry, "layers[]")
        blender_collection = require_string(
            layer_payload.get("blender_collection"),
            "layers[].blender_collection",
        )
        category, _ = split_layer_id(blender_collection)
        mask_relative = require_string(layer_payload.get("mask_path"), "layers[].mask_path")
        mask_path = (package_dir / mask_relative).resolve()
        try:
            mask_path.relative_to(package_dir)
        except ValueError as exc:
            raise ValueError(
                f"La máscara '{mask_relative}' debe residir dentro del paquete exportado."
            ) from exc
        mask_exists = mask_path.exists()
        if require_mask_files and not mask_exists:
            raise ValueError(f"Archivo de máscara inexistente: {mask_path}")

        settings_payload = require_mapping(layer_payload.get("settings", {}), "layers[].settings")
        layer_settings = ExportLayerSettings(
            density=require_float(settings_payload.get("density"), "layers[].settings.density", min_value=0.0),
            min_distance=require_float(
                settings_payload.get("min_distance"),
                "layers[].settings.min_distance",
                min_value=0.0,
            ),
            allow_overlap=require_bool(
                settings_payload.get("allow_overlap"),
                "layers[].settings.allow_overlap",
            ),
            scale_min=require_float(settings_payload.get("scale_min"), "layers[].settings.scale_min"),
            scale_max=require_float(settings_payload.get("scale_max"), "layers[].settings.scale_max"),
            rotation_random_z=require_float(
                settings_payload.get("rotation_random_z"),
                "layers[].settings.rotation_random_z",
            ),
            seed=require_int(settings_payload.get("seed"), "layers[].settings.seed"),
            priority=require_int(settings_payload.get("priority"), "layers[].settings.priority"),
        )
        if layer_settings.scale_min > layer_settings.scale_max:
            raise ValueError(
                f"scale_min > scale_max en la capa '{blender_collection}'."
            )

        layer = ExportLayerDefinition(
            layer_id=blender_collection,
            category=category,
            name=require_string(layer_payload.get("name", blender_collection), "layers[].name", allow_empty=True)
            or blender_collection,
            enabled=require_bool(layer_payload.get("enabled", True), "layers[].enabled"),
            mask_path=mask_path,
            mask_exists=mask_exists,
            settings=layer_settings,
        )
        layers.append(layer)

    return ExportPackage(
        project_json=absolute_path,
        package_dir=package_dir,
        project_id=project_id,
        source_blend=source_blend,
        blender_executable=blender_executable,
        output_blend=output_blend,
        map=map_info,
        layers=layers,
    )
