
<p align="center">
<img src="logo/horizontal_logo.svg" alt="MAPaint icon" width="220" />
</p>



![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-Desktop%20GUI-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Blender](https://img.shields.io/badge/Blender-5.x-F5792A?style=for-the-badge&logo=blender&logoColor=white)
![Geometry Nodes](https://img.shields.io/badge/Geometry%20Nodes-Procedural-FFB000?style=for-the-badge)




---

# MAPaint: A 3D scene generator for aerial semantic data creation

**MAPaint** is a Linux desktop application for creating large-scale 3D scenes procedurally. You paint 2D masks over a logical map, configure per-layer generation parameters, and let the tool drive Blender in headless mode to place and generate thousands of objects (trees, buildings, roads, terrain) in a final `.blend` file — ready for rendering or further editing.

The application bridges interactive 2D map design with fully automated 3D scene generation, with no manual Blender scripting required.

### Built for synthetic data generation

A primary use case for this tool is producing **synthetic aerial datasets** for training computer vision models. By generating diverse, configurable 3D scenes and rendering them from a top-down or oblique camera, you can produce large volumes of labelled training images for:

- **Object detection** models — trees, buildings, vehicles, and other assets appear as precisely located instances with known bounding boxes
- **Semantic segmentation** models — each asset category (vegetation, buildings, roads) maps directly to a label class, enabling pixel-accurate ground truth masks
- **Instance segmentation** models — individual object placements are tracked, enabling per-instance mask generation

Because placement is fully deterministic and parameterised, you can generate hundreds of scene variants by varying density, scale, seed, and asset mix — producing the diversity needed for robust model training without any manual labelling effort.

---

## Core workflow

1. **Choose a source `.blend`** containing your asset collections
2. **Inspect the collection tree** and expose layers in the editor
3. **Configure the map** (logical size, mask resolution, terrain material, output path, backend)
4. **Paint semantic masks** for asset categories
5. **Draw roads** where needed
6. **Tune generation parameters** per painted layer
7. **Validate and generate** a `working_map.blend`
8. **Export** a cleaned final result if needed

---

## Repository highlights

```text
src/proc_map_designer/
├── domain/            # Pure project models, validation, transforms, rules
├── services/          # Export, generation orchestration, terrain services
├── infrastructure/    # Blender runner, settings, project repository
├── ui/                # Qt application UI, terrain viewport, paint workflow
├── blender_bridge/    # Placement planner, package loader, terrain sampler
└── ai/                # LLM-assisted Blender script generation pipeline

scripts/               # Blender-side subprocess scripts
documentation/         # Guides and implementation notes
blender_defaults/      # Built-in roads, terrain materials, and reusable assets
tests/                 # Unit tests for domain, services, and bridge logic
```

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

```bash
# Activate your virtual environment first
source .venv/bin/activate

# Launch the app
python main.py
```

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
