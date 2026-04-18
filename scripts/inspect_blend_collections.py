from __future__ import annotations

import json
import sys
import traceback
from typing import Any

JSON_START = "__BLEND_JSON_START__"
JSON_END = "__BLEND_JSON_END__"


def _serialize_collection(collection: Any, visited: set[str]) -> dict[str, Any]:
    name = str(collection.name)
    if name in visited:
        return {"name": name, "children": [], "object_count": int(len(collection.objects))}

    next_visited = set(visited)
    next_visited.add(name)
    children = [_serialize_collection(child, next_visited) for child in collection.children]
    return {
        "name": name,
        "children": children,
        "object_count": int(len(collection.objects)),
    }


def _collect_reachable_collection_names(collection: Any, visited: set[str]) -> None:
    name = str(collection.name)
    if name in visited:
        return
    visited.add(name)
    for child in collection.children:
        _collect_reachable_collection_names(child, visited)


def _emit_json(payload: dict[str, Any]) -> None:
    print(JSON_START)
    print(json.dumps(payload, ensure_ascii=False))
    print(JSON_END)


def main() -> None:
    import bpy

    all_collections = list(bpy.data.collections)
    base_plane_candidates = sorted(
        obj.name
        for obj in bpy.data.objects
        if obj.type == "MESH"
        and obj.visible_get()
        and hasattr(obj, "dimensions")
        and max(float(obj.dimensions[0]), float(obj.dimensions[1])) >= 1.0
    )
    scene_root = bpy.context.scene.collection
    root_collections = list(scene_root.children)
    roots = [_serialize_collection(collection, set()) for collection in root_collections]

    reachable_names: set[str] = set()
    for collection in root_collections:
        _collect_reachable_collection_names(collection, reachable_names)

    all_collection_names = {str(collection.name) for collection in all_collections}
    unlinked_names = sorted(all_collection_names - reachable_names)

    warnings: list[str] = []
    if not root_collections:
        warnings.append("La escena no contiene collections enlazadas bajo 'Scene Collection'.")
    if not all_collections:
        warnings.append("El archivo no contiene collections.")
    if unlinked_names:
        warnings.append(
            "Hay collections no enlazadas en la escena activa: " + ", ".join(unlinked_names)
        )

    payload = {
        "blend_file": bpy.data.filepath,
        "roots": roots,
        "total_collections": len(reachable_names),
        "warnings": warnings,
        "base_plane_candidates": base_plane_candidates,
    }
    _emit_json(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        error_payload = {
            "error": f"{exc.__class__.__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        _emit_json(error_payload)
        print(traceback.format_exc(), file=sys.stderr)
        raise SystemExit(1)
