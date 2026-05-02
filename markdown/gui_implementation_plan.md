# GUI Implementation Plan — Procedural Map Designer
**Reference:** `markdown/image.png` — dark navy dashboard with teal accent, card panels, pill status badges  
**Rule:** Zero functional regression. Every signal/slot, every action, every method signature stays intact.

---

## Color Palette (use these exact hex values everywhere)

```
APP_BG        #0d1117    ← main window background (darkest)
SIDEBAR       #161b27    ← toolbar, header bar, menu bar
CARD          #1c2333    ← groupboxes, panels, raised surfaces
INPUT         #0d1117    ← input field backgrounds
SURFACE_3     #21262d    ← button default, hover states
BORDER        #30363d    ← all borders and separators
ACCENT        #00b4d8    ← primary teal — active states, CTA buttons
ACCENT_HOVER  #38bdf8    ← teal hover
ACCENT_DARK   #0e7490    ← teal pressed
TEXT_PRI      #e6edf3    ← main readable text
TEXT_SEC      #8b949e    ← labels, placeholders, form row names
TEXT_DIS      #484f58    ← disabled widgets
SUCCESS       #3fb950    ← pipeline success
WARNING       #d29922    ← warnings
DANGER        #f85149    ← errors, danger buttons
LOG_BG        #0d1117    ← log panel background
LOG_TEXT      #7ee787    ← log text (green terminal feel)
```

---

## TASK 1 — Create White SVG Logo Files

### 1a. `logo/icon_logo_white.svg`
Copy `logo/icon_logo.svg` exactly. Make ONE change: on line 11, replace:
```
fill="#000000"
```
with:
```
fill="#ffffff"
```

### 1b. `logo/name_logo_white.svg`
Copy `logo/name_logo.svg` exactly. Make these replacements (use find-and-replace-all):
- `fill="#000000"` → `fill="#ffffff"`
- `fill="#3B373A"` → `fill="#ffffff"`
- `fill="#3B373A" fill-opacity="0.84313726"` → `fill="#ffffff"`
- `fill="#3B373A" fill-opacity="0.98823529"` → `fill="#ffffff"`
- `fill="#3B373A" fill-opacity="0.95294118"` → `fill="#ffffff"`
- `fill="#252324"` → `fill="#ffffff"`
- `fill="#252324" fill-opacity="0.98431373"` → `fill="#ffffff"`

---

## TASK 2 — Create QSS Theme File

**Create new file:** `src/proc_map_designer/ui/style/theme.qss`

First create the directory: `src/proc_map_designer/ui/style/` (add empty `__init__.py` there too).

Write the following content exactly to `theme.qss`:

