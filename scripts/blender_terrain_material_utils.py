from __future__ import annotations

from pathlib import Path

import bpy

from proc_map_designer.services.terrain_material_catalog import (
    TerrainMaterialCatalogError,
    get_catalog_entry,
    load_terrain_material_catalog,
)


TERRAIN_TEXTURE_WORLD_TILE_SIZE = 8.0


def apply_terrain_material_to_object(*, terrain_material_id: str, target_object: bpy.types.Object) -> bpy.types.Material:
    try:
        catalog = load_terrain_material_catalog()
        entry = get_catalog_entry(terrain_material_id, catalog)
    except TerrainMaterialCatalogError as exc:
        raise ValueError(str(exc)) from exc

    material = _append_material_from_blend(catalog.blend_path, entry.blend_material_name)
    if material is None:
        raise ValueError(
            f"No se pudo cargar el material de terreno '{entry.blend_material_name}' desde '{catalog.blend_path}'."
        )

    material = material.copy()
    material.name = f"PM_{entry.id}_{target_object.name}"
    _configure_terrain_material_mapping(material, target_object)

    if getattr(target_object, "data", None) is None or not hasattr(target_object.data, "materials"):
        raise ValueError(f"El objeto '{target_object.name}' no admite materiales.")

    materials = target_object.data.materials
    if len(materials) == 0:
        materials.append(material)
    else:
        materials[0] = material
    return material


def prepare_runtime_plane_as_terrain(
    *,
    terrain_material_id: str,
    runtime_plane: bpy.types.Object,
) -> bpy.types.Object:
    runtime_plane["pm_layer_id"] = "terrain/base_plane"
    runtime_plane["pm_category"] = "terrain"
    runtime_plane["pm_backend"] = "terrain_material"
    runtime_plane.hide_viewport = False
    runtime_plane.hide_render = False
    runtime_plane.hide_select = False
    runtime_plane.display_type = 'TEXTURED'
    apply_terrain_material_to_object(terrain_material_id=terrain_material_id, target_object=runtime_plane)
    return runtime_plane


def validate_terrain_material_id(terrain_material_id: str) -> None:
    try:
        catalog = load_terrain_material_catalog()
        entry = get_catalog_entry(terrain_material_id, catalog)
    except TerrainMaterialCatalogError as exc:
        raise ValueError(str(exc)) from exc

    with bpy.data.libraries.load(str(catalog.blend_path), link=False) as (data_from, data_to):
        del data_to
        available = set(data_from.materials)
    if entry.blend_material_name not in available:
        raise ValueError(
            f"El material '{entry.blend_material_name}' no existe en '{catalog.blend_path}'."
        )


def _append_material_from_blend(blend_path: Path, material_name: str) -> bpy.types.Material | None:
    existing = bpy.data.materials.get(material_name)
    if existing is not None:
        return existing

    with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
        if material_name not in data_from.materials:
            raise ValueError(f"No existe el material '{material_name}' en '{blend_path}'.")
        data_to.materials = [material_name]
    return bpy.data.materials.get(material_name)


def _configure_terrain_material_mapping(material: bpy.types.Material, target_object: bpy.types.Object) -> None:
    if material.node_tree is None:
        return

    node_tree = material.node_tree
    texture_coordinate = node_tree.nodes.new("ShaderNodeTexCoord")
    texture_coordinate.name = "PM_TerrainTexCoord"
    texture_coordinate.location = (-1000.0, 0.0)

    mapping = node_tree.nodes.new("ShaderNodeMapping")
    mapping.name = "PM_TerrainMapping"
    mapping.location = (-800.0, 0.0)

    tile_scale_x, tile_scale_y = _terrain_tile_scale(target_object)
    try:
        mapping.inputs["Scale"].default_value[0] = tile_scale_x
        mapping.inputs["Scale"].default_value[1] = tile_scale_y
        mapping.inputs["Scale"].default_value[2] = 1.0
    except Exception:
        pass

    node_tree.links.new(texture_coordinate.outputs["Generated"], mapping.inputs["Vector"])

    for node in node_tree.nodes:
        if node.bl_idname != "ShaderNodeTexImage":
            continue
        vector_input = node.inputs.get("Vector")
        if vector_input is None:
            continue
        while vector_input.links:
            node_tree.links.remove(vector_input.links[0])
        node_tree.links.new(mapping.outputs["Vector"], vector_input)


def _terrain_tile_scale(target_object: bpy.types.Object) -> tuple[float, float]:
    dimensions = getattr(target_object, "dimensions", None)
    if dimensions is None:
        return 1.0, 1.0
    width = max(float(dimensions[0]), 0.01)
    height = max(float(dimensions[1]), 0.01)
    return (
        max(1.0, width / TERRAIN_TEXTURE_WORLD_TILE_SIZE),
        max(1.0, height / TERRAIN_TEXTURE_WORLD_TILE_SIZE),
    )
