# Procedural Map Designer

**Procedural Map Designer** is a Linux desktop application for creating large-scale 3D scenes procedurally. You paint 2D masks over a logical map, configure per-layer generation parameters, and let the tool drive Blender in headless mode to place and generate thousands of objects (trees, buildings, roads, terrain) in a final `.blend` file — ready for rendering or further editing.

The application bridges interactive 2D map design with fully automated 3D scene generation, with no manual Blender scripting required.

### Built for synthetic data generation

A primary use case for this tool is producing **synthetic aerial datasets** for training computer vision models. By generating diverse, configurable 3D scenes and rendering them from a top-down or oblique camera, you can produce large volumes of labelled training images for:

- **Object detection** models — trees, buildings, vehicles, and other assets appear as precisely located instances with known bounding boxes
- **Semantic segmentation** models — each asset category (vegetation, buildings, roads) maps directly to a label class, enabling pixel-accurate ground truth masks
- **Instance segmentation** models — individual object placements are tracked, enabling per-instance mask generation

Because placement is fully deterministic and parameterised, you can generate hundreds of scene variants by varying density, scale, seed, and asset mix — producing the diversity needed for robust model training without any manual labelling effort.

---

## Documentation

| Guide | Description |
|---|---|
| [Installation Guide](documentation/install.md) | Virtual environment setup, Python version, Blender installation, dependencies |
| [Blender File Configuration](documentation/blender_file_config.md) | How to structure your `.blend` asset library so the app can discover and use it |
| [Usage Guide](documentation/usage.md) | Full walkthrough of the scene creation pipeline, parameters, and generation backends |
| [How It Works](documentation/how_it_works.md) | Deep dive into the procedural placement algorithm and Geometry Nodes integration |

---

## Quick Start

1. **Prepare your asset library** — Organise your 3D objects in a `.blend` file using nested collections (`vegetation/pine_tree`, `buildings/hangar`, etc.)
2. **Open the app** — Select your Blender executable and your `.blend` file; the app inspects its collection structure automatically
3. **Configure the map** — Set real-world dimensions, mask resolution, and optionally a base terrain plane
4. **Paint your scene** — Use the 2D canvas to paint grayscale masks that control where each asset category is placed
5. **Tune parameters** — Adjust density, scale range, rotation, minimum distance, and seeding per layer
6. **Generate** — Run the pipeline; Blender executes headlessly and produces a `working_map.blend` with all objects placed
7. **Export** — Export a clean `final_map.blend` with objects neatly organised under category collections

---

## Demo

<!-- Add screenshots or screen recordings here -->
<!-- Example: ![App screenshot](documentation/images/demo_overview.png) -->
<!-- Example: ![Canvas painting](documentation/images/demo_canvas.png) -->
<!-- Example: ![Generated scene in Blender](documentation/images/demo_result.png) -->

> Screenshots coming soon.

---

## Tech Stack

- **Python 3.13** + **PySide6** — Desktop UI
- **Blender 4.x** — Headless 3D generation backend
- **NumPy / Pillow / SciPy** — Mask processing and spatial math
- **PyOpenGL** — Terrain viewport

---

## Running

```bash
# Activate your virtual environment first
source .venv/bin/activate

# Launch the app
python main.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```