```css
/* ===================================================
   PROCEDURAL MAP DESIGNER — DARK THEME
   =================================================== */

/* ----- GLOBAL BASE ----- */
QMainWindow, QDialog, QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-size: 13px;
}

/* ----- MENU BAR ----- */
QMenuBar {
    background-color: #161b27;
    color: #e6edf3;
    border-bottom: 1px solid #30363d;
    padding: 2px 4px;
    spacing: 2px;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected, QMenuBar::item:pressed {
    background-color: #00b4d8;
    color: #ffffff;
}
QMenu {
    background-color: #1c2333;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px 0px;
}
QMenu::item {
    padding: 6px 28px 6px 12px;
    border-radius: 0px;
}
QMenu::item:selected {
    background-color: #00b4d8;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background-color: #30363d;
    margin: 4px 8px;
}

/* ----- TOOLBAR ----- */
QToolBar {
    background-color: #161b27;
    border: none;
    border-bottom: 1px solid #30363d;
    spacing: 4px;
    padding: 4px 8px;
}
QToolBar::separator {
    width: 1px;
    background-color: #30363d;
    margin: 4px 6px;
}
QToolButton {
    background-color: transparent;
    color: #e6edf3;
    border: none;
    border-radius: 5px;
    padding: 5px 10px;
    min-width: 28px;
    min-height: 28px;
}
QToolButton:hover {
    background-color: #30363d;
}
QToolButton:pressed, QToolButton:checked {
    background-color: #00b4d8;
    color: #ffffff;
}
QToolButton:disabled {
    color: #484f58;
}

/* ----- STATUS BAR ----- */
QStatusBar {
    background-color: #161b27;
    color: #8b949e;
    border-top: 1px solid #30363d;
    font-size: 11px;
    padding: 2px 8px;
}

/* ----- BUTTONS ----- */
QPushButton {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 28px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #8b949e;
}
QPushButton:pressed {
    background-color: #161b27;
    border-color: #30363d;
}
QPushButton:checked {
    background-color: #00b4d8;
    color: #ffffff;
    border-color: #00b4d8;
}
QPushButton:disabled {
    background-color: #161b27;
    color: #484f58;
    border-color: #21262d;
}
QPushButton[role="primary"] {
    background-color: #00b4d8;
    color: #ffffff;
    border-color: #00b4d8;
    font-weight: bold;
}
QPushButton[role="primary"]:hover {
    background-color: #38bdf8;
    border-color: #38bdf8;
}
QPushButton[role="primary"]:pressed {
    background-color: #0e7490;
    border-color: #0e7490;
}
QPushButton[role="primary"]:disabled {
    background-color: #0e7490;
    color: #484f58;
    border-color: #0e7490;
}
QPushButton[role="danger"] {
    background-color: #da3633;
    color: #ffffff;
    border-color: #da3633;
}
QPushButton[role="danger"]:hover {
    background-color: #f85149;
    border-color: #f85149;
}
QPushButton[role="flat"] {
    background-color: transparent;
    border: none;
    color: #8b949e;
    padding: 4px 8px;
    min-height: 24px;
}
QPushButton[role="flat"]:hover {
    color: #e6edf3;
    background-color: #21262d;
}

/* ----- INPUTS ----- */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 26px;
    selection-background-color: #00b4d8;
    selection-color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #00b4d8;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background-color: #0d1117;
    color: #484f58;
    border-color: #21262d;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #21262d;
    border: none;
    width: 18px;
    border-radius: 3px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #30363d;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid #8b949e;
    width: 0; height: 0;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid #8b949e;
    width: 0; height: 0;
}

/* ----- COMBOBOX ----- */
QComboBox {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 26px;
    selection-background-color: #00b4d8;
}
QComboBox:focus {
    border-color: #00b4d8;
}
QComboBox:disabled {
    color: #484f58;
    border-color: #21262d;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}
QComboBox::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8b949e;
    width: 0; height: 0;
}
QComboBox QAbstractItemView {
    background-color: #1c2333;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    selection-background-color: #00b4d8;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}

/* ----- CHECKBOX ----- */
QCheckBox {
    color: #e6edf3;
    spacing: 8px;
    background-color: transparent;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #30363d;
    border-radius: 4px;
    background-color: #0d1117;
}
QCheckBox::indicator:hover {
    border-color: #8b949e;
}
QCheckBox::indicator:checked {
    background-color: #00b4d8;
    border-color: #00b4d8;
}
QCheckBox::indicator:disabled {
    background-color: #161b27;
    border-color: #21262d;
}

/* ----- LABELS ----- */
QLabel {
    color: #e6edf3;
    background-color: transparent;
}
QLabel[role="secondary"] {
    color: #8b949e;
    font-size: 12px;
}
QLabel[role="title"] {
    color: #e6edf3;
    font-weight: bold;
    font-size: 14px;
}
QLabel[role="pill-idle"] {
    background-color: #21262d;
    color: #8b949e;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel[role="pill-running"] {
    background-color: #0e7490;
    color: #bae6fd;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel[role="pill-success"] {
    background-color: #14532d;
    color: #86efac;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel[role="pill-error"] {
    background-color: #7f1d1d;
    color: #fca5a5;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}

/* ----- SLIDERS ----- */
QSlider::groove:horizontal {
    height: 4px;
    background-color: #21262d;
    border-radius: 2px;
    margin: 0 2px;
}
QSlider::sub-page:horizontal {
    background-color: #00b4d8;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background-color: #00b4d8;
    border: 2px solid #0d1117;
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px -2px;
}
QSlider::handle:horizontal:hover {
    background-color: #38bdf8;
}

/* ----- TREE / LIST / TABLE ----- */
QTreeWidget, QListWidget, QTableWidget {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    outline: none;
    alternate-background-color: #161b27;
    gridline-color: #21262d;
}
QTreeWidget::item, QListWidget::item {
    padding: 5px 6px;
    border-radius: 4px;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #00b4d8;
    color: #ffffff;
    border-radius: 4px;
}
QTreeWidget::item:hover:!selected, QListWidget::item:hover:!selected {
    background-color: #21262d;
}
QHeaderView {
    background-color: #0d1117;
    border: none;
}
QHeaderView::section {
    background-color: #1c2333;
    color: #8b949e;
    border: none;
    border-right: 1px solid #30363d;
    border-bottom: 1px solid #30363d;
    padding: 6px 8px;
    font-size: 12px;
    font-weight: bold;
}
QHeaderView::section:last {
    border-right: none;
}
QTreeWidget::branch {
    background-color: transparent;
}

/* ----- TABS ----- */
QTabWidget::pane {
    border: 1px solid #30363d;
    border-radius: 0 6px 6px 6px;
    background-color: #0d1117;
    top: -1px;
}
QTabBar::tab {
    background-color: #161b27;
    color: #8b949e;
    border: 1px solid #30363d;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 7px 18px;
    min-width: 80px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #0d1117;
    color: #e6edf3;
    border-bottom: 2px solid #00b4d8;
}
QTabBar::tab:hover:!selected {
    background-color: #21262d;
    color: #e6edf3;
}

/* ----- SPLITTER ----- */
QSplitter::handle {
    background-color: #30363d;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

/* ----- LOG PANEL ----- */
QPlainTextEdit#log_panel {
    background-color: #0d1117;
    color: #7ee787;
    border: 1px solid #30363d;
    border-radius: 6px;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 6px;
    selection-background-color: #00b4d8;
}

/* ----- GROUPBOX (cards) ----- */
QGroupBox {
    background-color: #1c2333;
    border: 1px solid #30363d;
    border-radius: 8px;
    margin-top: 12px;
    padding: 14px 10px 10px 10px;
    color: #8b949e;
    font-size: 11px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: -7px;
    padding: 0 4px;
    background-color: #1c2333;
    color: #8b949e;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ----- FORM LAYOUT LABELS ----- */
QFormLayout QLabel {
    color: #8b949e;
    font-size: 12px;
}

/* ----- SCROLLBARS ----- */
QScrollBar:vertical {
    background-color: #0d1117;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background-color: #30363d;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #484f58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0px;
    background: none;
}
QScrollBar:horizontal {
    background-color: #0d1117;
    height: 8px;
    margin: 0;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background-color: #30363d;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #484f58;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    width: 0px;
    background: none;
}

/* ----- HEADER BAR (custom widget) ----- */
QWidget#header-bar {
    background-color: #161b27;
    border-bottom: 1px solid #30363d;
}
QLabel#hdr-project {
    color: #e6edf3;
    font-weight: bold;
    font-size: 13px;
    background-color: transparent;
}
QLabel#hdr-secondary {
    color: #8b949e;
    font-size: 12px;
    background-color: transparent;
}
QLabel#hdr-map-info {
    color: #8b949e;
    font-size: 12px;
    background-color: transparent;
}
QFrame#hdr-separator {
    color: #30363d;
    background-color: #30363d;
}

/* ----- STEP INDICATOR ----- */
QWidget#step-indicator {
    background-color: #161b27;
    border-bottom: 1px solid #30363d;
}
QPushButton#step-btn {
    background-color: transparent;
    color: #484f58;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 0px 20px;
    font-size: 13px;
    font-weight: bold;
    min-height: 38px;
}
QPushButton#step-btn:hover {
    color: #8b949e;
    background-color: transparent;
    border-bottom: 2px solid transparent;
}
QPushButton#step-btn[active="true"] {
    color: #00b4d8;
    border-bottom: 2px solid #00b4d8;
    background-color: transparent;
}
QPushButton#step-btn[done="true"] {
    color: #3fb950;
    border-bottom: 2px solid transparent;
    background-color: transparent;
}

/* ----- DIALOG ----- */
QDialog {
    background-color: #0d1117;
}
QDialogButtonBox QPushButton {
    min-width: 80px;
}

/* ----- MESSAGE BOX ----- */
QMessageBox {
    background-color: #1c2333;
}
QMessageBox QLabel {
    color: #e6edf3;
}
```

---

## TASK 3 — Apply Theme in `src/proc_map_designer/app.py`

**File:** `src/proc_map_designer/app.py`

**Step 3a.** Add these two imports at the top of the file, after the existing imports (after line 9, `from PySide6.QtWidgets import QApplication`):

```python
from pathlib import Path as _Path
```
(Note: `Path` is already imported via main.py bootstrap but NOT inside app.py. Add it here.)

Actually `Path` is not imported in app.py. Add to imports block:
```python
from pathlib import Path
```

**Step 3b.** In the `run_app()` function, after the line `app = QApplication(sys.argv)` (currently line 25), add the following 5 lines:

```python
    _qss_path = Path(__file__).parent / "ui" / "style" / "theme.qss"
    if _qss_path.exists():
        app.setStyleSheet(_qss_path.read_text(encoding="utf-8"))
```

No other changes to `app.py`.

---

## TASK 4 — Modify `src/proc_map_designer/ui/main_window.py`

This is the largest task. Follow the sub-tasks in order.

### 4a. Update Imports

**At line 7**, change:
```python
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
```
to:
```python
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtSvg import QSvgRenderer
```
(Add the new import as a new line immediately after line 7.)

**At line 8**, change:
```python
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont
```
to:
```python
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont, QPainter, QPixmap
```

**In the `from PySide6.QtWidgets import (...)` block (lines 9–37)**, add `QFrame` and `QHBoxLayout` is already there, but add `QFrame` after `QFileDialog,`:
```python
    QFrame,
```

**After all PySide6 imports (after line 37)**, add:
```python
import html as _html
```

### 4b. Replace 7 Info Labels + Step Title in `_build_ui()`

