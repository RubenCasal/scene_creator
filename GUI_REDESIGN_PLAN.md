# GUI Modernization Plan — Scene Generator
**Target:** Deep-blue dark theme, white logos, cleaner layout, no redundant widgets.  
**Constraint:** Zero functional regression — every existing action must remain accessible.

---

## Color Palette

```
BACKGROUND     #111827   ← darkest — window base
SURFACE_1      #1f2937   ← panels, sidebars
SURFACE_2      #2d3748   ← cards, groupboxes, input fields
SURFACE_3      #374151   ← hover states, secondary buttons
BORDER         #4b5563   ← subtle separators
ACCENT         #3b82f6   ← primary blue — CTA buttons, selection highlight
ACCENT_HOVER   #60a5fa   ← lighter blue on hover
ACCENT_MUTED   #1d4ed8   ← pressed states
TEXT_PRIMARY   #f9fafb   ← main readable text
TEXT_SECONDARY #9ca3af   ← labels, placeholders, hints
TEXT_DISABLED  #6b7280   ← disabled widgets
SUCCESS        #22c55e   ← pipeline success indicator
WARNING        #f59e0b   ← warnings
DANGER         #ef4444   ← errors, destructive actions
LOG_BG         #0d1117   ← monospace log panel background
LOG_TEXT       #d1fae5   ← greenish log text (terminal feel)
```

---

## Phase 1 — QSS Global Stylesheet

**Files to create:**
- `src/proc_map_designer/ui/style/theme.qss`

**Files to modify:**
- `src/proc_map_designer/__main__.py` or app entry point — apply stylesheet at startup
- `src/proc_map_designer/ui/main_window.py` — call `app.setStyleSheet(load_theme())`

**What to style in `theme.qss`:**

```
QMainWindow, QWidget              → BACKGROUND fill
QMenuBar, QMenu                   → SURFACE_1, ACCENT highlight on hover
QToolBar                          → SURFACE_1, no border
QStatusBar                        → SURFACE_1 top border BORDER
QPushButton (default)             → SURFACE_2 bg, TEXT_PRIMARY, 4px radius, 1px BORDER
QPushButton:hover                 → SURFACE_3 bg
QPushButton:pressed               → SURFACE_2 bg, inset shadow
QPushButton[accent="true"]        → ACCENT bg, white text, no border
QPushButton[accent="true"]:hover  → ACCENT_HOVER bg
QPushButton[danger="true"]        → DANGER bg, white text
QPushButton:disabled              → SURFACE_2 bg, TEXT_DISABLED text
QLineEdit, QDoubleSpinBox,
QSpinBox, QComboBox               → SURFACE_2 bg, BORDER border, TEXT_PRIMARY text, 4px radius
QLineEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus                   → ACCENT 1px border
QCheckBox                         → TEXT_PRIMARY text, custom indicator (ACCENT fill when checked)
QLabel                            → TEXT_PRIMARY (secondary labels get TEXT_SECONDARY via property)
QTreeWidget, QListWidget,
QTableWidget                      → SURFACE_1 bg, BORDER grid lines, alternating SURFACE_2 rows
QTreeWidget::item:selected,
QListWidget::item:selected        → ACCENT bg, white text
QTabWidget::pane                  → SURFACE_1 bg, BORDER border top
QTabBar::tab                      → SURFACE_2 bg, TEXT_SECONDARY, flat bottom
QTabBar::tab:selected             → SURFACE_1 bg, ACCENT bottom-border 2px, TEXT_PRIMARY
QTabBar::tab:hover                → SURFACE_3 bg
QSplitter::handle                 → BORDER color, 1px wide
QPlainTextEdit (log)              → LOG_BG bg, LOG_TEXT color, monospace font 11pt
QSlider::groove:horizontal        → SURFACE_3, 4px height, rounded
QSlider::handle:horizontal        → ACCENT circle, 14px
QSlider::sub-page:horizontal      → ACCENT fill left of handle
QScrollBar                        → SURFACE_2 bg, SURFACE_3 handle
QGroupBox                         → SURFACE_2 bg, BORDER border, TEXT_SECONDARY title, 6px radius
QDialog                           → BACKGROUND fill
QMessageBox                       → SURFACE_1 bg
```

