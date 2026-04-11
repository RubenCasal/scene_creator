from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import bpy

MATERIAL_RE = re.compile(r'Material\("([^"]+)"\)')
ROAD_MATERIAL_NAMES = ("Road", "Borders", "Rail", "Sidewalk")
ROAD_IMAGE_NAMES = ("RoadBaseColor.jpg", "RoadRoughness.jpg")
ROAD_SHADER_NODE_GROUP_NAMES = ("NodeGroup.003", "NodeGroup.004", "NodeGroup.005")
ROAD_GEOMETRY_NODE_GROUP_NAME = "Procedural Road"
ROAD_TEMPLATE_OBJECT_NAME = "Procedural Road"
ROAD_SURFACE_Z_OFFSET = -0.02
ROAD_TEMPLATE_OBJECT_TAG_KEY = "pm_road_template_object"
ROAD_MATERIAL_TAG_KEY = "pm_road_material_role"
ROAD_MATERIAL_SOURCE_KEY = "pm_road_material_source"
ROAD_IMAGE_TAG_KEY = "pm_road_image_name"
ROAD_NODE_GROUP_TAG_KEY = "pm_road_node_group_name"
SOCKET_TYPE_ALIASES = {
    "NodeSocketFloatDistance": "NodeSocketFloat",
    "NodeSocketFloatFactor": "NodeSocketFloat",
    "NodeSocketVectorTranslation": "NodeSocketVector",
    "NodeSocketVectorEuler": "NodeSocketVector",
    "NodeSocketVectorDirection": "NodeSocketVector",
}