**Current code lines 313–338** (the seven label additions):
```python
        self.project_label = QLabel("Proyecto: sin guardar")
        self.project_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root_layout.addWidget(self.project_label)

        self.blend_file_label = QLabel("Blend fuente: ninguno")
        self.blend_file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root_layout.addWidget(self.blend_file_label)

        self.blender_path_label = QLabel()
        root_layout.addWidget(self.blender_path_label)

        self.map_summary_label = QLabel()
        root_layout.addWidget(self.map_summary_label)

        self.pipeline_state_label = QLabel("Pipeline: inactivo")
        root_layout.addWidget(self.pipeline_state_label)

        self.latest_output_label = QLabel("Último resultado: ninguno")
        self.latest_output_label.setWordWrap(True)
        root_layout.addWidget(self.latest_output_label)

        self.step_title_label = QLabel("Paso 1 de 3: Selección y configuración")
        step_font = QFont()
        step_font.setBold(True)
        self.step_title_label.setFont(step_font)
        root_layout.addWidget(self.step_title_label)
```

**Replace ALL of the above with:**
```python
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header_bar = self._build_header_bar()
        root_layout.addWidget(header_bar)

        step_indicator = self._build_step_indicator()
        root_layout.addWidget(step_indicator)
```

Also change line 309–311 (root_layout margins and spacing) — they will now be set inside the replacement block above, so remove the duplicate:
```python
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)
```
Change to:
```python
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
```
(The setContentsMargins and setSpacing in the replacement block above are redundant — just do it once at the layout creation.)

Add a small content margin wrapper inside the splitter area. After `root_layout.addWidget(self.content_splitter, stretch=1)`, add:
```python
        # Add 8px padding around the workflow content
        self.content_splitter.setContentsMargins(8, 6, 8, 6)
```

### 4c. Add `_build_header_bar()` Method

Add this new method to the `MainWindow` class, **before** `_build_setup_step()` (insert before line 363):

```python
    def _build_header_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("header-bar")
        bar.setFixedHeight(44)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        # Logo icon
        logo_path = Path(__file__).resolve().parents[3] / "logo" / "icon_logo_white.svg"
        if logo_path.exists():
            renderer = QSvgRenderer(str(logo_path))
            pixmap = QPixmap(26, 26)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            logo_lbl = QLabel()
            logo_lbl.setPixmap(pixmap)
            logo_lbl.setFixedSize(26, 26)
            layout.addWidget(logo_lbl)

        # Project name label (reuses self.project_label so _refresh_project_label() works)
        self.project_label = QLabel("sin guardar")
        self.project_label.setObjectName("hdr-project")
        self.project_label.setMaximumWidth(220)
        layout.addWidget(self.project_label)

        # Vertical separator
        sep1 = QFrame()
        sep1.setObjectName("hdr-separator")
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFixedSize(1, 22)
        layout.addWidget(sep1)

        # Map summary label (reuses self.map_summary_label)
        self.map_summary_label = QLabel("—")
        self.map_summary_label.setObjectName("hdr-map-info")
        layout.addWidget(self.map_summary_label)

        layout.addStretch(1)

        # Blend file label (reuses self.blend_file_label)
        self.blend_file_label = QLabel("ninguno")
        self.blend_file_label.setObjectName("hdr-secondary")
        self.blend_file_label.setMaximumWidth(260)
        layout.addWidget(self.blend_file_label)

        # Vertical separator
        sep2 = QFrame()
        sep2.setObjectName("hdr-separator")
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFixedSize(1, 22)
        layout.addWidget(sep2)

        # Pipeline status pill (reuses self.pipeline_state_label)
        self.pipeline_state_label = QLabel("Inactivo")
        self.pipeline_state_label.setObjectName("pipeline-pill")
        self.pipeline_state_label.setProperty("role", "pill-idle")
        layout.addWidget(self.pipeline_state_label)

        # Latest output (reuses self.latest_output_label) — hidden in header, kept for refresh compat
        self.latest_output_label = QLabel()
        self.latest_output_label.setVisible(False)

        # Blender path label — hidden, kept for refresh compat
        self.blender_path_label = QLabel()
        self.blender_path_label.setVisible(False)

        return bar
```

### 4d. Add `_build_step_indicator()` Method

Add this new method immediately after `_build_header_bar()`:

```python
    def _build_step_indicator(self) -> QWidget:
        container = QWidget()
        container.setObjectName("step-indicator")
        container.setFixedHeight(40)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        self._step_buttons: list[QPushButton] = []
        step_labels = ["① Setup", "② Paint", "③ Generate"]
        for i, label in enumerate(step_labels):
            btn = QPushButton(label)
            btn.setObjectName("step-btn")
            btn.setProperty("active", "false")
            btn.setProperty("done", "false")
            # Clicking step buttons uses the validated navigation methods
            if i == 0:
                btn.clicked.connect(lambda: self._set_workflow_step(0))
            elif i == 1:
                btn.clicked.connect(self._go_to_paint_step)
            else:
                btn.clicked.connect(self._go_to_generate_step)
            layout.addWidget(btn)
            self._step_buttons.append(btn)

        layout.addStretch(1)
        return container
```

### 4e. Update `_set_workflow_step()` to Drive Step Indicator

**Current method at lines 742–750:**
```python
    def _set_workflow_step(self, index: int) -> None:
        index = max(0, min(2, index))
        self.workflow_stack.setCurrentIndex(index)
        titles = {
            0: "Paso 1 de 3: Selección y configuración",
            1: "Paso 2 de 3: Pintado por colección",
            2: "Paso 3 de 3: Parámetros y generación",
        }
        self.step_title_label.setText(titles.get(index, "Workflow"))
```

**Replace with:**
```python
    def _set_workflow_step(self, index: int) -> None:
        index = max(0, min(2, index))
        self.workflow_stack.setCurrentIndex(index)
        if hasattr(self, "_step_buttons"):
            for i, btn in enumerate(self._step_buttons):
                btn.setProperty("active", "true" if i == index else "false")
                btn.setProperty("done", "true" if i < index else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
```

### 4f. Update `_refresh_project_label()`

**Current lines 1401–1405:**
```python
    def _refresh_project_label(self) -> None:
        if self._project_file_path:
            self.project_label.setText(f"Proyecto: {self._project_file_path}")
        else:
            self.project_label.setText("Proyecto: sin guardar")
```

**Replace with:**
```python
    def _refresh_project_label(self) -> None:
        if self._project_file_path:
            name = self._project_file_path.stem
            self.project_label.setText(name)
            self.project_label.setToolTip(str(self._project_file_path))
        else:
            self.project_label.setText("sin guardar")
            self.project_label.setToolTip("Proyecto no guardado")
```

### 4g. Update `_refresh_blend_label()`

**Current lines 1407–1411:**
```python
    def _refresh_blend_label(self) -> None:
        if self._project_state.source_blend:
            self.blend_file_label.setText(f"Blend fuente: {self._project_state.source_blend}")
        else:
            self.blend_file_label.setText("Blend fuente: ninguno")
```

**Replace with:**
```python
    def _refresh_blend_label(self) -> None:
        if self._project_state.source_blend:
            blend_name = Path(self._project_state.source_blend).name
            self.blend_file_label.setText(f"⬡  {blend_name}")
            self.blend_file_label.setToolTip(self._project_state.source_blend)
        else:
            self.blend_file_label.setText("⬡  sin .blend")
            self.blend_file_label.setToolTip("No se ha seleccionado archivo .blend")
```

### 4h. Update `_refresh_map_summary_label()`