**How to apply:** In `main_window.py` `__init__`, after `super().__init__()`:
```python
qss_path = Path(__file__).parent / "style" / "theme.qss"
self._apply_stylesheet(qss_path)
```
Add helper:
```python
def _apply_stylesheet(self, path: Path) -> None:
    if path.exists():
        QApplication.instance().setStyleSheet(path.read_text(encoding="utf-8"))
```

---

## Phase 2 — White Logo Variants

**Files to create:**
- `logo/icon_logo_white.svg`  — copy of `icon_logo.svg` with `fill="#000000"` → `fill="#ffffff"`
- `logo/name_logo_white.svg`  — copy of `name_logo.svg` with `fill="#000000"` → `fill="#ffffff"` (also replace `#3B373A`)
- `logo/full_logo_white.svg`  — copy of `full_logo.svg` with all `#252324`/`#3B373A` fills → `#ffffff`

**Rule:** Replace every `fill="#252324"`, `fill="#3B373A"`, `fill="#000000"` with `fill="#ffffff"`. Remove or set `fill-opacity` attributes to `1`.

**Usage:**
- Window icon: `icon_logo_white.svg` (converted to `QIcon` via `QSvgRenderer` + `QPixmap`, 32×32)
- Toolbar left slot: `name_logo_white.svg` (48px tall, left of toolbar separator)
- About/splash: `full_logo_white.svg`

**Files to modify:**
- `src/proc_map_designer/ui/main_window.py` — set window icon, add logo to toolbar

```python
# In __init__, after toolbar creation:
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QIcon, QPixmap, QPainter

def _load_svg_icon(self, svg_path: Path, size: int) -> QIcon:
    renderer = QSvgRenderer(str(svg_path))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

logo_path = Path(__file__).parent.parent.parent.parent / "logo" / "icon_logo_white.svg"
self.setWindowIcon(self._load_svg_icon(logo_path, 32))
```

---

## Phase 3 — Header Bar Consolidation (remove 6 redundant labels)

**Problem:** Currently 6 QLabel rows sit above the workflow:
```
project_label        ← "Proyecto: /path/to/file.json"
blend_file_label     ← "Blend: /path/to/scene.blend"
blender_path_label   ← "Blender: /usr/bin/blender"
map_summary_label    ← "Mapa: 200×200m | Máscaras: 1024×1024"
pipeline_state_label ← "Pipeline: Idle"
latest_output_label  ← "Último resultado: ..."
step_title_label     ← "Paso 1: Configuración"
```
These consume ~140px of vertical space, repeat info already available elsewhere, and look cluttered.

**Solution:** Replace all 7 labels with a single compact `_header_bar` (QWidget, fixed 36px tall):

```
[ LOGO ]  [ project name (truncated) ]  [ map: 200×200m ]  ···  [ status pill ]  [ last result path ]
```

**Layout (horizontal, inside _header_bar):**
```
QHBoxLayout:
  ├── logo_label (QLabel, SVG icon 24px)
  ├── project_name_label (QLabel, bold, TEXT_PRIMARY, max 200px, elided)
  ├── QFrame (vertical line separator, BORDER)
  ├── map_info_label (QLabel, TEXT_SECONDARY, "200×200m · 1024px")
  ├── QSpacerItem (expanding)
  ├── pipeline_pill (QLabel, styled with border-radius, changes color: grey/blue/green/red)
  └── output_chip (QLabel, TEXT_SECONDARY, small, last output path truncated)
```

**What gets REMOVED (widget deleted, not just hidden):**
- `project_label`
- `blend_file_label`
- `blender_path_label`
- `map_summary_label`
- `pipeline_state_label`
- `latest_output_label`
- `step_title_label`

