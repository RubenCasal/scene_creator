from __future__ import annotations

import argparse
import math
import sys
import traceback
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_collection_utils import find_collection_by_path
from blender_road_utils import ensure_roads_generated
from blender_script_utils import bootstrap_src_path, emit_json

bootstrap_src_path()

from blender_terrain_material_utils import prepare_runtime_plane_as_terrain

from proc_map_designer.blender_bridge import LayerPlanInput, MapDimensions, plan_generation
from proc_map_designer.blender_bridge.package_loader import ExportLayerDefinition, load_export_package
from blender_generate_python_batch import (
    configure_material_viewport,
    create_runtime_plane,
    cleanup_generated_state,
    hide_original_scene_content,
    load_mask_field,
)

BACKEND_NAME = "geometry_nodes_v2"
GEN_ROOT_NAME = "PM_Generated_GN"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backend Geometry Nodes basado en point-cloud intermedio.")
    parser.add_argument("--project", required=True, help="Ruta a project.json exportado")
    parser.add_argument("--output", help="Ruta del .blend de salida. Default = output_blend del paquete")
    parser.add_argument("--root-name", default=GEN_ROOT_NAME, help="Nombre de la collection raíz para resultados GN")
    return parser.parse_args(argv)


def cleanup_collection(name: str) -> None:
    collection = bpy.data.collections.get(name)
    if collection is None:
        return
    for scene in list(collection.users_scene):
        if scene.collection.children.get(collection.name) is not None:
            scene.collection.children.unlink(collection)
    bpy.data.collections.remove(collection)


def ensure_collection_linked_to_scene(collection: bpy.types.Collection) -> None:
    scene_collection = bpy.context.scene.collection
    if scene_collection.children.get(collection.name) is None:
        scene_collection.children.link(collection)