**Current lines 1425–1432:**
```python
    def _refresh_map_summary_label(self) -> None:
        settings = self._project_state.map_settings
        self.map_summary_label.setText(
            "Mapa: "
            f"{settings.logical_width:.2f} x {settings.logical_height:.2f} {settings.logical_unit} | "
            f"máscaras {settings.mask_width}x{settings.mask_height} | "
            f"terrain: {settings.terrain_material_id}"
        )
```

**Replace with:**
```python
    def _refresh_map_summary_label(self) -> None:
        settings = self._project_state.map_settings
        self.map_summary_label.setText(
            f"{settings.logical_width:.0f}×{settings.logical_height:.0f} {settings.logical_unit}"
            f"  ·  {settings.mask_width}×{settings.mask_height}px"
        )
        self.map_summary_label.setToolTip(
            f"Mapa lógico: {settings.logical_width:.2f} x {settings.logical_height:.2f} {settings.logical_unit}\n"
            f"Resolución máscaras: {settings.mask_width} x {settings.mask_height}\n"
            f"Material terrain: {settings.terrain_material_id}"
        )
```

### 4i. Update `_refresh_pipeline_state_label()`

**Current lines 1434–1446:**
```python
    def _refresh_pipeline_state_label(self) -> None:
        labels = {
            "idle": "inactivo",
            ...
        }
        state = labels.get(self._pipeline_state.current_stage, self._pipeline_state.current_stage)
        self.pipeline_state_label.setText(f"Pipeline: {state}")
```

**Replace with:**
```python
    def _refresh_pipeline_state_label(self) -> None:
        stage = self._pipeline_state.current_stage
        display = {
            "idle":       ("Inactivo",   "pill-idle"),
            "exporting":  ("Exportando", "pill-running"),
            "validating": ("Validando",  "pill-running"),
            "generating": ("Generando",  "pill-running"),
            "finalizing": ("Finalizando","pill-running"),
            "validated":  ("Validado",   "pill-success"),
            "completed":  ("Listo",      "pill-success"),
            "failed":     ("Error",      "pill-error"),
        }
        text, role = display.get(stage, (stage, "pill-idle"))
        self.pipeline_state_label.setText(text)
        self.pipeline_state_label.setProperty("role", role)
        self.pipeline_state_label.style().unpolish(self.pipeline_state_label)
        self.pipeline_state_label.style().polish(self.pipeline_state_label)
```

### 4j. Update `_append_log()` for Colored HTML Log

**Current lines 1837–1840:**
```python
    @Slot(str)
    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_panel.appendPlainText(f"[{timestamp}] {message}")
```

**Replace with:**
```python
    @Slot(str)
    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg_escaped = _html.escape(message)
        ts_escaped = _html.escape(timestamp)
        if "ERROR" in message or "Error" in message:
            msg_color = "#f85149"
        elif "Warning" in message or "WARNING" in message:
            msg_color = "#d29922"
        elif "completado" in message or "guardado" in message or "success" in message.lower():
            msg_color = "#7ee787"
        else:
            msg_color = "#7ee787"
        ts_html = f'<span style="color:#484f58">[{ts_escaped}]</span>'
        msg_html = f'<span style="color:{msg_color}">{msg_escaped}</span>'
        self.log_panel.appendHtml(f'{ts_html} {msg_html}')
```

Also add `self.log_panel.setObjectName("log_panel")` after the log panel is created (after line 351 where `self.log_panel = QPlainTextEdit()` is):

Insert after `self.log_panel = QPlainTextEdit()`:
```python
        self.log_panel.setObjectName("log_panel")
```

### 4k. Add "primary" Role to Key Buttons

These changes must be made WITHIN the `_build_setup_step()`, `_build_paint_step()`, and `_build_generate_step()` methods. Find the button creation lines and add `setProperty("role", "primary")` after creation:

**In `_build_setup_step()`:**
After `self.setup_next_button = QPushButton("Next")` (line ~431), add:
```python
        self.setup_next_button.setProperty("role", "primary")
```

**In `_build_paint_step()`:**
After `self.paint_next_button = QPushButton("Next")` (line ~591), add:
```python
        self.paint_next_button.setProperty("role", "primary")
```

After `self.paint_back_button = QPushButton("Back")` (line ~587), add:
```python
        self.paint_back_button.setProperty("role", "flat")
```

**In `_build_generate_step()`:**
After `self.generate_button = QPushButton("Generate")` (line ~711), add:
```python
        self.generate_button.setProperty("role", "primary")
```

After `self.generate_back_button = QPushButton("Back")` (line ~707), add:
```python
        self.generate_back_button.setProperty("role", "flat")
```

**In `_build_setup_step()`:**
After `self.select_blend_button = QPushButton("Seleccionar .blend")` (line ~376), add:
```python
        self.select_blend_button.setProperty("role", "primary")
```

### 4l. Wrap Setup Step Content in GroupBoxes

**In `_build_setup_step()`**, after the `intro` label and before `controls_layout`, wrap the content in GroupBoxes. Replace everything from `controls_layout = QHBoxLayout()` through `layout.addLayout(form_layout)` with:

```python
        # ── Group A: Scene Source ──────────────────────────────────
        source_group = QGroupBox("Scene Source")
        source_layout = QVBoxLayout(source_group)
        source_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        self.select_blend_button = QPushButton("Seleccionar .blend")
        self.select_blend_button.setProperty("role", "primary")
        self.select_blend_button.clicked.connect(self._on_select_blend)
        btn_row.addWidget(self.select_blend_button)

        self.configure_blender_button = QPushButton("Configurar Blender")
        self.configure_blender_button.clicked.connect(self._on_configure_blender)
        btn_row.addWidget(self.configure_blender_button)
        btn_row.addStretch(1)
        source_layout.addLayout(btn_row)

        self.blender_path_label = QLabel()
        self.blender_path_label.setWordWrap(True)
        self.blender_path_label.setProperty("role", "secondary")
        source_layout.addWidget(self.blender_path_label)
        layout.addWidget(source_group)

        # ── Group B: Map Settings ──────────────────────────────────
        map_group = QGroupBox("Map Settings")
        map_form = QFormLayout(map_group)
        map_form.setSpacing(8)

        self.setup_map_width_spin = QDoubleSpinBox()
        self.setup_map_width_spin.setRange(1.0, 100000.0)
        self.setup_map_width_spin.setDecimals(2)
        self.setup_map_width_spin.editingFinished.connect(self._on_setup_map_changed)
        map_form.addRow("Width", self.setup_map_width_spin)

        self.setup_map_height_spin = QDoubleSpinBox()
        self.setup_map_height_spin.setRange(1.0, 100000.0)
        self.setup_map_height_spin.setDecimals(2)
        self.setup_map_height_spin.editingFinished.connect(self._on_setup_map_changed)
        map_form.addRow("Height", self.setup_map_height_spin)

        self.setup_mask_width_spin = QSpinBox()
        self.setup_mask_width_spin.setRange(1, 8192)
        self.setup_mask_width_spin.editingFinished.connect(self._on_setup_map_changed)
        map_form.addRow("Mask W", self.setup_mask_width_spin)

        self.setup_mask_height_spin = QSpinBox()
        self.setup_mask_height_spin.setRange(1, 8192)
        self.setup_mask_height_spin.editingFinished.connect(self._on_setup_map_changed)
        map_form.addRow("Mask H", self.setup_mask_height_spin)

        self.terrain_material_combo = QComboBox()
        self.terrain_material_combo.currentIndexChanged.connect(self._on_terrain_material_changed)
        map_form.addRow("Terrain texture", self.terrain_material_combo)
        layout.addWidget(map_group)

        # ── Group C: Output ────────────────────────────────────────
        output_group = QGroupBox("Output")
        output_form = QFormLayout(output_group)
        output_form.setSpacing(8)

        output_row = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Ruta de salida/resultados")
        self.output_path_edit.editingFinished.connect(self._on_output_path_changed)
        output_row.addWidget(self.output_path_edit)
        self.browse_output_button = QPushButton("…")
        self.browse_output_button.setFixedWidth(36)
        self.browse_output_button.clicked.connect(self._browse_output_path)
        output_row.addWidget(self.browse_output_button)
        output_widget = QWidget()
        output_widget.setLayout(output_row)
        output_form.addRow("Path", output_widget)
        layout.addWidget(output_group)
```