def load_road_geometry_spec(asset_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(asset_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"No se pudo leer el asset Geometry Nodes '{asset_path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON Geometry Nodes inválido en '{asset_path}': {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("root_tree"), dict):
        raise ValueError(f"El asset Geometry Nodes '{asset_path}' no contiene root_tree válido.")
    return payload


def ensure_roads_generated(
    package,
    root_collection: bpy.types.Collection,
    base_plane: bpy.types.Object,
) -> list[dict[str, Any]]:
    visible_roads = [road for road in package.roads if road.visible]
    if not visible_roads:
        return []

    roads_collection = bpy.data.collections.new("roads")
    root_collection.children.link(roads_collection)
    summary: list[dict[str, Any]] = []
    for index, road in enumerate(visible_roads, start=1):
        road_object = create_road_curve_object(road, base_plane, index)
        roads_collection.objects.link(road_object)
        summary.append({"layer_id": road.road_id, "count": max(0, len(road.points) - 1)})
    _cleanup_road_template_artifacts()
    return summary


def ensure_road_materials() -> None:
    material_defaults = {
        "Road": (0.06, 0.06, 0.06, 1.0),
        "Borders": (0.75, 0.75, 0.75, 1.0),
        "Rail": (0.18, 0.18, 0.18, 1.0),
        "Sidewalk": (0.52, 0.52, 0.52, 1.0),
    }
    for name, color in material_defaults.items():
        material = bpy.data.materials.get(name)
        if material is None:
            material = bpy.data.materials.new(name=name)
        material.use_nodes = True
        principled = material.node_tree.nodes.get("Principled BSDF") if material.node_tree else None
        if principled is not None:
            try:
                principled.inputs["Base Color"].default_value = color
            except Exception:
                continue


def append_road_materials_from_blend(blend_path: Path) -> dict[str, bpy.types.Material]:
    if not blend_path.exists() or not blend_path.is_file():
        raise ValueError(f"No existe la librería visual Road: {blend_path}")

    _append_named_images_from_blend(blend_path, ROAD_IMAGE_NAMES, required=False)
    _append_named_node_groups_from_blend(blend_path, ROAD_SHADER_NODE_GROUP_NAMES, required=False)

    cached_materials = _find_cached_road_materials(blend_path)
    if len(cached_materials) == len(ROAD_MATERIAL_NAMES):
        _retarget_material_dependencies(cached_materials, blend_path)
        return cached_materials

    loaded_materials: list[bpy.types.Material | None]

    try:
        with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
            available = set(data_from.materials)
            unresolved = [name for name in ROAD_MATERIAL_NAMES if name not in available]
            if unresolved:
                raise ValueError(
                    "La librería visual Road no contiene los materiales requeridos: " + ", ".join(unresolved)
                )
            data_to.materials = list(ROAD_MATERIAL_NAMES)
            loaded_materials = data_to.materials
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"No se pudieron cargar materiales desde '{blend_path}': {exc}") from exc

    material_map: dict[str, bpy.types.Material] = {}
    for role, material in zip(ROAD_MATERIAL_NAMES, loaded_materials):
        if material is None:
            continue
        material[ROAD_MATERIAL_TAG_KEY] = role
        material[ROAD_MATERIAL_SOURCE_KEY] = str(blend_path.resolve())
        material_map[role] = material

    if len(material_map) != len(ROAD_MATERIAL_NAMES):
        raise ValueError(
            "No se pudieron cargar los materiales Road requeridos: "
            + ", ".join(sorted(set(ROAD_MATERIAL_NAMES) - set(material_map)))
        )
    _retarget_material_dependencies(material_map, blend_path)
    return material_map


def create_road_curve_object(road, base_plane: bpy.types.Object, index: int) -> bpy.types.Object:
    template_object = _append_or_reuse_road_template_object(road.generator.material_library_blend_path)
    if template_object is None:
        curve = bpy.data.curves.new(name=f"PM_RoadCurve_{index:03d}", type='CURVE')
        curve.dimensions = '3D'
        obj = bpy.data.objects.new(f"PM_Road_{index:03d}_{_sanitize_name(road.name)}", curve)
        modifier = obj.modifiers.new(name="PM_Road", type='NODES')
        modifier.node_group = build_road_node_group(road)
    else:
        obj = template_object.copy()
        obj.data = template_object.data.copy()
        obj.name = f"PM_Road_{index:03d}_{_sanitize_name(road.name)}"
        modifier = next((mod for mod in obj.modifiers if mod.type == 'NODES'), None)
        if modifier is None:
            modifier = obj.modifiers.new(name="PM_Road", type='NODES')
        modifier.node_group = build_road_node_group(road)

    _replace_curve_with_bezier_path(obj.data, road.points, road.closed)
    _configure_road_modifier(modifier, road)
    base_location = base_plane.matrix_world.translation.copy()
    base_location.z += ROAD_SURFACE_Z_OFFSET
    obj.location = tuple(base_location)
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj["pm_layer_id"] = road.road_id
    obj["pm_category"] = "road"
    obj["pm_backend"] = "geometry_nodes_road"
    return obj


def build_road_node_group(road) -> bpy.types.NodeTree:
    material_map = append_road_materials_from_blend(road.generator.material_library_blend_path)
    group = _append_or_reuse_geometry_node_group_from_blend(road.generator.material_library_blend_path)
    if group is None:
        spec = load_road_geometry_spec(road.generator.geometry_nodes_asset_path)
        group, interface_inputs = build_node_tree_from_json(
            spec["root_tree"],
            name=f"PM_Road_{_sanitize_name(road.road_id)}",
        )
        _enforce_set_material_nodes(group, material_map)
    else:
        group = group.copy()
        group.name = f"PM_Road_{_sanitize_name(road.road_id)}"
        interface_inputs = _index_group_interface_inputs(group)
        _enforce_set_material_nodes(group, material_map)
    _configure_road_group_profile(group, getattr(road.style, "profile", "single"))
    _apply_interface_override(interface_inputs, "Lane width", road.style.width)
    _apply_interface_override(interface_inputs, "Delete seed", int(road.generator.seed))
    _apply_interface_override(interface_inputs, "Resolution", int(road.style.resolution), apply_to_all=True)
    return group


def _replace_curve_with_bezier_path(
    curve: bpy.types.Curve,
    points: list[Any],
    closed: bool,
) -> None:
    while curve.splines:
        curve.splines.remove(curve.splines[0])
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(max(0, len(points) - 1))
    for bezier_point, road_point in zip(spline.bezier_points, points):
        bezier_point.co = (float(road_point.x), float(road_point.y), 0.0)
        bezier_point.handle_left_type = 'AUTO'
        bezier_point.handle_right_type = 'AUTO'
        bezier_point.radius = 1.0
    spline.use_cyclic_u = bool(closed)
    spline.resolution_u = 1
    curve.dimensions = '3D'
    curve.resolution_u = max(curve.resolution_u, 9)
    curve.twist_mode = 'MINIMUM'
    curve.fill_mode = 'FULL'


def _configure_road_modifier(modifier: bpy.types.NodesModifier, road) -> None:
    node_group = modifier.node_group
    if node_group is None:
        return
    inputs: dict[str, list[str]] = {}
    for item in node_group.interface.items_tree:
        if getattr(item, "item_type", None) != 'SOCKET' or getattr(item, "in_out", None) != 'INPUT':
            continue
        inputs.setdefault(item.name, []).append(item.identifier)
    _set_modifier_input(modifier, inputs, "Lane width", float(road.style.width))
    _set_modifier_input(modifier, inputs, "Delete seed", int(road.generator.seed))
    _set_modifier_input(modifier, inputs, "Resolution", int(road.style.resolution))
    profile_defaults = _road_profile_defaults(getattr(road.style, "profile", "single"))
    _set_modifier_input(modifier, inputs, "Separator height", profile_defaults["separator_height"])
    _set_modifier_input(modifier, inputs, "Separator width", profile_defaults["separator_width"])
    _set_modifier_input(modifier, inputs, "Separator lenght", profile_defaults["separator_length"])


def _set_modifier_input(
    modifier: bpy.types.NodesModifier,
    inputs: dict[str, list[str]],
    input_name: str,
    value: Any,
) -> None:
    identifiers = inputs.get(input_name, [])
    if not identifiers:
        return
    for identifier in identifiers:
        try:
            modifier[identifier] = value
        except Exception:
            continue


def _road_profile_defaults(profile: str) -> dict[str, float]:
    if profile == "double":
        return {
            "separator_height": 1.2,
            "separator_width": 0.15,
            "separator_length": 1.0,
        }
    return {
        "separator_height": 1.2,
        "separator_width": 0.15,
        "separator_length": 1.0,
    }


def _configure_road_group_profile(group: bpy.types.NodeTree, profile: str) -> None:
    if profile == "double":
        return
    _configure_main_road_subgroup_for_single(group)


def _configure_main_road_subgroup_for_single(group: bpy.types.NodeTree) -> None:
    main_road_node = group.nodes.get("Main Road")
    if main_road_node is None or getattr(main_road_node, "node_tree", None) is None:
        return

    subgroup = main_road_node.node_tree.copy()
    subgroup.name = f"{main_road_node.node_tree.name}_single"
    main_road_node.node_tree = subgroup

    group_input = subgroup.nodes.get("Group Input")
    if group_input is None:
        return

    links_to_remove = [
        link
        for link in subgroup.links
        if (
            link.from_node == group_input
            and link.from_socket.name == "Value"
            and getattr(link.to_node, "operation", None) == 'MULTIPLY'
            and link.to_socket.name == "Value"
        )
    ]
    for link in links_to_remove:
        subgroup.links.remove(link)


def build_node_tree_from_json(tree_spec: dict[str, Any], name: str | None = None) -> tuple[bpy.types.NodeTree, dict[str, list[Any]]]:
    tree_name = str(name or tree_spec.get("tree_name") or "ProceduralRoad")
    group = bpy.data.node_groups.new(name=tree_name, type="GeometryNodeTree")
    interface_inputs = _build_group_interface(group, tree_spec)

    node_lookup: dict[str, bpy.types.Node] = {}
    for node_spec in tree_spec.get("nodes", []):
        node = group.nodes.new(str(node_spec["type"]))
        node.name = str(node_spec.get("name", node.name))
        node.label = str(node_spec.get("label", ""))
        location = node_spec.get("location", [0.0, 0.0])
        if isinstance(location, list) and len(location) >= 2:
            node.location = (float(location[0]), float(location[1]))

        for key, value in node_spec.items():
            if key in {"name", "label", "type", "location", "inputs", "outputs", "subtree"}:
                continue
            if not hasattr(node, key):
                continue
            try:
                setattr(node, key, value)
            except Exception:
                continue

        subtree = node_spec.get("subtree")
        if isinstance(subtree, dict) and hasattr(node, "node_tree"):
            node.node_tree, _ = build_node_tree_from_json(subtree)

        _apply_node_input_defaults(node, node_spec.get("inputs", []))
        node_lookup[node.name] = node

    for link_spec in tree_spec.get("links", []):
        from_node = node_lookup.get(str(link_spec.get("from_node", "")))
        to_node = node_lookup.get(str(link_spec.get("to_node", "")))
        if from_node is None or to_node is None:
            continue
        from_socket = _find_socket(from_node.outputs, str(link_spec.get("from_socket", "")))
        to_socket = _find_socket(to_node.inputs, str(link_spec.get("to_socket", "")))
        if from_socket is None or to_socket is None:
            continue
        try:
            group.links.new(from_socket, to_socket)
        except Exception:
            continue
    return group, interface_inputs


def validate_road_assets(package) -> list[str]:
    errors: list[str] = []
    for road in package.roads:
        if len(road.points) < 2:
            errors.append(f"La road '{road.road_id}' debe tener al menos 2 puntos.")
        if not road.generator.geometry_nodes_asset_exists:
            errors.append(
                f"No existe el asset Geometry Nodes para '{road.road_id}': {road.generator.geometry_nodes_asset_path}"
            )
            continue
        if not road.generator.material_library_blend_exists:
            errors.append(
                f"No existe la librería visual Road para '{road.road_id}': {road.generator.material_library_blend_path}"
            )
            continue
        try:
            load_road_geometry_spec(road.generator.geometry_nodes_asset_path)
        except ValueError as exc:
            errors.append(str(exc))
        try:
            _validate_road_material_library(road.generator.material_library_blend_path)
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def _build_group_interface(group: bpy.types.NodeTree, tree_spec: dict[str, Any]) -> dict[str, list[Any]]:
    inputs_by_name: dict[str, list[Any]] = {}
    nodes = tree_spec.get("nodes", [])
    group_input_spec = next((node for node in nodes if node.get("type") == "NodeGroupInput"), None)
    group_output_spec = next((node for node in nodes if node.get("type") == "NodeGroupOutput"), None)

    if isinstance(group_input_spec, dict):
        for output_spec in group_input_spec.get("outputs", []):
            socket_name = str(output_spec.get("name", ""))
            socket_type = _normalize_socket_type(str(output_spec.get("socket_type", "NodeSocketFloat")))
            if not socket_name or socket_type == "NodeSocketVirtual":
                continue
            socket = _new_interface_socket(group, socket_name, "INPUT", socket_type)
            _apply_socket_default(socket, output_spec.get("default_value"))
            inputs_by_name.setdefault(socket_name, []).append(socket)

    if isinstance(group_output_spec, dict):
        for input_spec in group_output_spec.get("inputs", []):
            socket_name = str(input_spec.get("name", ""))
            socket_type = _normalize_socket_type(str(input_spec.get("socket_type", "NodeSocketFloat")))
            if not socket_name or socket_type == "NodeSocketVirtual":
                continue
            socket = _new_interface_socket(group, socket_name, "OUTPUT", socket_type)
            _apply_socket_default(socket, input_spec.get("default_value"))
    return inputs_by_name


def _index_group_interface_inputs(group: bpy.types.NodeTree) -> dict[str, list[Any]]:
    inputs_by_name: dict[str, list[Any]] = {}
    for item in group.interface.items_tree:
        if getattr(item, "item_type", None) != 'SOCKET':
            continue
        if getattr(item, "in_out", None) != 'INPUT':
            continue
        socket_name = str(getattr(item, "name", ""))
        if not socket_name:
            continue
        inputs_by_name.setdefault(socket_name, []).append(item)
    return inputs_by_name


def _new_interface_socket(
    group: bpy.types.NodeTree,
    socket_name: str,
    in_out: str,
    socket_type: str,
):
    normalized_type = _normalize_socket_type(socket_type)
    try:
        return group.interface.new_socket(name=socket_name, in_out=in_out, socket_type=normalized_type)
    except TypeError:
        fallback_type = _fallback_socket_type(normalized_type)
        return group.interface.new_socket(name=socket_name, in_out=in_out, socket_type=fallback_type)


def _normalize_socket_type(socket_type: str) -> str:
    if socket_type == "NodeSocketVirtual":
        return socket_type
    if socket_type in SOCKET_TYPE_ALIASES:
        return SOCKET_TYPE_ALIASES[socket_type]
    if socket_type.startswith("NodeSocketFloat"):
        return "NodeSocketFloat"
    if socket_type.startswith("NodeSocketVector"):
        return "NodeSocketVector"
    if socket_type.startswith("NodeSocketInt"):
        return "NodeSocketInt"
    if socket_type.startswith("NodeSocketBool"):
        return "NodeSocketBool"
    return socket_type


def _fallback_socket_type(socket_type: str) -> str:
    if socket_type == "NodeSocketGeometry":
        return socket_type
    if socket_type == "NodeSocketMaterial":
        return socket_type
    if socket_type == "NodeSocketObject":
        return socket_type
    if socket_type == "NodeSocketCollection":
        return socket_type
    if socket_type == "NodeSocketImage":
        return socket_type
    if socket_type == "NodeSocketColor":
        return socket_type
    if socket_type == "NodeSocketString":
        return socket_type
    if socket_type == "NodeSocketRotation":
        return socket_type
    if socket_type == "NodeSocketMatrix":
        return socket_type
    if socket_type == "NodeSocketMenu":
        return socket_type
    if socket_type == "NodeSocketFont":
        return socket_type
    return "NodeSocketFloat"


def _apply_node_input_defaults(node: bpy.types.Node, input_specs: list[dict[str, Any]]) -> None:
    for index, input_spec in enumerate(input_specs):
        socket = _resolve_input_socket(node, input_spec, index)
        if socket is None:
            continue
        if bool(input_spec.get("is_linked")):
            continue
        if "default_value" not in input_spec:
            continue
        _apply_socket_default(socket, input_spec.get("default_value"))


def _resolve_input_socket(node: bpy.types.Node, input_spec: dict[str, Any], index: int):
    socket_name = str(input_spec.get("name", "")).strip()
    if socket_name:
        socket = _find_socket(node.inputs, socket_name)
        if socket is not None:
            return socket
    if index < len(node.inputs):
        return node.inputs[index]
    return None


def _apply_socket_default(socket: Any, value: Any) -> None:
    if value is None or not hasattr(socket, "default_value"):
        return
    if isinstance(value, str):
        material_match = MATERIAL_RE.search(value)
        if material_match and hasattr(socket, "default_value"):
            material = bpy.data.materials.get(material_match.group(1))
            if material is not None:
                try:
                    socket.default_value = material
                    return
                except Exception:
                    return
        if value.startswith("<bpy_struct"):
            return
    try:
        if isinstance(value, list):
            socket.default_value = tuple(value)
        else:
            socket.default_value = value
    except Exception:
        return


def _find_socket(sockets: Any, name: str):
    for socket in sockets:
        if socket.name == name:
            return socket
    return None


def _apply_interface_override(interface_inputs: dict[str, list[Any]], name: str, value: Any, apply_to_all: bool = False) -> None:
    sockets = interface_inputs.get(name, [])
    if not sockets:
        return
    targets = sockets if apply_to_all else sockets[:1]
    for socket in targets:
        _apply_socket_default(socket, value)


def _enforce_set_material_nodes(group: bpy.types.NodeTree, material_map: dict[str, bpy.types.Material]) -> None:
    material_role_by_node_name = {
        "Set Material": "Road",
        "Set Material.002": "Borders",
        "Set Material.003": "Rail",
        "Set Material.004": "Sidewalk",
    }
    for node in group.nodes:
        if node.type == 'GROUP' and getattr(node, "node_tree", None) is not None:
            _enforce_set_material_nodes(node.node_tree, material_map)
            continue
        if node.bl_idname != "GeometryNodeSetMaterial":
            continue
        material_role = material_role_by_node_name.get(node.name)
        if material_role is None:
            continue
        material = material_map.get(material_role)
        if material is None:
            continue
        material_socket = _find_socket(node.inputs, "Material")
        if material_socket is None:
            continue
        _apply_socket_default(material_socket, material)


def _find_cached_road_materials(blend_path: Path) -> dict[str, bpy.types.Material]:
    source = str(blend_path.resolve())
    material_map: dict[str, bpy.types.Material] = {}
    for material in bpy.data.materials:
        role = material.get(ROAD_MATERIAL_TAG_KEY)
        material_source = material.get(ROAD_MATERIAL_SOURCE_KEY)
        if not isinstance(role, str) or not isinstance(material_source, str):
            continue
        if material_source != source:
            continue
        if role in ROAD_MATERIAL_NAMES:
            material_map[role] = material
    return material_map


def _append_named_images_from_blend(
    blend_path: Path,
    image_names: tuple[str, ...],
    *,
    required: bool,
) -> dict[str, bpy.types.Image]:
    cached = _find_cached_images(blend_path)
    missing = [name for name in image_names if name not in cached]
    if missing:
        loaded = _append_data_blocks_from_blend(blend_path, "images", missing, required=required)
        for name, image in zip(missing, loaded):
            if image is None:
                continue
            image[ROAD_IMAGE_TAG_KEY] = name
            image[ROAD_MATERIAL_SOURCE_KEY] = str(blend_path.resolve())
            cached[name] = image
    unresolved = [name for name in image_names if name not in cached]
    if required and unresolved:
        raise ValueError("No se pudieron cargar las texturas Road: " + ", ".join(unresolved))
    return cached


def _append_named_node_groups_from_blend(
    blend_path: Path,
    group_names: tuple[str, ...],
    *,
    required: bool,
) -> dict[str, bpy.types.NodeTree]:
    cached = _find_cached_node_groups(blend_path)
    missing = [name for name in group_names if name not in cached]
    if missing:
        loaded = _append_data_blocks_from_blend(blend_path, "node_groups", missing, required=required)
        for name, group in zip(missing, loaded):
            if group is None:
                continue
            group[ROAD_NODE_GROUP_TAG_KEY] = name
            group[ROAD_MATERIAL_SOURCE_KEY] = str(blend_path.resolve())
            cached[name] = group
    unresolved = [name for name in group_names if name not in cached]
    if required and unresolved:
        raise ValueError("No se pudieron cargar los node groups Road: " + ", ".join(unresolved))
    return cached


def _append_data_blocks_from_blend(
    blend_path: Path,
    attribute_name: str,
    names: list[str],
    *,
    required: bool,
) -> list[Any]:
    try:
        with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
            available = set(getattr(data_from, attribute_name))
            unresolved = [name for name in names if name not in available]
            if required and unresolved:
                raise ValueError(
                    f"La librería visual Road no contiene {attribute_name}: " + ", ".join(unresolved)
                )
            resolved_names = [name for name in names if name in available]
            setattr(data_to, attribute_name, resolved_names)
        return list(getattr(data_to, attribute_name))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"No se pudieron cargar {attribute_name} desde '{blend_path}': {exc}") from exc


