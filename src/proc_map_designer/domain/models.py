from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass(slots=True)
class CollectionNode:
    name: str
    object_count: int = 0
    children: list["CollectionNode"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CollectionNode":
        raw_name = data.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError("CollectionNode requires a non-empty 'name'.")

        raw_children = data.get("children", [])
        if not isinstance(raw_children, list):
            raise ValueError(f"Children for '{raw_name}' must be a list.")

        raw_object_count = data.get("object_count", 0)
        if not isinstance(raw_object_count, int):
            raise ValueError(f"'object_count' for '{raw_name}' must be an integer.")

        children: list[CollectionNode] = []
        for child in raw_children:
            if not isinstance(child, Mapping):
                raise ValueError(f"Invalid child node for '{raw_name}'.")
            children.append(cls.from_dict(child))

        return cls(name=raw_name, object_count=raw_object_count, children=children)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "object_count": self.object_count,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(slots=True)
class BlendInspectionResult:
    blend_file: str
    roots: list[CollectionNode]
    total_collections: int
    warnings: list[str] = field(default_factory=list)
    base_plane_candidates: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BlendInspectionResult":
        blend_file_value = data.get("blend_file", "")
        blend_file = str(blend_file_value).strip() or "<desconocido>"

        raw_roots = data.get("roots", [])
        if not isinstance(raw_roots, list):
            raise ValueError("'roots' must be a list.")
        roots = [CollectionNode.from_dict(node) for node in raw_roots]

        raw_total = data.get("total_collections", 0)
        if not isinstance(raw_total, int):
            raise ValueError("'total_collections' must be an integer.")

        raw_warnings = data.get("warnings", [])
        if not isinstance(raw_warnings, list):
            raise ValueError("'warnings' must be a list of strings.")
        warnings = [str(item) for item in raw_warnings]

        raw_planes = data.get("base_plane_candidates", [])
        if not isinstance(raw_planes, list):
            raise ValueError("'base_plane_candidates' must be a list of strings.")
        base_plane_candidates = [str(item).strip() for item in raw_planes if str(item).strip()]

        return cls(
            blend_file=blend_file,
            roots=roots,
            total_collections=raw_total,
            warnings=warnings,
            base_plane_candidates=base_plane_candidates,
        )

    def root_names_lower(self) -> set[str]:
        return {root.name.lower() for root in self.roots}

    def missing_expected_roots(self, expected_names: Iterable[str]) -> set[str]:
        expected = {name.lower() for name in expected_names}
        return expected - self.root_names_lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "blend_file": self.blend_file,
            "roots": [root.to_dict() for root in self.roots],
            "total_collections": self.total_collections,
            "warnings": list(self.warnings),
            "base_plane_candidates": list(self.base_plane_candidates),
        }