Keep `layout.addStretch(1)` and the nav_layout with `setup_next_button` as-is after the groups.

**Important:** The `intro` QLabel at lines 369–373 can be REMOVED (the step indicator already communicates context). Delete:
```python
        intro = QLabel(
            "Selecciona el archivo .blend, configura Blender y define el tamaño del mapa antes de continuar."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
```

### 4m. Improve Paint Step Labels

**In `_build_paint_step()`**, remove the `intro` label (lines 444–448):
```python
        intro = QLabel(
            "Pinta las subcollections que quieres generar. Al continuar solo aparecerán las capas que tengan pintura."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
```

**Change `layer_title` styling** (after `layer_title = QLabel("Capas pintables")`):
```python
        layer_title.setProperty("role", "secondary")
```
Remove the bold font code for `layer_title` (delete lines 468–470 that set `layer_font.setBold(True)` and `layer_title.setFont(layer_font)`).

**Remove `roads_hint_label`** (lines 492–496) — this hint is replaced by tooltip. Delete:
```python
        self.roads_hint_label = QLabel(
            "Road aparece en este árbol aunque no exista en el .blend. Selecciona 'Road > Nueva road' para dibujar carreteras procedurales."
        )
        self.roads_hint_label.setWordWrap(True)
        controls_layout.addWidget(self.roads_hint_label)
```

After deletion, add a tooltip to `self.layer_tree` instead. After `self.layer_tree.itemSelectionChanged.connect(...)` add:
```python
        self.layer_tree.setToolTip(
            "Road aparece aquí aunque no exista en el .blend.\n"
            "Selecciona 'Road > Nueva road' para dibujar carreteras procedurales."
        )
```

**Remove `active_layer_label`** (lines 498–499):
```python
        self.active_layer_label = QLabel("Capa activa: ninguna")
        controls_layout.addWidget(self.active_layer_label)
```
**KEEP** `self.active_layer_label` as a hidden widget (it may be referenced elsewhere). Replace the two deleted lines with:
```python
        self.active_layer_label = QLabel()
        self.active_layer_label.setVisible(False)
```

**Update brush size label** — the label shows current value inline, which is good. No change needed to behavior, only appearance is from QSS.

### 4n. Remove Generate Step Intro + Style

**In `_build_generate_step()`**, remove the intro label (lines 604–608):
```python
        intro = QLabel(
            "Ajusta los parámetros solo para las capas pintadas y genera el mapa. Las capas no pintadas no aparecen aquí."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
```

**Style the `parameter_layer_label`** — after it is created (line 641), add:
```python
        self.parameter_layer_label.setProperty("role", "title")
```

---

## TASK 5 — Modify `src/proc_map_designer/ui/map_preview_widget.py`

**File:** `src/proc_map_designer/ui/map_preview_widget.py`

Replace all hard-coded colors in `paintEvent` with dark-theme equivalents.

**Line 25:** Change:
```python
        painter.fillRect(self.rect(), QColor("#f4f4f4"))
```
to:
```python
        painter.fillRect(self.rect(), QColor("#0d1117"))
```

**Line 33:** Change:
```python
        painter.setPen(QPen(QColor("#d0d0d0"), 1, Qt.PenStyle.DashLine))
```
to:
```python
        painter.setPen(QPen(QColor("#30363d"), 1, Qt.PenStyle.DashLine))
```

**Line 42:** Change:
```python
        painter.setPen(QPen(QColor("#255aa8"), 2))
        painter.setBrush(QColor(90, 140, 210, 35))
```
to:
```python
        painter.setPen(QPen(QColor("#00b4d8"), 2))
        painter.setBrush(QColor(0, 180, 216, 30))
```

**Lines 46–48:** Change:
```python
        painter.setPen(QPen(QColor("#255aa8"), 1))
        painter.drawLine(map_x + map_w / 2.0, map_y, map_x + map_w / 2.0, map_y + map_h)
        painter.drawLine(map_x, map_y + map_h / 2.0, map_x + map_w, map_y + map_h / 2.0)
```
to:
```python
        painter.setPen(QPen(QColor("#30363d"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(map_x + map_w / 2.0, map_y, map_x + map_w / 2.0, map_y + map_h)
        painter.drawLine(map_x, map_y + map_h / 2.0, map_x + map_w, map_y + map_h / 2.0)
```

**Line 50:** Change:
```python
        painter.setPen(QColor("#404040"))
```
to:
```python
        painter.setPen(QColor("#8b949e"))
```

---

## TASK 6 — Modify `src/proc_map_designer/ui/terrain/terrain_viewport.py`

**File:** `src/proc_map_designer/ui/terrain/terrain_viewport.py`

**Line 83:** Change:
```python
        glClearColor(0.15, 0.16, 0.18, 1.0)
```
to:
```python
        glClearColor(0.051, 0.067, 0.090, 1.0)
```

This sets the OpenGL clear color to match `#0d1117` (R=13/255=0.051, G=17/255=0.067, B=23/255=0.090).

---

## TASK 7 — Modify `src/proc_map_designer/ui/terrain/terrain_toolbar.py`

**File:** `src/proc_map_designer/ui/terrain/terrain_toolbar.py`

Add labels for the sliders (currently unlabeled). Also add section labels for tool groups.

**Replace the entire `__init__` method body** (lines 17–57) with:

