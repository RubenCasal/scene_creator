from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TerrainMaterialCatalogEntry:
    id: str
    label: str
    blend_material_name: str


@dataclass(slots=True)
class TerrainMaterialCatalog:
    blend_path: Path
    entries: list[TerrainMaterialCatalogEntry]


class TerrainMaterialCatalogError(RuntimeError):
    pass


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parents[3] / "blender_defaults" / "terrain_textures" / "material_catalog.json"


def load_terrain_material_catalog(catalog_path: Path | None = None) -> TerrainMaterialCatalog:
    path = (catalog_path or default_catalog_path()).resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TerrainMaterialCatalogError(f"No se pudo leer el catálogo de materiales de terreno: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TerrainMaterialCatalogError(f"Catálogo JSON inválido: {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise TerrainMaterialCatalogError("El catálogo de materiales de terreno debe ser un objeto JSON.")

    blend_path_raw = payload.get("blend_path")
    if not isinstance(blend_path_raw, str) or not blend_path_raw.strip():
        raise TerrainMaterialCatalogError("El catálogo de materiales de terreno requiere 'blend_path'.")
    blend_path = (path.parents[2] / blend_path_raw).resolve()
    if not blend_path.exists() or not blend_path.is_file():
        raise TerrainMaterialCatalogError(f"No existe la librería .blend del catálogo: {blend_path}")

    raw_materials = payload.get("materials")
    if not isinstance(raw_materials, list) or not raw_materials:
        raise TerrainMaterialCatalogError("El catálogo de materiales de terreno requiere una lista 'materials' no vacía.")

    entries: list[TerrainMaterialCatalogEntry] = []
    seen_ids: set[str] = set()
    for raw_entry in raw_materials:
        entry = _parse_entry(raw_entry)
        if entry.id in seen_ids:
            raise TerrainMaterialCatalogError(f"Material de terreno duplicado en catálogo: {entry.id}")
        seen_ids.add(entry.id)
        entries.append(entry)

    return TerrainMaterialCatalog(blend_path=blend_path, entries=entries)


def get_catalog_entry(material_id: str, catalog: TerrainMaterialCatalog | None = None) -> TerrainMaterialCatalogEntry:
    resolved_catalog = catalog or load_terrain_material_catalog()
    for entry in resolved_catalog.entries:
        if entry.id == material_id:
            return entry
    raise TerrainMaterialCatalogError(f"Material de terreno no encontrado en catálogo: {material_id}")


def _parse_entry(raw_entry: Any) -> TerrainMaterialCatalogEntry:
    if not isinstance(raw_entry, dict):
        raise TerrainMaterialCatalogError("Cada entrada de materiales de terreno debe ser un objeto JSON.")
    material_id = raw_entry.get("id")
    label = raw_entry.get("label")
    blend_material_name = raw_entry.get("blend_material_name")
    if not isinstance(material_id, str) or not material_id.strip():
        raise TerrainMaterialCatalogError("Cada entrada del catálogo requiere 'id'.")
    if not isinstance(label, str) or not label.strip():
        raise TerrainMaterialCatalogError(f"La entrada '{material_id}' requiere 'label'.")
    if not isinstance(blend_material_name, str) or not blend_material_name.strip():
        raise TerrainMaterialCatalogError(f"La entrada '{material_id}' requiere 'blend_material_name'.")
    return TerrainMaterialCatalogEntry(
        id=material_id.strip(),
        label=label.strip(),
        blend_material_name=blend_material_name.strip(),
    )
