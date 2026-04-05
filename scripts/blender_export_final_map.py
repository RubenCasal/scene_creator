from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Any

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_script_utils import bootstrap_src_path, emit_json

bootstrap_src_path()

from proc_map_designer.blender_bridge.package_loader import load_export_package

GENERATED_ROOT_NAME = "PM_Generated"
GENERATED_ROOT_GN_NAME = "PM_Generated_GN"
FINAL_ROOT_NAME = "PM_Final"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolida colecciones generadas en un .blend final.")
    parser.add_argument("--project", required=True, help="Ruta a project.json exportado")
    parser.add_argument("--output", help="Ruta del final_map.blend. Default: <paquete>/final_map.blend")
    parser.add_argument("--generated-root", default=GENERATED_ROOT_NAME, help="Collection raíz generada")
    parser.add_argument("--final-root", default=FINAL_ROOT_NAME, help="Collection raíz para la exportación")
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
    scene_root = bpy.context.scene.collection
    if scene_root.children.get(collection.name) is None:
        scene_root.children.link(collection)


def link_object_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    if all(existing.name != collection.name for existing in obj.users_collection):
        collection.objects.link(obj)


def collect_generated_objects(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    return [obj for obj in collection.all_objects if "pm_layer_id" in obj]


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    package = load_export_package(Path(args.project))

    default_output = package.package_dir / "final_map.blend"
    output_path = Path(args.output or default_output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated_root_name = args.generated_root
    generated_root = bpy.data.collections.get(generated_root_name)
    if generated_root is None and generated_root_name == GENERATED_ROOT_NAME:
        generated_root_name = GENERATED_ROOT_GN_NAME
        generated_root = bpy.data.collections.get(generated_root_name)
    if generated_root is None:
        raise RuntimeError(f"No existe la collection generada '{args.generated_root}'.")

    generated_objects = collect_generated_objects(generated_root)
    if not generated_objects:
        raise RuntimeError("No se encontraron objetos con metadatos generados para consolidar.")

    cleanup_collection(args.final_root)
    final_root = bpy.data.collections.new(args.final_root)
    ensure_collection_linked_to_scene(final_root)

    category_collections: dict[str, bpy.types.Collection] = {}
    warnings: list[str] = []
    category_counts: dict[str, int] = {}

    for obj in generated_objects:
        category = str(obj.get("pm_category", "")).strip()
        if not category:
            warnings.append(f"El objeto '{obj.name}' no tiene 'pm_category'. Se omitió.")
            continue

        target_collection = category_collections.get(category)
        if target_collection is None:
            target_collection = bpy.data.collections.new(category)
            final_root.children.link(target_collection)
            category_collections[category] = target_collection

        link_object_to_collection(obj, target_collection)
        category_counts[category] = category_counts.get(category, 0) + 1

    # Conservamos las instancias como instancias: la exportación final reagrupa los emisores/instancers
    # bajo colecciones por categoría y evita realizar geometría de forma destructiva.
    cleanup_collection(generated_root_name)

    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))

    payload = {
        "success": True,
        "output_blend": str(output_path),
        "final_root": args.final_root,
        "category_counts": [
            {"category": name, "count": count} for name, count in sorted(category_counts.items())
        ],
        "warnings": warnings,
    }
    emit_json(payload)


if __name__ == "__main__":
    try:
        main(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:])
    except Exception as exc:  # pragma: no cover - Blender runtime specific
        error_payload = {
            "success": False,
            "error": f"{exc.__class__.__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        emit_json(error_payload)
        print(traceback.format_exc(), file=sys.stderr)
        raise