```python
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(130)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 8, 6, 8)

        # Tool buttons
        tools_label = QLabel("Tool")
        tools_label.setProperty("role", "secondary")
        layout.addWidget(tools_label)

        self._group = QButtonGroup(self)
        tool_names = [
            ("raise",   "▲ Raise"),
            ("lower",   "▼ Lower"),
            ("smooth",  "~ Smooth"),
            ("flatten", "— Flatten"),
            ("noise",   "# Noise"),
            ("ramp",    "/ Ramp"),
        ]
        for index, (tool, label) in enumerate(tool_names):
            button = QPushButton(label)
            button.setCheckable(True)
            if index == 0:
                button.setChecked(True)
            button.clicked.connect(lambda checked=False, t=tool: self.tool_changed.emit(t))
            self._group.addButton(button)
            layout.addWidget(button)

        layout.addSpacing(8)

        # Radius slider
        radius_label = QLabel("Radius")
        radius_label.setProperty("role", "secondary")
        layout.addWidget(radius_label)

        self.radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.radius_slider.setRange(1, 50)
        self.radius_slider.setValue(10)
        self.radius_slider.valueChanged.connect(lambda v: self.radius_changed.emit(v / 100.0))
        layout.addWidget(self.radius_slider)

        layout.addSpacing(4)

        # Strength slider
        strength_label = QLabel("Strength")
        strength_label.setProperty("role", "secondary")
        layout.addWidget(strength_label)

        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setRange(1, 100)
        self.strength_slider.setValue(25)
        self.strength_slider.valueChanged.connect(lambda v: self.strength_changed.emit(v / 100.0))
        layout.addWidget(self.strength_slider)

        layout.addSpacing(8)

        # Falloff combo
        falloff_label = QLabel("Falloff")
        falloff_label.setProperty("role", "secondary")
        layout.addWidget(falloff_label)

        self.falloff_combo = QComboBox()
        for value in ["smooth", "linear", "sharp", "flat"]:
            self.falloff_combo.addItem(value.title(), value)
        self.falloff_combo.currentIndexChanged.connect(
            lambda _: self.falloff_changed.emit(str(self.falloff_combo.currentData()))
        )
        layout.addWidget(self.falloff_combo)

        layout.addSpacing(8)

        # History buttons
        undo_button = QPushButton("↩ Undo")
        undo_button.clicked.connect(self.undo_requested.emit)
        layout.addWidget(undo_button)

        redo_button = QPushButton("↪ Redo")
        redo_button.clicked.connect(self.redo_requested.emit)
        layout.addWidget(redo_button)

        reset_button = QPushButton("⊘ Reset")
        reset_button.setProperty("role", "danger")
        reset_button.clicked.connect(self.reset_requested.emit)
        layout.addWidget(reset_button)

        layout.addStretch(1)
```

Add `QLabel` to the imports at line 4. Change:
```python
from PySide6.QtWidgets import QButtonGroup, QComboBox, QSlider, QVBoxLayout, QWidget, QPushButton
```
to:
```python
from PySide6.QtWidgets import QButtonGroup, QComboBox, QLabel, QSlider, QVBoxLayout, QWidget, QPushButton
```

---

## TASK 8 — Modify `src/proc_map_designer/ui/terrain/terrain_settings_panel.py`

No code changes needed. The QSS applied globally will style all `QGroupBox`, `QFormLayout`, `QPushButton`, `QSpinBox`, etc. automatically.

One optional improvement: mark the save button as primary. After `self.save_button = QPushButton("Save Height PNG")` (line 75), add:
```python
        self.save_button.setProperty("role", "primary")
```

---

## TASK 9 — Post-Implementation Verification (MANDATORY, run after ALL other tasks)

This task must be executed by the agent as the final step. Its purpose is to detect regressions, broken references, and import errors introduced by the GUI changes. The agent must perform every check below, fix any failure found, and report a final status summary.

### 9a. Static Import Check

Run the following command from the project root. It must exit with code 0 and print no error:

```bash
cd /home/ruben/Desktop/scene_generator && \
  .venv/bin/python -c "
from proc_map_designer.ui.main_window import MainWindow
from proc_map_designer.ui.map_preview_widget import MapPreviewWidget
from proc_map_designer.ui.terrain.terrain_toolbar import TerrainToolbar
from proc_map_designer.ui.terrain.terrain_settings_panel import TerrainSettingsPanel
print('ALL IMPORTS OK')
"
```

**Expected output:** `ALL IMPORTS OK`  
**On failure:** Read the traceback. The most common causes are:
- `QFrame` not added to the QtWidgets import block in `main_window.py`
- `QSvgRenderer` import missing (`from PySide6.QtSvg import QSvgRenderer`)
- `import html as _html` missing
- `QLabel` not added to `terrain_toolbar.py` imports
- Syntax error in any modified file

Fix the import error before proceeding.

### 9b. Widget Attribute Existence Check

Run this command. All 10 attributes must be printed without `AttributeError`:

```bash
cd /home/ruben/Desktop/scene_generator && \
  .venv/bin/python -c "
import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from proc_map_designer.infrastructure.settings import AppSettings
from proc_map_designer.infrastructure.project_repository import ProjectRepository
from proc_map_designer.services.project_service import ProjectService
from proc_map_designer.services.inspection_service import BlendInspectionService
from proc_map_designer.services.generation_pipeline_service import GenerationPipelineService
from proc_map_designer.infrastructure.blender_runner import BlenderRunner
from proc_map_designer.services.export_package_service import ExportPackageService
from proc_map_designer.services.final_export_service import FinalExportService
from proc_map_designer.services.generation_service import GenerationService
from proc_map_designer.services.validation_service import ValidationService
from proc_map_designer.ui.main_window import MainWindow
from pathlib import Path

settings = AppSettings()
runner = BlenderRunner(settings=settings)
scripts_dir = Path('scripts')
window = MainWindow(
    inspection_service=BlendInspectionService(runner=runner, script_path=scripts_dir/'inspect_blend_collections.py'),
    project_service=ProjectService(ProjectRepository()),
    pipeline_service=GenerationPipelineService(
        export_service=ExportPackageService(),
        validation_service=ValidationService(runner=runner, script_path=scripts_dir/'blender_validate_project.py'),
        generation_service=GenerationService(runner=runner, python_batch_script=scripts_dir/'blender_generate_python_batch.py', geometry_nodes_script=scripts_dir/'blender_generate_geometry_nodes.py'),
        final_export_service=FinalExportService(runner=runner, script_path=scripts_dir/'blender_export_final_map.py'),
        runner=runner,
    ),
    settings=settings,
)

# Verify all critical widget attributes still exist
attrs = [
    'project_label', 'blend_file_label', 'blender_path_label',
    'map_summary_label', 'pipeline_state_label', 'latest_output_label',
    'active_layer_label', 'roads_hint_label',
    'layer_tree', 'canvas_view',
    'setup_map_width_spin', 'setup_map_height_spin',
    'setup_mask_width_spin', 'setup_mask_height_spin',
    'terrain_material_combo', 'output_path_edit', 'browse_output_button',
    'setup_next_button', 'paint_back_button', 'paint_next_button',
    'generate_back_button', 'generate_button',
    'paint_mode_button', 'erase_mode_button',
    'brush_size_slider', 'brush_intensity_slider',
    'road_width_slider', 'road_profile_combo',
    'clear_layer_button', 'remove_last_road_button',
    'paint_tab_widget', 'backend_combo',
    'painted_layers_list', 'painted_layers_summary', 'painted_layers_table',
    'parameter_layer_label', 'param_enabled_check', 'param_density_spin',
    'param_allow_overlap_check', 'param_min_distance_spin',
    'param_scale_min_spin', 'param_scale_max_spin',
    'param_rotation_spin', 'param_seed_spin', 'param_priority_spin',
    'log_panel', 'workflow_stack', 'content_splitter',
    'action_new_project', 'action_open_project', 'action_save_project',
    'action_save_project_as', 'action_configure_map',
    'action_validate_pipeline', 'action_generate',
    'action_open_result', 'action_final_export',
    'select_blend_button', 'configure_blender_button',
]
missing = [a for a in attrs if not hasattr(window, a)]
if missing:
    print('MISSING ATTRIBUTES:', missing)
    sys.exit(1)
else:
    print('ALL ATTRIBUTES OK:', len(attrs), 'checked')
"
```

