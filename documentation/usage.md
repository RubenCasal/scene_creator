# Usage Guide

This guide walks through the full scene creation pipeline — from opening the app to generating a final `.blend` file ready for rendering.

---

## Overview: The Three-Step Pipeline

The app divides the workflow into three sequential steps, shown in the step indicator at the top of the window:

```
[ 1. Setup ] → [ 2. Paint ] → [ 3. Generate ]
```

You always move through them in order. At any point you can go back to a previous step, adjust settings, and re-run generation.

---

## Step 1 — Setup

### 1.1 Configure Blender

Before anything else, the app needs to know where Blender is installed on your system.

Click **Configure Blender** and navigate to the `blender` executable (e.g. `/home/you/Applications/blender-4.2/blender` or `/snap/bin/blender`). The app saves this path in its settings and reuses it across projects.

### 1.2 Select a source `.blend` file

Click **Select .blend** and choose your asset library file. See [Blender File Configuration](blender_file_config.md) for how to prepare this file.

Once selected, the app runs a **headless Blender inspection** in the background. The log panel at the bottom shows its progress. When inspection completes:

- The collection tree is populated with all discovered asset groups
- Available base-plane candidates (terrain mesh objects) are listed in the dropdown

If the inspection fails, check the log panel for the error message — the most common causes are an incorrect Blender path or a `.blend` file that has no collections under Scene Collection.

### 1.3 Configure map dimensions

Click **Map Settings** or fill in the fields directly:

| Field | Description |
|---|---|
| **Map width / height** | Real-world extent of your scene in logical units (e.g. metres). A value of 500 means the scene covers 500 × 500 m. |
| **Mask width / height** | Resolution of the internal raster masks in pixels. Higher resolution = finer painting detail but larger files and slower export. 1024 × 1024 is a good default. |
| **Unit** | Label for the logical unit (m, km, cm — for display only, does not affect scale). |

### 1.4 Select a base terrain plane (optional)

If your `.blend` contains a terrain mesh, select it from the **Base plane** dropdown. The generation backend will use this mesh to:

- Lift placed objects to follow the terrain surface
- Respect terrain slope limits (if configured per-layer)

Leave this blank for completely flat scenes.

### 1.5 Configure output path

Set the path where Blender should write the generated `working_map.blend`. You can type a path directly or click **Browse** to choose a location.

When you are satisfied with the setup, click **Next →** to proceed to the Paint step.

---

## Step 2 — Paint

This is where you define _where_ each asset type appears on the map by painting grayscale masks.

### 2.1 Understanding the canvas

The canvas shows a top-down view of your logical map. Each layer in the panel on the left corresponds to one asset group from your `.blend` collection tree.

- **White** areas (value 1.0) = maximum density — assets are placed here at full configured density
- **Grey** areas (intermediate values) = proportionally reduced density
- **Black** areas (value 0.0) = no assets placed

### 2.2 Selecting a layer

Click on a layer name in the left panel to make it the active painting target. The layer's current mask is shown on the canvas. You can paint on only one layer at a time.

### 2.3 Brush tools

| Control | Action |
|---|---|
| **Left-click drag** | Paint — add mask intensity |
| **Right-click drag** | Erase — remove mask intensity |
| Scroll wheel | Zoom in/out |
| Middle-click drag | Pan the canvas |

The toolbar above the canvas contains:

| Control | Description |
|---|---|
| **Paint / Erase** buttons | Switch between paint and erase mode |
| **Brush size** slider | Radius of the brush in canvas pixels |
| **Brush intensity** slider | How strongly each stroke adds/removes mask value (0.01 = faint, 1.0 = full) |

Use low intensity and multiple passes to create natural gradual transitions between asset zones.

### 2.4 Viewing other layers

You can toggle layer visibility in the layer panel to see how different masks overlap. The canvas shows the active layer's mask overlaid on a faint preview of the logical map boundary.

### 2.5 Roads (optional)

Switch to the **Roads** tab in the layer panel to place road paths on the map.

- Click to add waypoints along the desired road path
- Set the road **width** and **profile** (single lane or double lane)
- Roads are generated procedurally using Blender's curve system — you do not need to model road geometry yourself

### 2.6 Terrain sculpting (optional)

If the **Terrain** tab is available and terrain is enabled in your project settings, you can sculpt a heightfield directly in the app's 3D terrain viewport:

- Use **Raise / Lower / Smooth / Flatten** brushes to sculpt the height map
- Set **Max height** to control the overall vertical scale
- Save the heightfield as a PNG to include it in the export package

When you are satisfied with the painted masks, click **Next →** to proceed to Generate.

---

## Step 3 — Generate

### 3.1 Per-layer generation parameters

Before generating, configure how each layer's assets are placed. Select a layer in the list and adjust its settings in the right panel:

#### Placement

