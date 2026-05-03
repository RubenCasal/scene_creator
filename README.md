<div align="center">

<img src="logo/icon_logo.svg" alt="MAPaint icon" width="96" />

<img src="logo/name_logo.svg" alt="MAPaint" width="360" />

<br/>
<br/>

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-Desktop%20GUI-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Blender](https://img.shields.io/badge/Blender-4.x-F5792A?style=for-the-badge&logo=blender&logoColor=white)
![Geometry Nodes](https://img.shields.io/badge/Geometry%20Nodes-Procedural-FFB000?style=for-the-badge)
![PyOpenGL](https://img.shields.io/badge/PyOpenGL-Terrain%20Viewport-5586A4?style=for-the-badge)
![NumPy](https://img.shields.io/badge/NumPy-Spatial%20Math-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Pillow](https://img.shields.io/badge/Pillow-Heightfields-8CAAE6?style=for-the-badge)
![SciPy](https://img.shields.io/badge/SciPy-Brush%20Filters-8A2BE2?style=for-the-badge&logo=scipy&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Primary%20Target-FCC624?style=for-the-badge&logo=linux&logoColor=black)

</div>

---

# MAPaint: A 3D scene generator for semantic data generation

**MAPaint** is a Linux-first desktop application for painting semantic map layers and converting them into fully generated 3D scenes in Blender. It combines a Qt-based editor, deterministic placement logic, Geometry Nodes driven procedural generation, editable roads, terrain texturing, and Blender subprocess automation to help you build structured synthetic environments quickly and reproducibly.

It is especially useful for workflows where a **2D semantic layout** must become a **3D world** that can later be rendered, exported, or used for **synthetic data generation**.

---

## What MAPaint does

MAPaint lets you:

- inspect a source `.blend` asset library and expose nested collections as paintable semantic layers
- paint placement masks for vegetation, buildings, and other categories on a logical map
- draw **procedural roads** directly in the editor
- assign **terrain materials** from built-in Blender material libraries
- generate scenes through either a **Python batch backend** or a **Geometry Nodes backend**
- save the full project state so generation is reproducible and deterministic
- prepare structured scenes for **semantic / synthetic dataset creation**

---

## Main capabilities

### Semantic mask painting
Paint grayscale masks for different scene categories and control how objects are distributed in the final generated `.blend`.

### Deterministic object placement
Per-layer density, overlap rules, minimum distance, scale range, rotation randomness, priority, and seed are all stored as explicit project state.

### Procedural roads
Draw roads as vector strokes instead of raster masks and generate them in Blender with reusable procedural road assets and Geometry Nodes.

### Terrain pipeline
Select built-in terrain materials and prepare the project for terrain-aware generation and future sculpt/heightfield workflows.

### Blender subprocess generation
Blender is kept as a subprocess runtime, not the main UI. MAPaint exports a package, validates it, generates the scene headlessly, and saves the result as a working `.blend`.

---

## Why this repo exists

MAPaint is designed for workflows such as:

- **semantic data generation**
- **synthetic aerial / top-down datasets**
- **procedural environment prototyping**
- **structured 3D scene authoring from semantic intent**

Because generation is reproducible and driven by explicit project state, MAPaint is suitable for producing many controlled variations of the same scene family without manual Blender setup every time.

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

| Guide | Purpose |
|---|---|
| [Installation Guide](documentation/install.md) | Set up Python, Blender, dependencies, and runtime environment |
| [Blender File Configuration](documentation/blender_file_config.md) | Structure your `.blend` asset library so MAPaint can discover and use it |
| [Usage Guide](documentation/usage.md) | End-to-end walkthrough of the authoring and generation workflow |
| [How It Works](documentation/how_it_works.md) | Technical explanation of placement, generation, and Geometry Nodes integration |

---

## Quick start

```bash
# activate the virtual environment
source .venv/bin/activate

# install dependencies
python -m pip install -r requirements.txt

# launch the app
./main.py
```

---

## Running tests

```bash
python -m unittest discover -s tests -v
```

---

## Tech stack

- **Python 3.13+**
- **PySide6** for the desktop UI
- **Blender 4.x / 5.x** as headless generation runtime
- **Geometry Nodes** for procedural road and scene generation workflows
- **NumPy / Pillow / SciPy** for masks, heightfields, sampling, and filters
- **PyOpenGL** for the terrain viewport pipeline

---

## Current direction

MAPaint is evolving toward a full semantic-to-3D authoring tool with:

- paint-driven scene composition
- procedural roads and terrain
- terrain sculpting / heightfield workflows
- deterministic asset placement
- synthetic dataset preparation
- optional AI-assisted Blender generation

---

## Branding

The real application name is **MAPaint**.