**Expected output:** `ALL ATTRIBUTES OK: 54 checked`  
**On failure:** The listed attribute names are missing. The most common causes:
- `self.roads_hint_label` was fully deleted instead of replaced with `self.roads_hint_label = QLabel(); self.roads_hint_label.setVisible(False)`
- `self.active_layer_label` was fully deleted instead of being kept hidden
- `self.step_title_label` was kept with `setText()` in `_set_workflow_step()` — if so, remove only the `setText` call, and either keep the hidden label OR ensure it is not referenced anywhere else

### 9c. Signal Chain Verification — Read Key Methods

Read the following methods in `main_window.py` and verify the listed conditions. Use the `Read` tool with the exact line ranges.

**Check 1 — `_wire_canvas()` (around line 718):**  
Verify it still references: `self.canvas_view`, `self.road_width_slider`, `self.road_profile_combo`.  
None of these widgets were removed. If any `AttributeError` would occur at runtime, fix the corresponding widget creation.

**Check 2 — `_on_brush_size_changed()` and `_on_brush_intensity_changed()`:**  
Search for these methods with `grep -n "_on_brush_size_changed\|_on_brush_intensity_changed" src/proc_map_designer/ui/main_window.py`.  
Verify they still reference `self.brush_size_label` and `self.brush_intensity_label` respectively.  
These labels were NOT removed — they are the inline value labels for sliders. If the grep shows they reference `self.active_layer_label` or any other removed label, fix.

**Check 3 — `_set_loading_state()` (around line 1388):**  
Verify it still references `self.select_blend_button` and `self.configure_blender_button`.  
Both buttons were recreated inside GroupBoxes in TASK 4l — the `self.X` attribute names are preserved, so this is safe. If not, the GroupBox rewrite in TASK 4l forgot to assign to `self.select_blend_button`.

**Check 4 — `_set_pipeline_running()` (around line 1377):**  
Verify it still references `self.backend_combo`, `self.output_path_edit`, `self.browse_output_button`.  
All three were preserved in TASK 4l. Confirm by reading the method.

**Check 5 — `_apply_project_to_ui()` (around line 1795):**  
Verify it calls `self._refresh_project_label()`, `self._refresh_blend_label()`, `self._refresh_blender_path_label()`, `self._refresh_map_summary_label()`, `self._refresh_pipeline_state_label()`, `self._refresh_latest_output_label()`.  
All six refresh methods must still exist and their bodies must reference the correct `self.X` label attributes.

### 9d. Structural File Checks

Run each grep and verify the expected result:

**Check: QSS file exists and is non-empty**
```bash
wc -l src/proc_map_designer/ui/style/theme.qss
```
Expected: at least 200 lines. If 0 or missing, TASK 2 was not completed.

**Check: White logo files exist**
```bash
test -f logo/icon_logo_white.svg && echo "icon OK" || echo "icon MISSING"
test -f logo/name_logo_white.svg && echo "name OK" || echo "name MISSING"
```

**Check: Stylesheet is loaded in app.py**
```bash
grep -n "theme.qss\|setStyleSheet" src/proc_map_designer/app.py
```
Expected: at least 2 lines matching (the path and the setStyleSheet call).

**Check: log_panel has objectName set**
```bash
grep -n 'log_panel.*setObjectName\|setObjectName.*log_panel' src/proc_map_designer/ui/main_window.py
```
Expected: 1 match. If 0, the `setObjectName("log_panel")` line from TASK 4j was not added.

**Check: appendHtml is used (not appendPlainText) in _append_log**
```bash
grep -n "appendPlainText\|appendHtml" src/proc_map_designer/ui/main_window.py
```
Expected: `appendHtml` appears in `_append_log`. `appendPlainText` should NOT appear in `_append_log` (it may still appear elsewhere in the file if used by other code — that is fine).

**Check: No dangling step_title_label.setText calls**
```bash
grep -n "step_title_label" src/proc_map_designer/ui/main_window.py
```
Expected: **0 matches** (the label was never created and the setText call was removed in TASK 4e). If any matches found, the old `step_title_label.setText(...)` line was not removed from `_set_workflow_step()`.

**Check: _build_header_bar method exists**
```bash
grep -n "_build_header_bar\|_build_step_indicator" src/proc_map_designer/ui/main_window.py
```
Expected: at least 4 matches (2 definitions, 2 call sites in `_build_ui()`).

**Check: GroupBox imports available**
```bash
grep -n "QGroupBox" src/proc_map_designer/ui/main_window.py
```
Expected: at least 3 matches (1 import, 2+ usages for "Scene Source", "Map Settings", "Output" groups).  
If 0 import matches, add `QGroupBox` to the QtWidgets import block.

**Check: QFrame imported**
```bash
grep -n "QFrame" src/proc_map_designer/ui/main_window.py
```
Expected: at least 2 matches (1 import, 2+ usages as separators in `_build_header_bar()`).

**Check: Primary role on key buttons**
```bash
grep -n 'setProperty.*primary\|setProperty.*flat\|setProperty.*danger' src/proc_map_designer/ui/main_window.py
```
Expected: at least 6 matches covering `setup_next_button`, `paint_next_button`, `paint_back_button`, `generate_button`, `generate_back_button`, `select_blend_button`.

**Check: terrain_toolbar imports QLabel**
```bash
grep -n "QLabel" src/proc_map_designer/ui/terrain/terrain_toolbar.py
```
Expected: at least 1 import match and 4+ usage matches (Tool, Radius, Strength, Falloff section labels).

**Check: glClearColor updated in terrain_viewport**
```bash
grep -n "glClearColor" src/proc_map_designer/ui/terrain/terrain_viewport.py
```
Expected: `glClearColor(0.051, 0.067, 0.090, 1.0)`. If still `0.15, 0.16, 0.18`, TASK 6 was not applied.

**Check: map_preview_widget uses dark colors**
```bash
grep -n "f4f4f4\|d0d0d0\|255aa8\|404040" src/proc_map_designer/ui/map_preview_widget.py
```
Expected: **0 matches**. Any match means TASK 5 was partially applied.

### 9e. Functional Regression Analysis — Read Critical Code Paths

For each flow below, read the relevant lines in `main_window.py` and confirm the code path is intact:

**Flow 1 — Blend file selection:**
- Method `_on_select_blend()`: must call `QFileDialog`, set `self._current_blend`, trigger `_start_inspection()`
- Method `_start_inspection()`: must create `InspectionWorker`, connect `worker.log` to `self._append_log`, connect `worker.finished` to `_on_inspection_success`
- Method `_on_inspection_success()`: must call `self._refresh_blend_label()` and `self._refresh_layer_tree()`
- **Verify:** `self._refresh_blend_label()` now sets text on `self.blend_file_label` which is a QLabel inside the header bar (created in `_build_header_bar()`). The label must exist.

**Flow 2 — Map settings change:**
- Spinboxes `setup_map_width_spin`, `setup_map_height_spin`, `setup_mask_width_spin`, `setup_mask_height_spin` must still connect `editingFinished` to `_on_setup_map_changed()`
- `_on_setup_map_changed()` must call `self._refresh_map_summary_label()`
- `_refresh_map_summary_label()` must call `self.map_summary_label.setText(...)` — `map_summary_label` is in the header bar

