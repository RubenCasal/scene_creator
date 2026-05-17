from __future__ import annotations

import argparse
import math
import sys
import traceback
from pathlib import Path
from typing import Any

import bpy
from mathutils import Euler, Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_collection_utils import find_collection_by_path
from blender_generation_metadata import stamp_generated_metadata
from blender_road_utils import ensure_roads_generated
from blender_script_utils import bootstrap_src_path, emit_json
from blender_terrain_utils import create_terrain_plane, displace_terrain_from_heightfield

bootstrap_src_path()

from blender_terrain_material_utils import prepare_runtime_plane_as_terrain

from proc_map_designer.blender_bridge import (
    LayerPlanInput,
    LayerPlacementPlan,
    MapDimensions,
    MaskField,
    decode_mask_values,
    plan_generation,
)
from proc_map_designer.blender_bridge.terrain_sampler import TerrainSampler
from proc_map_designer.blender_bridge.package_loader import ExportLayerDefinition, load_export_package


GEN_ROOT_NAME = "PM_Generated"
FINAL_ROOT_NAME = "PM_Final"
RUNTIME_PLANE_NAME = "PM_RuntimePlane"
BACKEND_NAME = "python_batch_v1"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generación determinista usando Python dentro de Blender.")
    parser.add_argument("--project", required=True, help="Ruta a project.json exportado")
    parser.add_argument("--output", help="Ruta del .blend de salida. Default = output_blend del paquete")
    parser.add_argument("--root-name", default=GEN_ROOT_NAME, help="Nombre de la collection raíz para resultados")
    return parser.parse_args(argv)


def load_mask_field(mask_path: Path) -> MaskField:
    try:
        image = bpy.data.images.load(str(mask_path), check_existing=False)
    except RuntimeError as exc:
        raise ValueError(f"No se pudo cargar la máscara '{mask_path}': {exc}") from exc

    try:
        width, height = int(image.size[0]), int(image.size[1])
        channels = int(image.channels)
        total_values = width * height * channels
        buffer = [0.0] * total_values
        image.pixels.foreach_get(buffer)
        values = decode_mask_values(width=width, height=height, channels=channels, buffer=buffer)
    finally:
        bpy.data.images.remove(image)

    return MaskField(width=width, height=height, values=tuple(values))


def cleanup_collection(name: str) -> None:
    collection = bpy.data.collections.get(name)
    if collection is None:
        return
    for scene in list(collection.users_scene):
        if scene.collection.children.get(collection.name) is not None:
            scene.collection.children.unlink(collection)
    bpy.data.collections.remove(collection)


def cleanup_object(name: str) -> None:
    obj = bpy.data.objects.get(name)
    if obj is None:
        return
    bpy.data.objects.remove(obj, do_unlink=True)


def cleanup_generated_state(root_name: str) -> None:
    cleanup_collection(FINAL_ROOT_NAME)
    cleanup_object(RUNTIME_PLANE_NAME)
    for obj in list(bpy.data.objects):
        if obj.get("pm_backend") or obj.get("pm_runtime_plane"):
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        if collection.get("pm_generated_category"):
            bpy.data.collections.remove(collection)