| Parameter | Description |
|---|---|
| **Enabled** | If unchecked, this layer is skipped during generation. |
| **Density** | Number of instances per 100 logical units². A density of 1.0 on a 100 × 100 m map places approximately 100 instances over a fully painted region. |
| **Seed** | Fixed random seed for deterministic placement. Leave blank to randomise on each run. |
| **Allow overlap** | If disabled, the placement algorithm enforces minimum distance between all instances, regardless of layer. |
| **Min distance** | Minimum distance (in logical units) between any two instances of this layer. |
| **Priority** | Layers with higher priority are placed first. Lower-priority layers then fill in around them, respecting min-distance rules. |

#### Scale

| Parameter | Description |
|---|---|
| **Scale min / max** | Each placed instance gets a random uniform scale multiplier in this range. `1.0 / 1.0` = no scale variation. `0.8 / 1.2` = ±20% random scale. |

#### Rotation

| Parameter | Description |
|---|---|
| **Rotation random Z** | Maximum random Z-axis rotation in degrees. `180` = fully random rotation. `0` = all instances face the same direction. |

### 3.2 Choosing a generation backend

Select the backend from the **Backend** dropdown:

#### Python Batch (default — recommended)

- Reads the painted masks and `project.json`
- Runs a deterministic placement algorithm:
  - Samples candidate positions from mask intensity (denser paint = more candidates)
  - Filters candidates by min_distance, allow_overlap, slope_limit
  - Applies scale and rotation variation per-instance
- Places actual object instances in the Blender scene
- Produces a working `.blend` with fully placed, individually movable objects
- Best for scenes where you need precise control and want to edit the result in Blender

#### Geometry Nodes

- Builds a point-cloud from the painted masks
- Instances collections through a Geometry Nodes modifier
- Faster for very high instance counts
- Instances are not individually placed objects — they remain GN instances
- Scale and rotation are approximate (handled inside the node graph)
- Use this backend when you need the fastest generation and do not need to edit individual instances

### 3.3 Running the pipeline

Click **Generate** to start. The pipeline runs four stages in sequence:

```
1. Export package   → Writes project.json and mask PNGs to the export directory
2. Validation       → Headless Blender validates collections, masks, and terrain paths
3. Generation       → Headless Blender places all instances and saves working_map.blend
4. (Optional) Final export → Creates a clean final_map.blend with organised collections
```

The log panel at the bottom streams live output from each stage. Errors and warnings are colour-coded.

**Pipeline states:**

| State | Meaning |
|---|---|
| Idle | No generation running |
| Exporting | Writing project.json and mask PNGs |
| Validating | Blender checking the export package |
| Generating | Blender placing instances |
| Done | Generation complete — output path shown |
| Error | A stage failed — see log for details |

### 3.4 Opening the result

Once generation completes, a **Open result** button appears. Click it to open `working_map.blend` in Blender for review or further editing.

### 3.5 Iterating

You can go back to the Paint step, adjust masks, return to Generate, and run again. The app re-exports the updated masks and re-runs the full pipeline. Previous working outputs are overwritten.

### 3.6 Final export

When you are satisfied with the result, click **Final Export** (from the menu or the generate step). This produces a separate `final_map.blend` with objects regrouped under clean category collections (`vegetation`, `buildings`, etc.), ready for production use.

---

## Project Save / Load

Your project (all layer masks, settings, layer parameters, road paths, terrain data, and file paths) is saved in a single `.pmd` project file.

- **Save project**: `File → Save` or `Ctrl+S`
- **Save as**: `File → Save As`
- **Open project**: `File → Open` or `Ctrl+O`

The project file stores a reference to the source `.blend` path — if you move the `.blend` file, you will need to re-select it after opening the project.

---

## Workflow Tips

**Start with low density.** Set density to 0.5–1.0 initially and generate a quick preview. It is faster to increase density and regenerate than to wait for a very dense scene only to discover the result is wrong.

**Use priority to control overlap.** Give large objects (buildings, boulders) a higher priority so they are placed first. Vegetation and ground cover get lower priority and fill in around them, naturally avoiding overlap.

**Use min distance for natural spacing.** Trees in a forest can have `min_distance = 2 m` and `allow_overlap = false` for a realistic spread. Dense bushes might have `min_distance = 0` for a carpet effect.

**Seed for reproducibility.** Once you find a placement you like, note the seed values. If `Randomise seed` is enabled in the generation settings, each run produces a different result. Set a fixed seed to reproduce the same placement.

**Low mask resolution for fast iteration, high for final.** Use 512 × 512 masks while painting and testing, then switch to 2048 × 2048 for the final export.

**Keep the Python Batch backend for final output.** The Geometry Nodes backend is useful for quick previews of very large scenes, but for a production-ready file with individually editable objects, always use Python Batch for the final run.
