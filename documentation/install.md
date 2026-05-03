# Installation Guide

This guide covers everything needed to run MAPaint on a Linux system.

---

## System Requirements

| Component | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 22.04 / Debian 12 | Ubuntu 24.04 |
| Python | 3.11 | **3.13** |
| Blender | 3.6 | **4.2 LTS or 4.3+** |
| RAM | 8 GB | 16 GB+ |
| GPU | Optional | OpenGL 3.3+ (for terrain viewport) |

---

## 1 — Install Python 3.13

The app requires Python 3.11 or newer. Python 3.13 is the tested version.

### Check your current version

```bash
python3 --version
```

### Install Python 3.13 via deadsnakes PPA (Ubuntu)

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13 python3.13-venv python3.13-dev
```

### Verify

```bash
python3.13 --version
# Python 3.13.x
```

---

## 2 — Install Blender

MAPaint drives Blender as a headless subprocess. Blender must be installed separately and its executable path must be configured inside the app.

### Option A — Official binary (recommended)

1. Download Blender 4.2 LTS or later from [blender.org/download](https://www.blender.org/download/)
2. Extract the archive to a stable location, for example:

```bash
tar -xf blender-4.2.x-linux-x64.tar.xz -C ~/Applications/
```

3. Confirm the executable works:

```bash
~/Applications/blender-4.2.x-linux-x64/blender --version
# Blender 4.2.x
```

### Option B — Snap package

```bash
sudo snap install blender --classic
which blender   # /snap/bin/blender
```

> **Note:** The app needs the absolute path to the `blender` binary. Make a note of it — you will enter it in the app the first time you run it.

### Minimum supported Blender API features

| Feature | Minimum Blender version |
|---|---|
| Hierarchical collections | 2.80 |
| Geometry Nodes backend | 3.0 |
| Stable GN instancing | 3.6 |
| Recommended LTS | **4.2** |

---

## 3 — Clone the repository

```bash
git clone <repository-url> scene_generator
cd scene_generator
```

Or if you received the project as a ZIP archive, extract it and enter the directory:

```bash
unzip scene_generator.zip
cd scene_generator
```

---

## 4 — Create a virtual environment

Always use an isolated virtual environment to avoid conflicts with system Python packages.

```bash
# Create the environment using Python 3.13
python3.13 -m venv .venv

# Activate it
source .venv/bin/activate

# Confirm you are inside the venv
which python
# .../scene_generator/.venv/bin/python
python --version
# Python 3.13.x
```

---

## 5 — Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### What gets installed

| Package | Version | Purpose |
|---|---|---|
| `PySide6` | ≥ 6.7 | Qt 6 UI framework |
| `numpy` | ≥ 1.26 | Mask math and spatial arrays |
| `Pillow` | ≥ 10.0 | PNG mask read/write |
| `scipy` | ≥ 1.11 | Scientific computing (placement) |
| `PyOpenGL` | ≥ 3.1.7 | Terrain OpenGL viewport |
| `PyOpenGL-accelerate` | ≥ 3.1.7 | C-accelerated OpenGL bindings |

### Installing system-level OpenGL libraries (if terrain viewport fails)

```bash
sudo apt install libgl1-mesa-glx libglib2.0-0
```

---

## 6 — Run the application

```bash
# Make sure the venv is active
source .venv/bin/activate

python main.py
```

On first launch, the app will open with an empty project. You will need to:

1. Click **Configure Blender** and point it to your `blender` binary (e.g. `/home/you/Applications/blender-4.2/blender`)
2. Click **Select .blend file** and choose your asset library (see [Blender File Configuration](blender_file_config.md))

---

## 7 — Run the test suite (optional)

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

---

## Troubleshooting

### `ModuleNotFoundError: PySide6`

You are not inside the virtual environment. Run `source .venv/bin/activate` first.

### `libGL error: unable to load driver`

Missing system OpenGL libraries. Install them:

```bash
sudo apt install libgl1 libglx-mesa0
```

### Blender path not found

Confirm the path is correct:

```bash
/your/path/to/blender --version
```

The path must point directly to the `blender` binary, not to a folder.

### App window does not open (Wayland/X11 issue)

If you are on a Wayland compositor and the window does not appear, force X11 mode:

```bash
QT_QPA_PLATFORM=xcb python main.py
```

### PyOpenGL-accelerate fails to compile

The accelerate package is optional. If pip fails to build it, install without it:

```bash
pip install PyOpenGL
```

The terrain viewport will still work, just slightly slower.
