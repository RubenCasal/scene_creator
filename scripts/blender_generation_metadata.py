from __future__ import annotations

import bpy


def stamp_generated_metadata(
    obj: bpy.types.Object,
    *,
    layer_id: str,
    category: str,
    backend: str,
) -> None:
    obj["pm_layer_id"] = layer_id
    obj["pm_category"] = category
    obj["pm_backend"] = backend
