from __future__ import annotations

import bpy


def split_collection_path(path: str) -> list[str]:
    return [part.strip() for part in path.split("/") if part.strip()]


def find_collection_by_path(path: str) -> tuple[bpy.types.Collection | None, list[str]]:
    parts = split_collection_path(path)
    if not parts:
        return None, []

    current = bpy.data.collections.get(parts[0])
    if current is None:
        return None, parts

    for name in parts[1:]:
        next_child = _find_child_by_name(current, name)
        if next_child is None:
            return None, parts
        current = next_child

    return current, parts


def _find_child_by_name(collection: bpy.types.Collection, name: str) -> bpy.types.Collection | None:
    for child in collection.children:
        if child.name == name:
            return child
    return None