def create_child_collection(parent: bpy.types.Collection, name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    collection["pm_generated_category"] = True
    parent.children.link(collection)
    return collection


def ensure_collection_linked_to_scene(collection: bpy.types.Collection) -> None:
    scene_collection = bpy.context.scene.collection
    if scene_collection.children.get(collection.name) is None:
        scene_collection.children.link(collection)


def create_runtime_plane(width: float, height: float) -> bpy.types.Object:
    half_width = width / 2.0
    half_height = height / 2.0
    mesh = bpy.data.meshes.new(RUNTIME_PLANE_NAME)
    mesh.from_pydata(
        [
            (-half_width, -half_height, 0.0),
            (half_width, -half_height, 0.0),
            (half_width, half_height, 0.0),
            (-half_width, half_height, 0.0),
        ],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()

    obj = bpy.data.objects.new(RUNTIME_PLANE_NAME, mesh)
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj["pm_runtime_plane"] = True
    bpy.context.scene.collection.objects.link(obj)
    return obj


def detach_original_scene_content(visible_root_names: set[str]) -> None:
    scene_root = bpy.context.scene.collection
    for child in list(scene_root.children):
        if child.name in visible_root_names:
            continue
        scene_root.children.unlink(child)
    for obj in list(scene_root.objects):
        if obj.name in visible_root_names:
            continue
        scene_root.objects.unlink(obj)


def category_cache_names(root_collection: bpy.types.Collection) -> set[str]:
    return {child.name for child in root_collection.children if child.get("pm_generated_category")}


def rename_original_scene_content(prefix: str = "__SRC__") -> None:
    scene_root = bpy.context.scene.collection
    for child in list(scene_root.children):
        _rename_collection_recursive(child, prefix)
    for obj in list(scene_root.objects):
        if obj.get("pm_backend") or obj.get("pm_runtime_plane"):
            continue
        if not obj.name.startswith(prefix):
            obj.name = f"{prefix}{obj.name}"


def _rename_collection_recursive(collection: bpy.types.Collection, prefix: str) -> None:
    if not collection.name.startswith(prefix):
        collection.name = f"{prefix}{collection.name}"
    for obj in collection.objects:
        if obj.get("pm_backend") or obj.get("pm_runtime_plane"):
            continue
        if not obj.name.startswith(prefix):
            obj.name = f"{prefix}{obj.name}"
    for child in collection.children:
        _rename_collection_recursive(child, prefix)


def configure_material_viewport() -> None:
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type != 'VIEW_3D':
                    continue
                try:
                    space.shading.type = 'MATERIAL'
                    space.shading.color_type = 'MATERIAL'
                except Exception:
                    continue


def collection_ground_offset(collection: bpy.types.Collection) -> float:
    min_z: float | None = None
    for obj in collection.all_objects:
        if obj.type not in {"MESH", "CURVE", "SURFACE", "FONT", "META", "VOLUME", "POINTCLOUD"}:
            continue
        if not obj.bound_box:
            continue
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            if min_z is None or world_corner.z < min_z:
                min_z = world_corner.z
    if min_z is None:
        return 0.0
    return -min_z


def collection_horizontal_radius(collection: bpy.types.Collection) -> float:
    max_radius = 0.0
    for obj in collection.all_objects:
        if obj.type not in {"MESH", "CURVE", "SURFACE", "FONT", "META", "VOLUME", "POINTCLOUD"}:
            continue
        if not obj.bound_box:
            continue
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            radius = math.hypot(world_corner.x, world_corner.y)
            if radius > max_radius:
                max_radius = radius
    return max_radius


def plan_layer_inputs(
    package_layers: list[ExportLayerDefinition],
) -> tuple[list[LayerPlanInput], dict[str, ExportLayerDefinition]]:
    layer_inputs: list[LayerPlanInput] = []
    layer_lookup: dict[str, ExportLayerDefinition] = {}
    for layer in package_layers:
        layer_lookup[layer.layer_id] = layer
        if not layer.enabled:
            continue
        if layer.generation_mode != "single" and not layer.mask_exists:
            raise ValueError(f"No existe la máscara necesaria para '{layer.layer_id}'.")
        mask_field = load_mask_field(layer.mask_path) if layer.mask_path is not None else None
        layer_inputs.append(
            LayerPlanInput(
                layer_id=layer.layer_id,
                category=layer.category,
                enabled=True,
                settings=layer.settings,
                mask=mask_field,
                single_instances=layer.single_instances,
            )
        )
    return layer_inputs, layer_lookup


def resolve_asset_collections(layers: list[ExportLayerDefinition]) -> dict[str, bpy.types.Collection]:
    assets: dict[str, bpy.types.Collection] = {}
    missing: list[str] = []
    for layer in layers:
        collection, _ = find_collection_by_path(layer.layer_id)
        if collection is None:
            missing.append(layer.layer_id)
        else:
            assets[layer.layer_id] = collection
    if missing:
        raise ValueError(
            "No se encontraron las collections requeridas: " + ", ".join(missing)
        )
    return assets


def apply_default_bounding_radii(
    layer_inputs: list[LayerPlanInput],
    asset_collections: dict[str, bpy.types.Collection],
) -> None:
    for layer_input in layer_inputs:
        settings = layer_input.settings
        if getattr(settings, "bounding_radius", None) not in (None, 0.0):
            continue
        collection = asset_collections.get(layer_input.layer_id)
        if collection is None:
            continue
        settings.bounding_radius = collection_horizontal_radius(collection)


def generate_instances(
    plans: list[LayerPlacementPlan],
    layer_lookup: dict[str, ExportLayerDefinition],
    asset_collections: dict[str, bpy.types.Collection],
    runtime_plane: bpy.types.Object,
    root_collection: bpy.types.Collection,
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    ground_offsets = {layer_id: collection_ground_offset(collection) for layer_id, collection in asset_collections.items()}

    category_cache: dict[str, bpy.types.Collection] = {}

    for plan in plans:
        layer_id = plan.layer_id
        definition = layer_lookup[layer_id]
        placements = plan.placements
        asset_collection = asset_collections[layer_id]

        category_collection = category_cache.get(definition.category)
        if category_collection is None:
            category_collection = create_child_collection(root_collection, definition.category)
            category_cache[definition.category] = category_collection

        placed = 0
        for index, placement in enumerate(placements):
            base_name = definition.name or layer_id.split("/")[-1]
            obj_name = base_name if index == 0 else f"{base_name}_{index:05d}"
            obj = bpy.data.objects.new(obj_name, None)
            obj.empty_display_type = 'PLAIN_AXES'
            obj.instance_type = 'COLLECTION'
            obj.instance_collection = asset_collection

            offset_z = ground_offsets.get(layer_id, 0.0) * placement.scale
            terrain_z = getattr(placement, "z", 0.0)
            obj.location = Vector((placement.x, placement.y, terrain_z + offset_z))
            rotation = Euler((0.0, 0.0, math.radians(placement.rotation_z_deg)), 'XYZ')
            obj.rotation_mode = 'XYZ'
            obj.rotation_euler = rotation
            obj.scale = (placement.scale, placement.scale, placement.scale)
            stamp_generated_metadata(
                obj,
                layer_id=layer_id,
                category=definition.category,
                backend=BACKEND_NAME,
            )

            category_collection.objects.link(obj)
            placed += 1

        summary.append({"layer_id": layer_id, "count": placed})

    return summary


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    package_path = Path(args.project)
    package = load_export_package(package_path, require_mask_files=True)
    print(f"[python_batch] Cargando paquete: {package.project_json}")

    output_path = Path(args.output or package.output_blend).expanduser().resolve()
    if not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if package.map.base_plane_object:
        print(f"[python_batch] Plano base configurado (no usado para terrain): {package.map.base_plane_object}")

    layer_inputs, layer_lookup = plan_layer_inputs(package.layers)
    asset_collections = resolve_asset_collections([layer for layer in package.layers if layer.enabled])
    apply_default_bounding_radii(layer_inputs, asset_collections)
    print(f"[python_batch] Capas habilitadas: {len(layer_inputs)}")

    map_dims = MapDimensions(
        width=package.map.width,
        height=package.map.height,
        mask_width=package.map.mask_width,
        mask_height=package.map.mask_height,
    )
    terrain_sampler = None
    if package.map.terrain.enabled and package.map.terrain.heightfield_exists:
        terrain_sampler = TerrainSampler(
            package.map.terrain.heightfield_path,
            package.map.terrain.max_height,
            package.map.width,
            package.map.height,
        )
    plans = plan_generation(package.project_id, map_dims, layer_inputs, terrain_sampler=terrain_sampler)

    cleanup_generated_state(args.root_name)
    rename_original_scene_content()
    root_collection = bpy.context.scene.collection
    if package.map.terrain.enabled and package.map.terrain.heightfield_exists:
        runtime_plane = create_terrain_plane(
            package.map.width,
            package.map.height,
            package.map.terrain.export_subdivision,
            RUNTIME_PLANE_NAME,
        )
        displace_terrain_from_heightfield(
            runtime_plane,
            heightfield_path=package.map.terrain.heightfield_path,
            max_height=package.map.terrain.max_height,
            map_width=package.map.width,
            map_height=package.map.height,
        )
    else:
        runtime_plane = create_runtime_plane(package.map.width, package.map.height)
    if runtime_plane.name not in root_collection.objects:
        root_collection.objects.link(runtime_plane)
    prepare_runtime_plane_as_terrain(
        terrain_material_id=package.map.terrain_material_id,
        runtime_plane=runtime_plane,
    )
    print(f"[python_batch] Plano runtime creado: {runtime_plane.name} ({package.map.width} x {package.map.height})")
    configure_material_viewport()

    summary = generate_instances(plans, layer_lookup, asset_collections, runtime_plane, root_collection)
    road_summary = ensure_roads_generated(package, root_collection, runtime_plane)
    combined_summary = summary + road_summary
    for entry in combined_summary:
        print(f"[python_batch] {entry['layer_id']}: {entry['count']} instancias")

    detach_original_scene_content({runtime_plane.name, *category_cache_names(root_collection)})

    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    print(f"[python_batch] Archivo guardado: {output_path}")

    warnings = [
        f"La capa '{entry['layer_id']}' no generó instancias." for entry in combined_summary if entry["count"] == 0
    ]
    if not combined_summary:
        warnings.append("No se generó ninguna instancia. Verifica que existan capas habilitadas y máscaras con información.")

    payload = {
        "success": True,
        "backend": BACKEND_NAME,
        "output_blend": str(output_path),
        "placed_layers": combined_summary,
        "warnings": warnings,
    }
    emit_json(payload)


if __name__ == "__main__":
    try:
        main(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:])
    except Exception as exc:  # pragma: no cover - Blender runtime specific
        error_payload = {
            "success": False,
            "backend": BACKEND_NAME,
            "error": f"{exc.__class__.__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        emit_json(error_payload)
        print(traceback.format_exc(), file=sys.stderr)
        raise