**What gets ADDED:**
- `self._header_bar` (QWidget)
- `self._header_logo` (QLabel with SVG)
- `self._header_project_name` (QLabel)
- `self._header_map_info` (QLabel)
- `self._header_pipeline_pill` (QLabel, styled dynamically)
- `self._header_output_chip` (QLabel)

**Refresh method:** `_refresh_header_bar()` — called wherever the removed labels were refreshed.  
Replaces: `_refresh_blend_label()`, `_refresh_map_summary_label()`, all `pipeline_state_label.setText()`, `latest_output_label.setText()`, `blender_path_label.setText()`, `project_label.setText()`.

**Pipeline pill colors:**
```python
PILL_STYLES = {
    "idle":       "background:#374151; color:#9ca3af;",
    "exporting":  "background:#1d4ed8; color:#bfdbfe;",
    "validating": "background:#1d4ed8; color:#bfdbfe;",
    "generating": "background:#1d4ed8; color:#bfdbfe;",
    "success":    "background:#14532d; color:#86efac;",
    "failed":     "background:#7f1d1d; color:#fca5a5;",
}
```

---

## Phase 4 — Workflow Stepper Navigation

**Problem:** `workflow_stack` (QStackedWidget) is navigated by back/next buttons buried at the bottom of each page. There is no persistent visual indicator of where the user is in the 3-step flow.

**Solution:** Replace `step_title_label` with a `_stepper_bar` (custom QWidget) that sits between `_header_bar` and `content_splitter`.

**Stepper bar layout (horizontal, fixed 44px):**
```
[  ① Setup  ]──────[  ② Paint  ]──────[  ③ Generate  ]
```
- Each step is a QPushButton (flat, no border-radius, text + step number)
- Active step: ACCENT bottom border 2px, TEXT_PRIMARY text, bold
- Completed step: SUCCESS dot indicator, TEXT_SECONDARY text
- Inactive step: TEXT_DISABLED text
- Connector lines: BORDER color

**Clicking a stepper button navigates to that step** (replaces back/next buttons for navigation).  
Back/Next buttons at step bottoms become **optional shortcut buttons** (kept for keyboard flow):
- Rename "Siguiente →" and "← Atrás" buttons, smaller, secondary style
- Or remove them entirely if stepper click covers the workflow

**Files to modify:**
- `src/proc_map_designer/ui/main_window.py`

**New widget:** `src/proc_map_designer/ui/stepper_bar.py`
```python
class StepperBar(QWidget):
    step_clicked = Signal(int)

    def __init__(self, steps: list[str], parent=None):
        ...

    def set_active_step(self, index: int) -> None: ...
    def set_step_completed(self, index: int, done: bool) -> None: ...
```

---

## Phase 5 — Setup Step Redesign

**Current problems:**
- All fields in a single column QFormLayout with no grouping
- Button labels are generic ("Seleccionar Blend", "Configurar Blender")
- No visual hierarchy

**Restructure into 2 card columns:**

**Card A — Scene Source (left, 50%):**
```
┌─ Scene Source ──────────────────────────────┐
│  [📁 Select .blend file]                    │
│  blend_file_label  (small, secondary color)  │
│  [⚙ Configure Blender executable]           │
│  blender_path_label (small, secondary color) │
└─────────────────────────────────────────────┘
```

**Card B — Map Settings (right, 50%):**
```
┌─ Map Settings ──────────────────────────────┐
│  Width:   [═══200.00 m═══]                  │
│  Height:  [═══200.00 m═══]                  │
│  Mask X:  [══════1024══════]                │
│  Mask Y:  [══════1024══════]                │
│  [⚙ Advanced map config...]                 │
└─────────────────────────────────────────────┘
```

**Card C — Output (full width below):**
```
┌─ Output ────────────────────────────────────┐
│  Path: [═══/path/to/output.blend═══] [Browse]│
│  Backend: [═══ python_batch ▾ ═══]          │
│  Terrain Material: [═══ material ▾ ═══]     │
└─────────────────────────────────────────────┘
```

