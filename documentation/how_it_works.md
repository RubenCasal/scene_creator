# How It Works — Procedural Generation

This document explains the technical mechanisms behind how Procedural Map Designer places objects, generates roads, and uses Blender's Geometry Nodes system.

---

## Overview

The tool uses two independent generation backends that share the same input data but differ in how they place objects inside Blender:

| Backend | Placement method | Object type | Best for |
|---|---|---|---|
| **Python Batch** | Deterministic Python algorithm | Fully realized instances | Production output, editing, synthetic data rendering |
| **Geometry Nodes** | GN modifier on a point mesh | GN instances (not realized) | Large-scale previews, high instance counts |

Both backends read the same export package (`project.json` + mask PNGs) and run inside Blender as headless Python scripts.

---

## Stage 1 — Mask-Driven Candidate Sampling

Every layer has a greyscale PNG mask painted in the app's 2D canvas. The mask encodes **placement probability**: white pixels (value 1.0) allow maximum density, black pixels (value 0.0) forbid placement, and grey values scale density proportionally.

```
Canvas mask (greyscale PNG)
          ↓
   Mask decoder (Pillow + NumPy)
          ↓
   Float array [0.0 … 1.0] per pixel
          ↓
   Candidate position sampler
   (samples N candidates proportional to mask intensity)
          ↓
   List of (x, y) positions in logical map space
```

The sampler converts mask pixel coordinates back to logical world coordinates using the map's real-world dimensions (e.g. 500 × 500 m) and the mask resolution (e.g. 1024 × 1024 px).

<!-- Add an illustration here: painted mask on left, candidate points overlaid on right -->
<!-- Example: ![Mask to candidates](images/mask_sampling.png) -->

---

## Stage 2 — Deterministic Placement Planner

The placement planner filters and finalises candidate positions using a spatial index. It is fully deterministic when a fixed seed is used.

### Algorithm

```
For each layer (processed in descending priority order):

  1. Sample candidate positions from the mask
  2. Shuffle candidates using a per-layer seed
     (seed derived from project_id + layer_id via SHA-256)
  3. For each candidate:
     a. Check min_distance constraint using a spatial index
        (KD-tree over already-accepted positions across all layers)
     b. If allow_overlap = false, reject positions too close
        to accepted positions from other layers too
     c. If terrain slope limit is set, sample terrain normal
        at this position and reject if slope exceeds the limit
     d. If max_count is set, stop once reached
     e. Accept the position → store in spatial index
  4. For each accepted position, sample:
     - Random scale in [scale_min, scale_max]
     - Random Z rotation in [-rotation_random_z, +rotation_random_z]
     - Z height from terrain heightfield (if terrain is enabled)
```

The spatial index ensures that `min_distance` is respected globally across all layers simultaneously — a tree placed by the `vegetation/pine` layer blocks a `vegetation/oak` from being too close, if overlap is disabled.

<!-- Add a diagram here showing spatial index and accepted/rejected points -->
<!-- Example: ![Placement planner diagram](images/placement_planner.png) -->

---

## Stage 3A — Python Batch Backend

The Python Batch backend uses the placement plans to create **real object instances** inside Blender.

```
Accepted placement positions
          ↓
   For each layer:
     - Find the Blender collection (e.g. "vegetation/pine_tree")
     - Get all objects inside it (the asset variants)
     - For each position:
         - Pick a random object variant from the collection
         - Duplicate (instance) it at the target position
         - Apply computed scale and Z rotation
         - Lift to terrain surface (if terrain enabled)
         - Add to output collection hierarchy
          ↓
   Save working_map.blend
```

The resulting `.blend` contains individually placed objects. Each instance is a real Blender object — it can be selected, moved, deleted, or modified in Blender after generation.

### Output collection structure

```
PM_Generated
├── vegetation
│   ├── pine_tree      (objects: PM_pine_tree_0001, PM_pine_tree_0002, …)
│   └── almond_tree    (objects: PM_almond_tree_0001, …)
└── buildings
    └── hangar         (objects: PM_hangar_0001, …)
```

---

## Stage 3B — Geometry Nodes Backend

The Geometry Nodes backend uses the **same placement planner** to compute positions, but instead of placing individual objects it creates a **point mesh** — a Blender mesh where each vertex is one placement position — and attaches a Geometry Nodes modifier that instances the asset collection on every point.

```
Accepted placement positions (x, y, z)
          ↓
   Create point mesh in Blender
   (one vertex per placement position)
          ↓
   Build GN node group programmatically:

     ┌─────────────────────────────────────────────────┐
     │  Group Input (Geometry)                         │
     │       ↓                                         │
     │  Instance on Points ←── Collection Info         │
     │       ↑                   (asset collection)    │
     │  Random Scale (Float)                           │
     │  Random Rotation (Vector Z)                     │
     │       ↓                                         │
     │  Group Output (Geometry)                        │
     └─────────────────────────────────────────────────┘

          ↓
   Attach modifier to point mesh
          ↓
   Save working_map.blend
```

The node group is built entirely in Python at runtime using `bpy.data.node_groups.new()` — no pre-made node file is needed for asset instancing. The `Instance on Points` node reads each vertex of the point mesh and places one instance of the asset collection there.

### Key GN nodes used

| Node | Purpose |
|---|---|
| `GeometryNodeInstanceOnPoints` | Places one collection instance at each point of the input geometry |
| `GeometryNodeCollectionInfo` | References the asset collection and provides its geometry |
| `FunctionNodeRandomValue` | Generates per-instance random scale and rotation values |

