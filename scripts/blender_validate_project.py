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

from blender_collection_utils import find_collection_by_path
from blender_road_utils import validate_road_assets
from blender_script_utils import bootstrap_src_path, emit_json

bootstrap_src_path()

from proc_map_designer.blender_bridge.package_loader import load_export_package


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida un paquete exportado para Blender.")
    parser.add_argument("--project", required=True, help="Ruta a project.json exportado")
    return parser.parse_args(argv)


def resolve_base_plane(object_name: str) -> tuple[dict[str, Any] | None, str | None]:
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        return None, f"No se encontró el objeto base '{object_name}' en el archivo abierto."
    translation = list(obj.matrix_world.translation)
    rotation = list(obj.matrix_world.to_euler("XYZ"))
    dimensions = (list(obj.dimensions) if hasattr(obj, "dimensions") else [0.0, 0.0, 0.0])
    return (
        {
            "name": obj.name,
            "type": obj.type,
            "location": [float(value) for value in translation],
            "rotation_euler": [float(value) for value in rotation],
            "dimensions": [float(value) for value in dimensions],
        },
        None,
    )


def read_mask_resolution(mask_path: Path) -> tuple[int, int]:
    try:
        image = bpy.data.images.load(str(mask_path), check_existing=False)
    except RuntimeError as exc:
        raise ValueError(f"No se pudo cargar la máscara '{mask_path}': {exc}") from exc

    try:
        return int(image.size[0]), int(image.size[1])
    finally:
        bpy.data.images.remove(image)


def validate_package(package_path: Path) -> dict[str, Any]:
    package = load_export_package(package_path, require_mask_files=False)

    errors: list[str] = []
    warnings: list[str] = []
    resolved_layers: list[dict[str, Any]] = []

    resolved_base_plane, base_plane_error = resolve_base_plane(package.map.base_plane_object)
    if base_plane_error:
        errors.append(base_plane_error)

    for layer in package.layers:
        layer_info: dict[str, Any] = {
            "layer_id": layer.layer_id,
            "category": layer.category,
            "mask_path": str(layer.mask_path),
            "mask_exists": layer.mask_exists,
            "enabled": layer.enabled,
        }

        if not layer.enabled:
            warnings.append(f"La capa '{layer.layer_id}' está deshabilitada y se omitirá en la generación.")

        if not layer.mask_exists:
            errors.append(f"No se encontró la máscara para '{layer.layer_id}': {layer.mask_path}")
        else:
            try:
                mask_width, mask_height = read_mask_resolution(layer.mask_path)
            except ValueError as exc:
                errors.append(str(exc))
            else:
                if (mask_width, mask_height) != (package.map.mask_width, package.map.mask_height):
                    errors.append(
                        f"La máscara de '{layer.layer_id}' tiene resolución {mask_width}x{mask_height} y se esperaba "
                        f"{package.map.mask_width}x{package.map.mask_height}."
                    )

        collection, parts = find_collection_by_path(layer.layer_id)
        if collection is None:
            errors.append(
                f"No se encontró la colección '{layer.layer_id}' en el .blend (ruta: {'/'.join(parts)})."
            )
        else:
            layer_info.update(
                {
                    "collection_name": collection.name,
                    "object_count": len(collection.objects),
                }
            )
            if len(collection.objects) == 0:
                warnings.append(f"La colección '{layer.layer_id}' está vacía.")

        resolved_layers.append(layer_info)

    errors.extend(validate_road_assets(package))
    for road in package.roads:
        if not road.visible:
            warnings.append(f"La road '{road.road_id}' está oculta y se omitirá en la generación.")

    success = not errors
    payload = {
        "success": success,
        "errors": errors,
        "warnings": warnings,
        "project_json": str(package.project_json),
        "blend_file": bpy.data.filepath,
        "resolved_collections": resolved_layers,
        "resolved_base_plane": resolved_base_plane,
    }
    return payload


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    package_path = Path(args.project)
    print(f"[validate] Validando paquete: {package_path}")
    payload = validate_package(package_path)
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