def _find_cached_images(blend_path: Path) -> dict[str, bpy.types.Image]:
    source = str(blend_path.resolve())
    image_map: dict[str, bpy.types.Image] = {}
    for image in bpy.data.images:
        name = image.get(ROAD_IMAGE_TAG_KEY)
        image_source = image.get(ROAD_MATERIAL_SOURCE_KEY)
        if not isinstance(name, str) or not isinstance(image_source, str):
            continue
        if image_source != source:
            continue
        image_map[name] = image
    return image_map


def _find_cached_node_groups(blend_path: Path) -> dict[str, bpy.types.NodeTree]:
    source = str(blend_path.resolve())
    group_map: dict[str, bpy.types.NodeTree] = {}
    for node_group in bpy.data.node_groups:
        name = node_group.get(ROAD_NODE_GROUP_TAG_KEY)
        group_source = node_group.get(ROAD_MATERIAL_SOURCE_KEY)
        if not isinstance(name, str) or not isinstance(group_source, str):
            continue
        if group_source != source:
            continue
        group_map[name] = node_group
    return group_map


def _append_or_reuse_geometry_node_group_from_blend(blend_path: Path) -> bpy.types.NodeTree | None:
    source = str(blend_path.resolve())
    for node_group in bpy.data.node_groups:
        if node_group.get(ROAD_MATERIAL_SOURCE_KEY) != source:
            continue
        if node_group.get(ROAD_NODE_GROUP_TAG_KEY) == ROAD_GEOMETRY_NODE_GROUP_NAME:
            return node_group

    loaded = _append_data_blocks_from_blend(
        blend_path,
        "node_groups",
        [ROAD_GEOMETRY_NODE_GROUP_NAME],
        required=False,
    )
    if not loaded:
        return None
    node_group = loaded[0]
    if node_group is None:
        return None
    node_group[ROAD_NODE_GROUP_TAG_KEY] = ROAD_GEOMETRY_NODE_GROUP_NAME
    node_group[ROAD_MATERIAL_SOURCE_KEY] = source
    return node_group


