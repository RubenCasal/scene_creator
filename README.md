# Procedural Map Designer

Linux-first external desktop app in Python 3.11+ and PySide6 for preparing procedural map generation packages and running Blender batch generation.

## Current Milestones

- Milestone 1: `.blend` inspection through Blender CLI
- Milestone 2: persistent versioned project model
- Milestone 3: logical map size, mask resolution, and coordinate transforms
- Milestone 4: paintable 2D raster masks by subcollection
- Milestone 5: per-layer generation settings with persistence and validation
- Milestone 6: formal export package with `project.json` and grayscale `masks/*.png`
- Milestone 7: headless Blender validation of the exported package
- Milestone 8: Python batch generation backend using `project.json` and mask PNGs
- Milestone 9: async execution, live logs, progress states, and open-result flow
- Milestone 10: editable regeneration workflow with persisted latest-output metadata
- Milestone 11: final clean export into a separate `final_map.blend`
- Milestone 12: optional Geometry Nodes backend using the same export contract

## Architecture

```text
src/proc_map_designer/
├─ blender_bridge/
│  ├─ package_loader.py
│  └─ placement_planner.py
├─ domain/
│  ├─ export_package.py
│  ├─ models.py
│  ├─ project_state.py
│  ├─ coordinates.py
│  └─ validators.py
├─ infrastructure/
│  ├─ blender_runner.py
│  ├─ project_repository.py
│  └─ settings.py
├─ services/
│  ├─ export_package_service.py
│  ├─ validation_service.py
│  ├─ generation_service.py
│  ├─ final_export_service.py
│  ├─ generation_pipeline_service.py
│  ├─ inspection_service.py
│  └─ project_service.py
└─ ui/
   ├─ main_window.py
   ├─ map_settings_dialog.py
   ├─ map_preview_widget.py
   └─ canvas/
      ├─ canvas_view.py
      ├─ brush_tool.py
      ├─ layer_mask_manager.py
      └─ overlay_renderer.py

scripts/
├─ inspect_blend_collections.py
├─ blender_validate_project.py
├─ blender_generate_python_batch.py
├─ blender_generate_geometry_nodes.py
├─ blender_export_final_map.py
├─ blender_collection_utils.py
└─ blender_script_utils.py
```

## Product Flow

1. Select Blender executable.
2. Select a source `.blend`.
3. Inspect collections and base-plane candidates.
4. Choose logical map settings and base plane.
5. Paint layer masks.
6. Configure per-layer generation parameters.
7. Validate the exported package in headless Blender.
8. Generate a working `.blend` with `python_batch` or `geometry_nodes`.
9. Iterate on masks/settings and regenerate.
10. Export a separate final consolidated `.blend`.

## Export Package Contract

The app keeps `ProjectState` as the durable source of truth. Blender consumes a derived package:

```text
<export_dir>/
├─ project.json
└─ masks/
   ├─ 000_vegetation_pino.png
   └─ ...
```

`project.json` contains at least:

- `schema_version`
- `project_id`
- `source_blend`
- `blender_executable`
- `output_blend`
- `map.width`
- `map.height`
- `map.unit`
- `map.mask_resolution.width`
- `map.mask_resolution.height`
- `map.base_plane_object`
- `layers[].category`
- `layers[].name`
- `layers[].blender_collection`
- `layers[].enabled`
- `layers[].mask_path`
- `layers[].settings.density`
- `layers[].settings.min_distance`
- `layers[].settings.allow_overlap`
- `layers[].settings.scale_min`
- `layers[].settings.scale_max`
- `layers[].settings.rotation_random_z`
- `layers[].settings.seed`
- `layers[].settings.priority`

## Spatial Contract

- Editor logical map origin is centered at `(0, 0)`.
- Mask origin is top-left.
- `mask_to_scene` maps mask pixels into logical map space with Y flipped.
- Blender backends use the same logical width/height contract.
- Python batch places instances by transforming logical XY points through the selected base plane.
- Geometry Nodes backend uses a Python-built point-cloud intermediate and then instances through a GN modifier on those points.

## Generation Backends

### `python_batch`

Stable default backend.

- Reads `project.json` and `masks/*.png`
- Validates package first
- Processes enabled layers in descending priority order
- Uses deterministic SHA-256–derived layer seeds
- Applies density, scale range, Z rotation randomness, `min_distance`, and `allow_overlap`
- Writes a working output `.blend`

### `geometry_nodes`

Optional secondary backend.

- Uses the same `project.json` contract
- Builds a point-cloud intermediate from the exported masks
- Instances collections through a Geometry Nodes modifier
- Keeps the real selected base plane in the workflow

Limitations:

- It does not attempt perfect parity with `python_batch`
- Scale and rotation are approximated inside the node graph
- Instances remain instances; they are not automatically realized
- `python_batch` remains the default stable backend

## Final Export

Final export produces a separate `final_map.blend`.

- Working output remains available
- Generated objects/instancers are regrouped under category collections such as `vegetation` and `building`
- Instances remain instances; the export does not realize geometry destructively

## Running

```bash
python main.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```

Current automated coverage includes:

- `ProjectState` persistence and backward-compatible loading
- export contract generation
- Blender runner JSON parsing
- package loader validation
- deterministic placement planner behavior
- mask persistence/export helpers