**Changes:**
- Move `backend_combo` FROM the generate step INTO the output card (it belongs to setup, not generation)
- Move `terrain_material_combo` INTO the output card
- Remove the "Advanced map config" link opens `MapSettingsDialog` (same as `action_configure_map`)
- Keep `setup_next_button` at the bottom, renamed to "→ Paint" with ACCENT style

---

## Phase 6 — Paint Step Redesign

**Current problems:**
- Left panel mixes layer tree AND brush controls in a splitter — confusing
- Brush controls below the tree are hard to discover
- Road controls appear even when in layer mode (and vice versa) — causes confusion
- `roads_hint_label` is a floating hint text that looks broken

**Restructure:**

**Left panel → fixed 220px sidebar:**
```
┌─ Layers ────────────────────────────────────┐
│  [layer_tree — fills remaining space]        │
│                                              │
└──────────────────────────────────────────────┘
┌─ Brush ─────────────────────────────────────┐
│  [🖌 Paint] [⬜ Erase]   ← toggle group     │
│  Size     ░░░░░░░░░░░░░  64px               │
│  Intensity░░░░░░░░░░░░░  80%                │
└──────────────────────────────────────────────┘
```

**Road controls panel (only visible when `_editing_target == "road"`):**
```
┌─ Road ──────────────────────────────────────┐
│  Width    ░░░░░░░░░░░░░  12px               │
│  Profile  [Single ▾]                        │
│  [🗑 Remove last road]                       │
└──────────────────────────────────────────────┘
```

**Changes:**
- Remove `roads_hint_label` — the road controls panel's visibility makes intent obvious
- Remove `active_layer_label` — the selected tree item already shows the active layer
- `clear_layer_button` moves into the layer tree header as a small icon button
- Paint/Erase buttons become a `QButtonGroup` toggle bar (pill shape)
- Brush sliders get inline value labels (no separate `QLabel` — use `QSlider` with `setSuffix`-style trick)

**Files to modify:**
- `src/proc_map_designer/ui/main_window.py` — `_build_paint_step()`

---

## Phase 7 — Generate Step Redesign

**Current problems:**
- `backend_combo` at the top of generate step — better in setup
- `painted_layers_list` (left) + parameter form (right) + `painted_layers_table` (below) duplicates the layer info

**Restructure:**

Remove `painted_layers_table` entirely — the `painted_layers_list` with inline summaries is enough. The table is pure redundancy.

**Left panel — Layer list with inline stats (fixed 200px):**
```
┌─ Painted Layers ────────────────────────────┐
│  ✓ Vegetation/Tree     density: 5.0          │
│  ✓ Building/House      density: 2.0          │
│  ✗ Vegetation/Grass    (disabled)            │
│                                              │
│  3 layers · 1 disabled                      │
└──────────────────────────────────────────────┘
```

Each item in `painted_layers_list` gets a custom delegate showing layer name + density + enabled indicator. The `painted_layers_summary` label becomes a footer inside the panel.

**Right panel — Parameter form (same fields, better layout):**
```
┌─ Vegetation/Tree ───────────────────────────┐
│  [✓] Generate this layer                    │
├─────────────────────────────────────────────┤
│  Density           [═══ 5.000 ══════]       │
│  Min distance      [═══ 0.500 ══════]  m    │
│  ☐ Allow overlap                            │
├─ Scale ─────────────────────────────────────┤
│  Min  [═══ 0.800 ══]   Max  [═══ 1.200 ══] │
├─ Randomization ─────────────────────────────┤
│  Rotation Z        [═══ 180.0 ═════]  °     │
│  Seed              [═══ 42 ═════════]       │
│  Priority          [═══ 0 ══════════]       │
└──────────────────────────────────────────────┘
```