def _append_or_reuse_road_template_object(blend_path: Path) -> bpy.types.Object | None:
    source = str(blend_path.resolve())
    for obj in bpy.data.objects:
        if obj.get(ROAD_TEMPLATE_OBJECT_TAG_KEY) != ROAD_TEMPLATE_OBJECT_NAME:
            continue
        if obj.get(ROAD_MATERIAL_SOURCE_KEY) != source:
            continue
        return obj

    loaded = _append_data_blocks_from_blend(
        blend_path,
        "objects",
        [ROAD_TEMPLATE_OBJECT_NAME],
        required=False,
    )
    if not loaded:
        return None
    obj = loaded[0]
    if obj is None:
        return None
    obj[ROAD_TEMPLATE_OBJECT_TAG_KEY] = ROAD_TEMPLATE_OBJECT_NAME
    obj[ROAD_MATERIAL_SOURCE_KEY] = source
    return obj


def _cleanup_road_template_artifacts() -> None:
    removable_objects = [
        obj
        for obj in bpy.data.objects
        if obj.get(ROAD_TEMPLATE_OBJECT_TAG_KEY) == ROAD_TEMPLATE_OBJECT_NAME
        and not obj.users_collection
        and not obj.users_scene
    ]
    for obj in removable_objects:
        obj_data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if obj_data is not None and getattr(obj_data, "users", 0) == 0:
            try:
                bpy.data.curves.remove(obj_data, do_unlink=True)
            except Exception:
                pass
    try:
        bpy.data.orphans_purge(do_recursive=True)
    except Exception:
        pass


def _retarget_material_dependencies(material_map: dict[str, bpy.types.Material], blend_path: Path) -> None:
    images = _find_cached_images(blend_path)
    node_groups = _find_cached_node_groups(blend_path)
    for material in material_map.values():
        if material.node_tree is None:
            continue
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and getattr(node, "image", None) is not None:
                replacement = images.get(node.image.name)
                if replacement is not None:
                    node.image = replacement
            elif node.type == 'GROUP' and getattr(node, "node_tree", None) is not None:
                replacement_group = node_groups.get(node.node_tree.name)
                if replacement_group is not None:
                    node.node_tree = replacement_group


def _validate_road_material_library(blend_path: Path) -> None:
    try:
        with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
            del data_to
            available = set(data_from.materials)
    except Exception as exc:
        raise ValueError(f"No se pudo inspeccionar la librería visual Road '{blend_path}': {exc}") from exc
    missing = [name for name in ROAD_MATERIAL_NAMES if name not in available]
    if missing:
        raise ValueError(
            f"La librería visual Road '{blend_path}' no contiene los materiales requeridos: {', '.join(missing)}"
        )


def _sanitize_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_") or "road"
