# Blender File Configuration

This guide explains how to structure your `.blend` asset library so that MAPaint can discover your 3D objects, assign them to map layers, and place them correctly during generation.

---

## Overview

The app does not create or modify your 3D models. Instead, it reads a `.blend` file you prepare in advance and uses **Blender's collection system** as a catalogue of placeable asset groups. When you run generation, the app instructs Blender (headlessly) to instance objects from those collections according to the painted masks.

Think of your `.blend` file as a **library** — you organise assets inside it, and the app reads that organisation to populate the layer panel.

---

## Collection Hierarchy

The app expects a **two-level hierarchy** of collections inside the Blender scene:

```
Scene Collection
├── vegetation              ← Category (top-level collection)
│   ├── pine_tree           ← Asset group (sub-collection)
│   ├── almond_tree         ← Asset group (sub-collection)
│   ├── oak                 ← Asset group (sub-collection)
│   └── bush                ← Asset group (sub-collection)
├── buildings               ← Category (top-level collection)
│   ├── hangar              ← Asset group (sub-collection)
│   ├── warehouse           ← Asset group (sub-collection)
│   └── small_house         ← Asset group (sub-collection)
└── rocks                   ← Category (top-level collection)
    ├── boulder_large        ← Asset group (sub-collection)
    └── pebble              ← Asset group (sub-collection)
```

### Level 1 — Category collections

These are broad semantic groups (e.g. `vegetation`, `buildings`, `rocks`, `props`). The name is free-form. The app uses it as a prefix for layer IDs.

### Level 2 — Asset group collections

Each sub-collection represents **one type of placeable asset**. The collection name becomes the layer name in the app. For example, a sub-collection called `almond_tree` under `vegetation` appears in the app as the layer `vegetation / almond_tree`.

Inside each asset group collection, place the actual mesh objects that form that asset:

```
vegetation
└── almond_tree
    ├── AlmondTree.001      ← mesh object (trunk + canopy)
    ├── AlmondTree.002      ← mesh variant
    └── AlmondTree.003      ← mesh variant
```

Multiple object variants inside the same sub-collection are supported — the placement algorithm selects among them randomly.

---

## Naming Conventions

There are no strict naming rules, but follow these conventions for clarity:

- Use **lowercase with underscores** for collection names: `pine_tree`, `small_house`
- Avoid spaces and special characters in collection names
- Collection names are used as layer identifiers in the exported `project.json`; consistent names make projects more portable

---

## Object Scale

**This is the most important configuration step.**

The app uses the map's real-world logical dimensions (e.g. 500 × 500 metres) to place objects. For the result to look correct, all objects in your `.blend` must use a **consistent, coherent scale** relative to the logical map unit.

### Rules

1. **Apply scale on all objects before using them.** In Blender, select each object, press `Ctrl+A` → `Scale`. This resets the scale to `(1, 1, 1)` with the geometry sized correctly.

2. **Match the map's unit.** If your map uses metres, a pine tree that should be 8 m tall must have an actual height of 8 Blender units (with scale applied).

3. **Be consistent across categories.** A building that is 20 m wide must be 20 Blender units wide; a bush that is 0.5 m tall must be 0.5 Blender units tall.

### Why this matters

The placement algorithm places objects by transforming 2D map coordinates into 3D world space. If an object has an unapplied scale of `(0.01, 0.01, 0.01)`, it will appear 100× smaller than intended — or if scale is `(100, 100, 100)` with tiny geometry, the collision radius and density calculations will be wrong.

### How to check scale in Blender

1. Select an object
2. Open the sidebar (`N` key) → **Item** tab
3. Check **Scale** — all three values should be `1.000`
4. If not: `Ctrl+A` → **Scale**

---

## Positioning Objects

Objects inside an asset group collection should be placed **at the world origin** (0, 0, 0) or near it. The placement algorithm ignores the original position and places each instance at the computed map location. An offset from the origin will carry over to every instance and produce floating or buried objects.

### Recommended workflow

1. Model or import the object
2. Move it so its **base is at Z = 0** (sitting on the ground plane)
3. Center it horizontally near the origin
4. Apply all transforms: `Ctrl+A` → **All Transforms**
5. Move it into the correct collection

---

## Base Terrain Plane (optional)

If your map has uneven terrain, you can include a **base plane mesh** in your `.blend` that represents the ground surface. The app can use it to:

- Align placed objects to the terrain surface
- Compute height offsets for instances

The base plane must be:

- A single **MESH** object (not a subdivision modifier without applying, not a NURBS surface)
- Visible in the scene (not hidden)
- Named clearly so you can identify it in the app's dropdown (e.g. `terrain_base`, `ground_plane`)
- Large enough to cover the full logical map extent

If you are not using terrain, leave this blank — the app places all objects at a flat Z = 0.

---

## Road Assets (optional)

If you use the road generation feature, the app references road material assets from `blender_defaults/road.blend`, which is bundled with the application. You do not need to add road meshes to your custom `.blend` — roads are generated procedurally.

---

## Full Example

Below is a complete example of a well-structured `.blend` file for a rural scene:

```
Scene Collection
├── vegetation
│   ├── almond_tree         (3 mesh variants, scale applied, base at Z=0)
│   ├── olive_tree          (2 mesh variants, scale applied)
│   ├── cypress             (1 mesh, scale applied)
│   ├── dry_bush            (4 mesh variants, scale applied)
│   └── tall_grass_patch    (2 mesh variants, scale applied)
├── buildings
│   ├── farmhouse           (1 mesh, scale applied, base at Z=0)
│   ├── barn                (1 mesh, scale applied)
│   └── stone_wall_section  (3 mesh variants, scale applied)
├── rocks
│   ├── boulder_large       (2 mesh variants, scale applied)
│   └── scatter_pebble      (5 mesh variants, scale applied)
└── terrain_base            (optional — flat or sculpted ground mesh)
```

After opening this file in the app and clicking **Inspect**, the layer panel will show:

- `vegetation / almond_tree`
- `vegetation / olive_tree`
- `vegetation / cypress`
- `vegetation / dry_bush`
- `vegetation / tall_grass_patch`
- `buildings / farmhouse`
- `buildings / barn`
- `buildings / stone_wall_section`
- `rocks / boulder_large`
- `rocks / scatter_pebble`

Each of these becomes a paintable layer on the 2D canvas.

---

## Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Objects not inside a sub-collection | Layer not appearing in the app | Move objects into a named sub-collection under a category |
| Scale not applied | Objects appear at wrong size or collision is wrong | `Ctrl+A` → Scale on all objects |
| Objects not at Z = 0 | Instances float above or sink below the ground | Move object base to Z = 0, then apply transforms |
| Empty sub-collection | Validation warning, no objects placed | Add at least one mesh object to the collection |
| Deeply nested collections (3+ levels) | Layer ID path may not resolve | Keep the hierarchy exactly 2 levels deep |
| Collection exists but is excluded from View Layer | App reports collection missing | Re-include the collection in the active View Layer |