**Bottom bar:**
```
[ ← Paint ]    [ 🔍 Validate ]  [ ▶ Generate ]
```
- "Validate" = `action_validate_pipeline` (already exists)
- "Generate" = `action_generate` (already exists)
- These replace `generate_button` (keep the same connection, just new widget)

**Files to modify:**
- `src/proc_map_designer/ui/main_window.py` — `_build_generate_step()`

---

## Phase 8 — Toolbar Redesign

**Current:** Text-only toolbar actions. No icons. Repeats menu exactly.

**Changes:**
1. Add SVG icons to every action using the QIcon loading helper from Phase 2.  
   Use [Material Design Icons](https://fonts.google.com/icons) or embed minimal SVG strings directly — no external dependency needed since PySide6 bundles Qt SVG support.
2. Toolbar layout:
   ```
   [logo_name] | [New] [Open] [Save] | [Configure] | [Inspect] | [Validate] [Generate] [Export]
   ```
   - First segment: logo image (name_logo_white.svg, 80px wide)
   - `addSeparator()` between groups
   - Actions show icon only (no text) — tooltip on hover

**Icon sources (inline SVG paths, all white fill):**
| Action | Icon |
|--------|------|
| New    | document-plus |
| Open   | folder-open |
| Save   | save / floppy-disk |
| Configure Map | cog / settings |
| Validate | magnifying-glass-check |
| Generate | play-circle |
| Open Result | cube / blender icon |
| Final Export | arrow-down-tray |

**Files to modify:**
- `src/proc_map_designer/ui/main_window.py` — toolbar creation section (~lines 291–303)
- New file: `src/proc_map_designer/ui/style/icons.py` — inline SVG icon helper

---

## Phase 9 — Log Panel Styling

**Current:** Default white background `QPlainTextEdit`.

**Changes:**
- Background: LOG_BG (`#0d1117`)
- Text: LOG_TEXT (`#d1fae5`) — soft green for terminal feel
- Font: `"JetBrains Mono", "Fira Code", "Courier New"` at 10pt (monospace, fallback chain)
- Max block count: keep 700
- Add a thin header label above the log panel: "Output Log" in TEXT_SECONDARY
- Log panel height in splitter: set initial sizes so log is 20% of vertical space by default

**Color-coded prefixes** (optional enhancement):
```python
def _append_log(self, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    if "ERROR" in message:
        prefix_color = "#ef4444"
    elif "Warning" in message or "WARNING" in message:
        prefix_color = "#f59e0b"
    elif "completado" in message or "success" in message:
        prefix_color = "#22c55e"
    else:
        prefix_color = "#9ca3af"
    html = f'<span style="color:{prefix_color}">[{timestamp}]</span> <span style="color:#d1fae5">{html.escape(message)}</span>'
    self.log_panel.appendHtml(html)
```
Note: switch from `appendPlainText` to `appendHtml` — keeps the same maximum block count behavior.

**Files to modify:**
- `src/proc_map_designer/ui/main_window.py` — `_append_log()`, log panel creation
- `src/proc_map_designer/ui/style/theme.qss` — log panel rule

---

## Phase 10 — Terrain Tab Styling

**Current:** Terrain toolbar is 120px fixed width, settings panel 220px fixed. Uses default styling.

**Changes:**
- `terrain_toolbar.py`: Style tool buttons as icon-only toggle buttons, 36×36, SURFACE_2 bg, ACCENT when active
- `terrain_settings_panel.py`: Apply groupbox card style from QSS (auto-inherits)
- `terrain_viewport.py`: The OpenGL viewport background — change clear color to match BACKGROUND (`0.067, 0.094, 0.153, 1.0` in float)

**Files to modify:**
- `src/proc_map_designer/ui/terrain/terrain_toolbar.py`
- `src/proc_map_designer/ui/terrain/terrain_viewport.py` — `initializeGL()` glClearColor call
- `src/proc_map_designer/ui/terrain/terrain_settings_panel.py` — no code changes needed if QSS covers QGroupBox

---

## Phase 11 — Map Settings Dialog Styling

The dialog inherits from `QDialog` so it will pick up the QSS automatically. Only change needed:

- `map_preview_widget.py` — update `paintEvent` hard-coded colors to match theme:
  - Background: `#1f2937` (SURFACE_1)
  - Logical area fill: `#2d3748` (SURFACE_2)
  - Logical area border: `#3b82f6` (ACCENT)
  - Mask grid: `#374151` (SURFACE_3)
  - Text labels: `#f9fafb` (TEXT_PRIMARY)

**Files to modify:**
- `src/proc_map_designer/ui/map_preview_widget.py` — color constants in `paintEvent`

---

## Complete File Change Summary

| File | Action | Phase |
|------|--------|-------|
| `logo/icon_logo_white.svg` | CREATE | 2 |
| `logo/name_logo_white.svg` | CREATE | 2 |
| `logo/full_logo_white.svg` | CREATE | 2 |
| `src/proc_map_designer/ui/style/theme.qss` | CREATE | 1 |
| `src/proc_map_designer/ui/style/icons.py` | CREATE | 8 |
| `src/proc_map_designer/ui/stepper_bar.py` | CREATE | 4 |
| `src/proc_map_designer/ui/main_window.py` | MODIFY | 1,2,3,4,5,6,7,8,9 |
| `src/proc_map_designer/ui/map_preview_widget.py` | MODIFY | 11 |
| `src/proc_map_designer/ui/terrain/terrain_toolbar.py` | MODIFY | 10 |
| `src/proc_map_designer/ui/terrain/terrain_viewport.py` | MODIFY | 10 |

---

## Widget Removal Summary (functionality preserved via alternative UI)

| Widget removed | Why | Replacement |
|----------------|-----|-------------|
| `project_label` | Redundant info at top | `_header_project_name` in header bar |
| `blend_file_label` | Redundant info at top | Inline label next to blend select button |
| `blender_path_label` | Rarely needed, clutters top | Inline label next to configure button |
| `map_summary_label` | Redundant info at top | `_header_map_info` in header bar |
| `pipeline_state_label` | Redundant info at top | `_header_pipeline_pill` in header bar |
| `latest_output_label` | Redundant info at top | `_header_output_chip` in header bar |
| `step_title_label` | Replaced by stepper | `StepperBar` widget |
| `roads_hint_label` | Self-explaining UI now | Road panel only shows when road mode active |
| `active_layer_label` | Tree selection is obvious | Tree item highlight is sufficient |
| `painted_layers_table` | Duplicates list + params | Enhanced list items with inline stats |
| `backend_combo` (generate step) | Wrong step | Moved to setup step output card |

---

## Execution Order for OpenCode Agents

```
Phase 1  → QSS theme file (no Python changes, isolated)
Phase 2  → White SVG logos (file creation only)
Phase 8  → icons.py helper (new file, no deps)
Phase 4  → StepperBar widget (new file, tested standalone)
Phase 3  → Header bar (modify main_window.py, remove 7 labels)
Phase 9  → Log panel (_append_log color-coding)
Phase 5  → Setup step layout
Phase 6  → Paint step layout
Phase 7  → Generate step layout
Phase 10 → Terrain tab styling
Phase 11 → Map preview colors
Phase 1b → Wire stylesheet loading in main_window __init__
Phase 8b → Wire toolbar icons
Phase 4b → Wire StepperBar into main_window
```

---

## Testing Checklist per Phase

Each phase must pass before proceeding:

- [ ] App starts without Python errors
- [ ] All QActions still trigger correct handlers
- [ ] 3-step workflow navigation works (setup → paint → generate → back)
- [ ] Blend inspection completes and layers appear in tree
- [ ] Brush painting works on canvas
- [ ] Terrain viewport renders and sculpting works
- [ ] Generate pipeline completes and log shows output
- [ ] Map settings dialog opens and preview renders
- [ ] Project save/load round-trips correctly
- [ ] Status bar updates on pipeline state changes