<!-- Add a screenshot of a GN node tree here -->
<!-- Suggested image: Blender Geometry Editor showing Instance on Points setup -->
<!-- Example: ![Geometry Nodes instance on points](images/gn_instance_on_points.png) -->

---

## Road Generation — Geometry Nodes via JSON

Roads use a different and more complex GN system. The procedural road is a fully-featured Geometry Nodes tree that extrudes geometry along a Bezier curve, adds lane markings, road borders, and optional separators for double-lane roads.

### How the road GN JSON works

The road node tree is serialized to `geometry_nodes_procedural_road.json`. This file is a complete description of the Blender node graph — every node, its type, position, input socket values, and all links between sockets:

```json
{
  "root_tree": {
    "tree_name": "Procedural Road",
    "nodes": [
      {
        "name": "Instance on Points",
        "type": "GeometryNodeInstanceOnPoints",
        "location": [-50.0, 0.0],
        "inputs": [
          { "name": "Points",    "socket_type": "NodeSocketGeometry", "is_linked": true },
          { "name": "Instance",  "socket_type": "NodeSocketGeometry", "is_linked": true },
          ...
        ]
      },
      ...
    ],
    "links": [
      { "from_node": "Curve to Mesh", "from_socket": "Mesh",
        "to_node":   "Set Material",  "to_socket": "Geometry" },
      ...
    ],
    "subtree": { ... }   ← nested node groups are embedded recursively
  }
}
```

At runtime, `build_node_tree_from_json()` reconstructs the entire node tree inside Blender by:

1. Creating each node with `group.nodes.new(node_type)`
2. Setting socket default values (positions, widths, seeds, material references)
3. Creating links between sockets: `group.links.new(from_socket, to_socket)`
4. Recursively building embedded subtrees for nested node groups

This approach makes the road GN graph **portable and version-independent** — the complete node structure is stored as plain JSON and does not require a specific Blender version to open.

> **Preferred path:** If `road.blend` already contains the `Procedural Road` node group, the app appends it directly from the `.blend` library (faster). The JSON is used only as a fallback when the `.blend` library doesn't include it.

### Road Bezier curve

The user's road waypoints (placed in the 2D canvas) are converted to a **Bezier spline** in Blender. Handle types are set to `AUTO` so Blender smooths the curve automatically. The GN modifier reads this curve and sweeps the road cross-section profile along it.

```
User waypoints (2D canvas clicks)
          ↓
   Bezier spline in Blender
   (AUTO handles for smooth interpolation)
          ↓
   GN modifier "Procedural Road"
   (extrudes profile along curve)
          ↓
   Road mesh with materials:
     Road surface / Borders / Rails / Sidewalk
```

### Configurable road parameters

| Parameter | How it reaches the GN modifier |
|---|---|
| Lane width | Modifier input socket `Lane width` |
| Resolution | Modifier input socket `Resolution` (curve subdivisions) |
| Profile (single/double) | Modifier input socket `Separator height/width/length` |
| Seed | Modifier input socket `Delete seed` (controls pothole/crack variation) |

<!-- Add an image of the road GN result in Blender viewport here -->
<!-- Example: ![Procedural road in Blender](images/gn_road_result.png) -->

---

## Terrain

If a heightfield PNG is saved (from the terrain sculpting tab), the generation backends create a subdivided plane in Blender and apply a **Displace modifier** using the heightfield as the texture. The `max_height` parameter controls the vertical scale of the displacement.

```
Heightfield PNG (greyscale, 0=low, 1=high)
          ↓
   Create subdivided plane (export_subdivision level)
          ↓
   Apply Displace modifier:
     strength = max_height
     texture = heightfield PNG
          ↓
   Terrain plane in working_map.blend
```

Object placement (both backends) samples the terrain height at each position using the same heightfield array, so objects sit correctly on the displaced surface.

---

## Export Package Contract

All backends consume the same export package, making it easy to switch backends or replay generation:

```
<export_dir>/
├── project.json          ← all settings, layer definitions, road paths, terrain config
└── masks/
    ├── 000_vegetation_pine_tree.png
    ├── 001_vegetation_almond_tree.png
    ├── 002_buildings_hangar.png
    └── ...
```

The `project.json` schema (version 3) is the single source of truth for generation. It contains every parameter needed to reproduce the output exactly — map dimensions, mask resolution, per-layer settings, road waypoints, terrain settings, Blender executable path, and output path.

---

## Summary: Full Data Flow

```
                    ┌─────────────────────────────┐
                    │     Procedural Map Designer  │
                    │         (PySide6 UI)         │
                    └──────────────┬──────────────┘
                                   │  Paint masks, set parameters
                                   ▼
                    ┌─────────────────────────────┐
                    │       Export Package         │
                    │  project.json + masks/*.png  │
                    └──────────────┬──────────────┘
                                   │  Headless Blender
                    ┌──────────────┴──────────────┐
                    │                             │
           ┌────────▼────────┐         ┌──────────▼────────┐
           │  Python Batch   │         │  Geometry Nodes   │
           │                 │         │                   │
           │ Placement planner         │ Placement planner │
           │ → real instances│         │ → point mesh      │
           │                 │         │ → GN modifier     │
           └────────┬────────┘         └──────────┬────────┘
                    │                             │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │      working_map.blend       │
                    │  (placed objects + terrain   │
                    │   + roads + materials)       │
                    └──────────────┬──────────────┘
                                   │  Render from above
                                   ▼
                    ┌─────────────────────────────┐
                    │   Synthetic aerial images   │
                    │   + ground truth labels     │
                    │  (detection / segmentation) │
                    └─────────────────────────────┘
```