**Flow 3 — Step navigation:**
- `setup_next_button.clicked` → `_go_to_paint_step()` → validates blend + blender + collection_tree → calls `_set_workflow_step(1)`
- `_set_workflow_step(1)` → `self.workflow_stack.setCurrentIndex(1)` + updates `self._step_buttons` styles
- `paint_back_button.clicked` → `lambda: self._set_workflow_step(0)`
- **Verify:** `self.workflow_stack` still exists and `setCurrentIndex` is called. The step buttons in `self._step_buttons` are polished after property changes.

**Flow 4 — Pipeline execution:**
- `generate_button.clicked` → `_generate_pipeline()` (same as `action_generate.triggered`)
- `_generate_pipeline()` → `self._set_pipeline_running(True, "exporting")` → updates `self.pipeline_state_label` pill style
- Worker emits `log` → `_append_log()` → `self.log_panel.appendHtml(...)`
- Worker emits `finished` → `_on_pipeline_success()` → `self._refresh_pipeline_state_label()` → pill changes to "pill-success"

**Flow 5 — Project save/load:**
- `action_save_project.triggered` → `_save_project()` → calls `_apply_project_to_ui()`
- `_apply_project_to_ui()` calls `_refresh_project_label()`, `_refresh_blend_label()`, `_refresh_blender_path_label()`, etc.
- All these methods reference `self.project_label`, `self.blend_file_label`, `self.blender_path_label` — all must exist (in header bar or hidden)

### 9f. Fix Any Issues Found

After running the checks in 9a–9e, fix every failure found before marking the task complete. For each fix:
1. Identify which task introduced the regression (e.g., "TASK 4l forgot to assign `self.configure_blender_button`")
2. Apply the minimal targeted fix (do not redo the entire task unless necessary)
3. Re-run the specific check that failed to confirm the fix

### 9g. Final Report

After all checks pass, output a report with this exact format:

```
=== GUI IMPLEMENTATION VERIFICATION REPORT ===

IMPORT CHECK:           PASS
ATTRIBUTE CHECK:        PASS  (54 attributes verified)
SIGNAL CHAINS:          PASS  (5 flows verified)
FILE STRUCTURE:         PASS
QSS FILE:               PASS  (N lines)
WHITE LOGOS:            PASS  (icon_logo_white.svg, name_logo_white.svg)
DARK COLORS:            PASS  (map_preview, terrain viewport)
LOG HTML:               PASS  (appendHtml in _append_log)
BUTTON ROLES:           PASS  (N setProperty calls found)
NO DANGLING REFS:       PASS  (step_title_label: 0 occurrences)

REGRESSIONS FOUND:      0
REGRESSIONS FIXED:      0

STATUS: READY FOR MANUAL UI TESTING
```

If any item is FAIL, list the specific issue and what was fixed. Do not output READY FOR MANUAL UI TESTING until all items are PASS.

---

## Implementation Order for OpenCode Agents

Execute tasks in this exact sequence — each is independent of the next EXCEPT where noted:

```
1.  TASK 1a  → Create logo/icon_logo_white.svg
2.  TASK 1b  → Create logo/name_logo_white.svg
3.  TASK 2   → Create src/proc_map_designer/ui/style/theme.qss
               Create src/proc_map_designer/ui/style/__init__.py (empty)
4.  TASK 3   → Modify src/proc_map_designer/app.py
5.  TASK 5   → Modify map_preview_widget.py   (independent)
6.  TASK 6   → Modify terrain_viewport.py     (independent)
7.  TASK 7   → Modify terrain_toolbar.py      (independent)
8.  TASK 8   → Modify terrain_settings_panel.py (independent)
9.  TASK 4a  → Add imports to main_window.py
10. TASK 4b  → Replace 7 labels in _build_ui()
11. TASK 4c  → Add _build_header_bar() method
12. TASK 4d  → Add _build_step_indicator() method
13. TASK 4e  → Update _set_workflow_step()
14. TASK 4f  → Update _refresh_project_label()
15. TASK 4g  → Update _refresh_blend_label()
16. TASK 4h  → Update _refresh_map_summary_label()
17. TASK 4i  → Update _refresh_pipeline_state_label()
18. TASK 4j  → Update _append_log()  +  add setObjectName to log_panel
19. TASK 4k  → Add "role" properties to buttons
20. TASK 4l  → Wrap setup step in GroupBoxes (REPLACES current _build_setup_step content)
21. TASK 4m  → Paint step cleanup (remove intro/hint labels)
22. TASK 4n  → Generate step cleanup (remove intro, style label)
23. TASK 9   → Post-implementation verification (MANDATORY LAST STEP)
```

---

## Verification Checklist

After all tasks complete, verify:

- [ ] App starts without Python errors (`./main.py`)
- [ ] Window background is `#0d1117` (dark navy), not white or grey
- [ ] Toolbar background is `#161b27` (darker navy stripe)
- [ ] Header bar shows project name, map info, pipeline pill
- [ ] Step indicator shows 3 steps; clicking Step 2/3 triggers validation
- [ ] Active step is highlighted in teal (`#00b4d8`)
- [ ] All buttons have rounded corners and dark background
- [ ] Primary buttons (Next, Select .blend, Generate, Save Height PNG) are teal
- [ ] Flat/back buttons are transparent with muted text
- [ ] Setup step shows 3 GroupBox cards (Scene Source, Map Settings, Output)
- [ ] Log panel has dark background with green monospace text
- [ ] Pipeline status pill changes color on generate/validate
- [ ] Blend inspection still triggers and populates layer tree
- [ ] Canvas painting still works (masks painted on canvas)
- [ ] Terrain viewport renders with dark background
- [ ] Terrain tool buttons show labels (▲ Raise, ▼ Lower, etc.)
- [ ] Map settings dialog opens and preview is dark-themed
- [ ] Project save/load works without errors
- [ ] Generate pipeline completes and log output is readable
- [ ] TASK 9 verification report shows all items PASS

---

## Notes for Agents

1. **Do NOT modify any method signatures, signal names, or slot connections.** Only change widget creation code, text, and visual properties.

2. **The `self.X` widget names must be preserved exactly.** `self.project_label`, `self.blend_file_label`, `self.blender_path_label`, `self.pipeline_state_label`, `self.latest_output_label`, `self.map_summary_label`, `self.step_title_label` — all of these must continue to exist as attributes (some hidden, some in the header bar). Their `setText()` calls in refresh methods still work.

3. **`self.step_title_label` is no longer created.** Its only usage is in `_set_workflow_step()` at line 750 (`self.step_title_label.setText(...)`). That line is removed in TASK 4e. No other usage of `step_title_label` exists in the codebase.

4. **For `QPushButton[role="primary"]` QSS to apply**, the `setProperty("role", "primary")` call must be made BEFORE the widget is shown. All the `setProperty` calls in TASK 4k happen during `__init__` widget construction, so this is safe.

5. **QSvgRenderer requires `PySide6.QtSvg`** which is part of PySide6's standard distribution. No additional pip install needed.

6. **The `_html` import** (as `import html as _html`) avoids name collision with any local variable named `html`.

7. **If `logo/icon_logo_white.svg` does not exist**, `_build_header_bar()` skips the logo safely (the `if logo_path.exists():` guard).

8. **`appendHtml()` on QPlainTextEdit** is a valid method — it appends HTML-formatted text as a new paragraph block, same as `appendPlainText`. The `setMaximumBlockCount(700)` limit still applies.
