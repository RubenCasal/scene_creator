from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage

from proc_map_designer.domain.coordinates import scene_to_mask
from proc_map_designer.domain.layer_palette import (
    is_valid_hex_color,
    split_layer_id,
    variant_color_for_sibling,
)
from proc_map_designer.domain.models import CollectionNode
from proc_map_designer.domain.project_state import LayerGenerationSettings, LayerState, MapSettings
from proc_map_designer.ui.canvas.brush_tool import BrushTool


def _sanitize_layer_id(layer_id: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", layer_id.strip())
    return sanitized.strip("_") or "layer"


@dataclass(slots=True)
class LayerMask:
    layer_id: str
    display_name: str
    color_hex: str
    visible: bool = True
    opacity: float = 0.85
    mask_data_path: str | None = None
    generation_settings: LayerGenerationSettings = field(default_factory=LayerGenerationSettings)
    mask_image: QImage | None = None


class LayerMaskManager:
    def __init__(self, map_settings: MapSettings) -> None:
        self._map_settings = map_settings
        self._layers: dict[str, LayerMask] = {}
        self._order: list[str] = []

    @property
    def map_settings(self) -> MapSettings:
        return self._map_settings

    def all_layers(self) -> list[LayerMask]:
        return [self._layers[layer_id] for layer_id in self._order if layer_id in self._layers]

    def get_layer(self, layer_id: str) -> LayerMask | None:
        return self._layers.get(layer_id)

    def set_map_settings(self, map_settings: MapSettings) -> None:
        old_width = self._map_settings.mask_width
        old_height = self._map_settings.mask_height
        self._map_settings = map_settings

        if (old_width, old_height) == (map_settings.mask_width, map_settings.mask_height):
            return

        for layer in self._layers.values():
            mask = layer.mask_image or self._new_empty_mask()
            layer.mask_image = mask.scaled(
                map_settings.mask_width,
                map_settings.mask_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    def sync_from_collection_tree(self, roots: list[CollectionNode]) -> None:
        layer_paths = self._extract_layer_paths(roots)
        self._sync_to_paths(layer_paths)

    def load_from_project_layers(self, layers: list[LayerState], project_dir: Path) -> None:
        self._layers.clear()
        self._order.clear()
        category_indices: dict[str, int] = {}

        for layer_state in layers:
            category, _ = split_layer_id(layer_state.layer_id)
            sibling_index = category_indices.get(category, 0)
            category_indices[category] = sibling_index + 1

            if is_valid_hex_color(layer_state.color_hex):
                color_hex = layer_state.color_hex.strip().lower()
            else:
                color_hex = variant_color_for_sibling(category, sibling_index)

            mask = self._load_mask_from_layer_state(layer_state, project_dir)
            layer = LayerMask(
                layer_id=layer_state.layer_id,
                display_name=layer_state.name or layer_state.layer_id,
                color_hex=color_hex,
                visible=layer_state.visible,
                opacity=layer_state.opacity,
                mask_data_path=layer_state.mask_data_path,
                generation_settings=layer_state.generation_settings,
                mask_image=mask,
            )
            self._layers[layer.layer_id] = layer
            self._order.append(layer.layer_id)

    def ensure_layers_for_collections(self, roots: list[CollectionNode]) -> None:
        expected = self._extract_layer_paths(roots)
        if not self._layers:
            self._sync_to_paths(expected)
            return

        existing = set(self._layers.keys())
        for path in expected:
            if path in existing:
                continue
            category, _ = split_layer_id(path)
            sibling_index = self._count_category_layers(category)
            self._layers[path] = LayerMask(
                layer_id=path,
                display_name=path,
                color_hex=variant_color_for_sibling(category, sibling_index),
                mask_image=self._new_empty_mask(),
            )
            self._order.append(path)

    def clear_layer(self, layer_id: str) -> None:
        layer = self._layers.get(layer_id)
        if layer is None:
            return
        layer.mask_image = self._new_empty_mask()

    def set_layer_visibility(self, layer_id: str, visible: bool) -> None:
        layer = self._layers.get(layer_id)
        if layer is None:
            return
        layer.visible = visible

    def paint_stroke(
        self,
        layer_id: str,
        brush: BrushTool,
        start_scene: QPointF,
        end_scene: QPointF,
    ) -> bool:
        layer = self._layers.get(layer_id)
        if layer is None:
            return False

        if layer.mask_image is None:
            layer.mask_image = self._new_empty_mask()

        start_mask = self._scene_to_mask_point(start_scene)
        end_mask = self._scene_to_mask_point(end_scene)
        brush.paint_segment(layer.mask_image, start_mask, end_mask)
        return True

    def to_layer_states(self, project_dir: Path) -> list[LayerState]:
        mask_dir = project_dir / "masks"
        mask_dir.mkdir(parents=True, exist_ok=True)

        states: list[LayerState] = []
        for index, layer_id in enumerate(self._order):
            layer = self._layers[layer_id]
            filename = f"{index:03d}_{_sanitize_layer_id(layer.layer_id)}.png"
            mask_path = mask_dir / filename

            mask = layer.mask_image or self._new_empty_mask()
            if not mask.save(str(mask_path), "PNG"):
                raise RuntimeError(f"No se pudo guardar la máscara de la capa '{layer.layer_id}'.")

            relative = mask_path.relative_to(project_dir).as_posix()
            layer.mask_data_path = relative
            states.append(
                LayerState(
                    layer_id=layer.layer_id,
                    name=layer.display_name,
                    visible=layer.visible,
                    opacity=layer.opacity,
                    mask_data_path=relative,
                    color_hex=layer.color_hex,
                    generation_settings=layer.generation_settings,
                )
            )
        return states

    def snapshot_layer_states(self) -> list[LayerState]:
        states: list[LayerState] = []
        for layer_id in self._order:
            layer = self._layers[layer_id]
            states.append(
                LayerState(
                    layer_id=layer.layer_id,
                    name=layer.display_name,
                    visible=layer.visible,
                    opacity=layer.opacity,
                    mask_data_path=layer.mask_data_path,
                    color_hex=layer.color_hex,
                    generation_settings=layer.generation_settings,
                )
            )
        return states

    def has_paint_data(self, layer_id: str) -> bool:
        layer = self._layers.get(layer_id)
        if layer is None:
            return False
        mask = layer.mask_image
        if mask is None or mask.isNull():
            return False
        source = mask.convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(source.height()):
            for x in range(source.width()):
                if source.pixelColor(x, y).alpha() > 0:
                    return True
        return False

    def painted_layer_ids(self) -> list[str]:
        return [layer_id for layer_id in self._order if self.has_paint_data(layer_id)]

    def export_grayscale_masks(self, package_dir: Path, layer_order: list[str]) -> dict[str, str]:
        snapshots = self.capture_mask_snapshots(layer_order)
        return self.export_grayscale_mask_snapshots(
            package_dir=package_dir,
            layer_order=layer_order,
            mask_snapshots=snapshots,
            map_settings=self._map_settings,
        )

    def capture_mask_snapshots(self, layer_order: list[str]) -> dict[str, QImage]:
        snapshots: dict[str, QImage] = {}
        for layer_id in layer_order:
            layer = self._layers.get(layer_id)
            if layer is None:
                raise RuntimeError(f"No existe la capa '{layer_id}' para exportar máscara.")
            mask = layer.mask_image or self._new_empty_mask()
            snapshots[layer_id] = mask.copy()
        return snapshots

    @staticmethod
    def export_grayscale_mask_snapshots(
        package_dir: Path,
        layer_order: list[str],
        mask_snapshots: dict[str, QImage],
        map_settings: MapSettings,
    ) -> dict[str, str]:
        masks_dir = package_dir / "masks"
        masks_dir.mkdir(parents=True, exist_ok=True)

        exported: dict[str, str] = {}
        for index, layer_id in enumerate(layer_order):
            mask = mask_snapshots.get(layer_id)
            if mask is None:
                raise RuntimeError(f"No existe la capa '{layer_id}' para exportar máscara.")

            filename = f"{index:03d}_{_sanitize_layer_id(layer_id)}.png"
            mask_path = masks_dir / filename
            grayscale = LayerMaskManager._to_grayscale_alpha(mask)
            if grayscale.size() != LayerMaskManager._mask_size_for_settings(map_settings):
                grayscale = grayscale.scaled(
                    map_settings.mask_width,
                    map_settings.mask_height,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            if not grayscale.save(str(mask_path), "PNG"):
                raise RuntimeError(f"No se pudo exportar la máscara de la capa '{layer_id}'.")

            exported[layer_id] = mask_path.relative_to(package_dir).as_posix()

        return exported

    def _load_mask_from_layer_state(self, layer_state: LayerState, project_dir: Path) -> QImage:
        if not layer_state.mask_data_path:
            return self._new_empty_mask()

        absolute = project_dir / layer_state.mask_data_path
        if not absolute.exists():
            return self._new_empty_mask()

        loaded = QImage(str(absolute))
        if loaded.isNull():
            return self._new_empty_mask()

        loaded = loaded.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        if loaded.size() != self._mask_size():
            loaded = loaded.scaled(
                self._map_settings.mask_width,
                self._map_settings.mask_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return loaded

    def _new_empty_mask(self) -> QImage:
        image = QImage(
            self._map_settings.mask_width,
            self._map_settings.mask_height,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.transparent)
        return image

    @staticmethod
    def _to_grayscale_alpha(mask: QImage) -> QImage:
        source = mask.convertToFormat(QImage.Format.Format_ARGB32)
        grayscale = QImage(source.width(), source.height(), QImage.Format.Format_Grayscale8)
        for y in range(source.height()):
            for x in range(source.width()):
                value = source.pixelColor(x, y).alpha()
                grayscale.setPixelColor(x, y, QColor(value, value, value))
        return grayscale

    def _mask_size(self):
        return self._new_empty_mask().size()

    @staticmethod
    def _mask_size_for_settings(map_settings: MapSettings):
        image = QImage(
            map_settings.mask_width,
            map_settings.mask_height,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        return image.size()

    def _scene_to_mask_point(self, scene_point: QPointF) -> QPointF:
        scene_y_up = -scene_point.y()
        mask_x, mask_y = scene_to_mask(
            scene_x=scene_point.x(),
            scene_y=scene_y_up,
            map_settings=self._map_settings,
        )
        return QPointF(float(mask_x), float(mask_y))

    def _sync_to_paths(self, layer_paths: list[str]) -> None:
        old_layers = self._layers
        self._layers = {}
        self._order = []
        category_counts = self._count_categories_for_existing_paths(layer_paths, old_layers)

        for path in layer_paths:
            if path in old_layers:
                layer = old_layers[path]
                if layer.mask_image is None:
                    layer.mask_image = self._new_empty_mask()
                if not is_valid_hex_color(layer.color_hex):
                    category, _ = split_layer_id(path)
                    sibling_index = max(0, category_counts.get(category, 1) - 1)
                    layer.color_hex = variant_color_for_sibling(category, sibling_index)
                self._layers[path] = layer
                self._order.append(path)
                continue

            category, _ = split_layer_id(path)
            sibling_index = category_counts.get(category, 0)
            category_counts[category] = sibling_index + 1
            self._layers[path] = LayerMask(
                layer_id=path,
                display_name=path,
                color_hex=variant_color_for_sibling(category, sibling_index),
                visible=True,
                opacity=0.85,
                mask_data_path=None,
                mask_image=self._new_empty_mask(),
            )
            self._order.append(path)

    def _extract_layer_paths(self, roots: list[CollectionNode]) -> list[str]:
        paths: list[str] = []

        def visit(node: CollectionNode, prefix: str | None = None) -> None:
            if prefix is None and node.name.strip().lower() == "collection":
                for child in node.children:
                    visit(child, None)
                return
            path = node.name if prefix is None else f"{prefix}/{node.name}"
            if not node.children:
                paths.append(path)
                return
            for child in node.children:
                visit(child, path)

        for root in roots:
            visit(root, None)

        # De-dup manteniendo orden
        unique: list[str] = []
        seen: set[str] = set()
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            unique.append(path)
        return unique

    def _count_categories_for_existing_paths(
        self,
        layer_paths: list[str],
        old_layers: dict[str, LayerMask],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for path in layer_paths:
            if path not in old_layers:
                continue
            category, _ = split_layer_id(path)
            counts[category] = counts.get(category, 0) + 1
        return counts

    def _count_category_layers(self, category: str) -> int:
        total = 0
        for layer_id in self._order:
            existing_category, _ = split_layer_id(layer_id)
            if existing_category == category:
                total += 1
        return total