def create_child_collection(parent: bpy.types.Collection, name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


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
        raise ValueError("No se encontraron las collections requeridas: " + ", ".join(missing))
    return assets


def build_layer_inputs(package_layers: list[ExportLayerDefinition]) -> tuple[list[LayerPlanInput], dict[str, ExportLayerDefinition]]:
    layer_inputs: list[LayerPlanInput] = []
    layer_lookup: dict[str, ExportLayerDefinition] = {}
    for layer in package_layers:
        layer_lookup[layer.layer_id] = layer
        if not layer.enabled:
            continue
        if not layer.mask_exists:
            raise ValueError(f"No existe la máscara necesaria para '{layer.layer_id}'.")
        layer_inputs.append(
            LayerPlanInput(
                layer_id=layer.layer_id,
                category=layer.category,
                enabled=True,
                settings=layer.settings,
                mask=load_mask_field(layer.mask_path),
            )
        )
    return layer_inputs, layer_lookup


def create_point_mesh(name: str, positions: list[Vector]) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(position) for position in positions], [], [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    return obj


def build_instance_node_group(
    name: str,
    asset_collection: bpy.types.Collection,
    settings: Any,
) -> bpy.types.NodeTree:
    group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")

    group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    group_in = group.nodes.new("NodeGroupInput")
    group_in.location = (-600, 0)
    group_out = group.nodes.new("NodeGroupOutput")
    group_out.location = (500, 0)

    collection_info = group.nodes.new("GeometryNodeCollectionInfo")
    collection_info.location = (-350, -180)
    collection_info.inputs[0].default_value = asset_collection
    collection_info.transform_space = 'RELATIVE'
    collection_info.reset_children = False
    collection_info.separate_children = False

    instance_on_points = group.nodes.new("GeometryNodeInstanceOnPoints")
    instance_on_points.location = (-50, 0)

    random_scale = group.nodes.new("FunctionNodeRandomValue")
    random_scale.location = (-330, 140)
    random_scale.data_type = 'FLOAT'
    random_scale.inputs[2].default_value = float(settings.scale_min)
    random_scale.inputs[3].default_value = float(settings.scale_max)

    random_rotation = group.nodes.new("FunctionNodeRandomValue")
    random_rotation.location = (-330, 300)
    random_rotation.data_type = 'FLOAT_VECTOR'
    rotation_range = math.radians(float(settings.rotation_random_z))
    random_rotation.inputs[2].default_value = (0.0, 0.0, -rotation_range)
    random_rotation.inputs[3].default_value = (0.0, 0.0, rotation_range)

    group.links.new(group_in.outputs[0], instance_on_points.inputs[0])
    group.links.new(collection_info.outputs[0], instance_on_points.inputs[2])
    group.links.new(random_rotation.outputs[1], instance_on_points.inputs[5])
    group.links.new(random_scale.outputs[1], instance_on_points.inputs[6])
    group.links.new(instance_on_points.outputs[0], group_out.inputs[0])
    return group


def generate_emitters(
    runtime_plane: bpy.types.Object,
    root_collection: bpy.types.Collection,
    plans,
    layer_lookup: dict[str, ExportLayerDefinition],
    assets: dict[str, bpy.types.Collection],
) -> list[dict[str, Any]]:
    category_cache: dict[str, bpy.types.Collection] = {}
    summary: list[dict[str, Any]] = []

    for plan in plans:
        layer = layer_lookup[plan.layer_id]
        category_collection = category_cache.get(layer.category)
        if category_collection is None:
            category_collection = create_child_collection(root_collection, layer.category)
            category_cache[layer.category] = category_collection

        emitter_collection = create_child_collection(category_collection, layer.name)
        positions = [runtime_plane.matrix_world @ Vector((placement.x, placement.y, 0.0)) for placement in plan.placements]
        emitter = create_point_mesh(f"PM_GN_{layer.name}", positions)
        emitter["pm_layer_id"] = layer.layer_id
        emitter["pm_category"] = layer.category
        emitter["pm_backend"] = BACKEND_NAME
        modifier = emitter.modifiers.new(name="PM_GN", type='NODES')
        modifier.node_group = build_instance_node_group(
            name=f"PM_GN_{layer.name}_Group",
            asset_collection=assets[layer.layer_id],
            settings=layer.settings,
        )
        emitter_collection.objects.link(emitter)
        summary.append({"layer_id": layer.layer_id, "count": len(plan.placements)})

    return summary


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    package = load_export_package(Path(args.project), require_mask_files=True)
    print(f"[geometry_nodes] Cargando paquete: {package.project_json}")
    output_path = Path(args.output or package.output_blend).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if package.map.base_plane_object:
        print(f"[geometry_nodes] Plano base configurado (no usado para terrain): {package.map.base_plane_object}")

    layer_inputs, layer_lookup = build_layer_inputs(package.layers)
    assets = resolve_asset_collections([layer for layer in package.layers if layer.enabled])
    map_dims = MapDimensions(
        width=package.map.width,
        height=package.map.height,
        mask_width=package.map.mask_width,
        mask_height=package.map.mask_height,
    )
    plans = plan_generation(package.project_id, map_dims, layer_inputs)

    cleanup_generated_state(args.root_name)
    root_collection = bpy.data.collections.new(args.root_name)
    ensure_collection_linked_to_scene(root_collection)
    runtime_plane = create_runtime_plane(package.map.width, package.map.height)
    root_collection.objects.link(runtime_plane)
    if bpy.context.scene.collection.objects.get(runtime_plane.name) is not None:
        bpy.context.scene.collection.objects.unlink(runtime_plane)
    prepare_runtime_plane_as_terrain(
        terrain_material_id=package.map.terrain_material_id,
        runtime_plane=runtime_plane,
    )
    print(f"[geometry_nodes] Plano runtime creado: {runtime_plane.name} ({package.map.width} x {package.map.height})")
    hide_original_scene_content({root_collection.name})
    configure_material_viewport()
    summary = generate_emitters(runtime_plane, root_collection, plans, layer_lookup, assets)
    road_summary = ensure_roads_generated(package, root_collection, runtime_plane)
    combined_summary = summary + road_summary
    for entry in combined_summary:
        print(f"[geometry_nodes] {entry['layer_id']}: {entry['count']} puntos emisores")

    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    print(f"[geometry_nodes] Archivo guardado: {output_path}")

    payload = {
        "success": True,
        "backend": BACKEND_NAME,
        "output_blend": str(output_path),
        "placed_layers": combined_summary,
        "warnings": [
            "Backend Geometry Nodes usa un point-cloud intermedio generado por Python.",
            "La orientación y escala por punto se aproximan dentro del node graph y pueden no coincidir exactamente con python_batch.",
            "Las instancias finales permanecen como instancias Geometry Nodes; no se realizan automáticamente.",
        ],
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
