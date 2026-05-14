# Performance Optimisation Plan — Scene Generator

> **Goal:** Restructure the pipeline so that lightweight user-facing operations (design, configuration, .blend validation) run fast and never block UX, while all heavy Blender computations are deferred to a clearly separated "generation" phase that can run unattended in the background.

---

## 1. Current State Summary

### 1.1 Architecture Overview

```
main.py → app.py → MainWindow (PySide6)
                        ↓
            ┌───────────┴───────────┐
            │  Worker Threads (QThread) │
            └───────────┬───────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
   InspectionWorker  PipelineWorker  (future workers)
   (inspect .blend)   (export→validate→generate)
          ↓             ↓
   BlenderRunner   BlenderRunner
   (subprocess)    (subprocess)
```

### 1.2 What Currently Runs on Each Thread

| Operation | Thread | Blocks UI? | Typical Duration |
|-----------|--------|-----------|-----------------|
| Brush stroke painting | **Main** | **YES** | < 100 ms |
| Canvas overlay composite | **Main** | Brief | < 50 ms |
| Road simplification/smooth | **Main** | Brief | < 5 ms |
| Terrain GL sculpt (NumPy) | GL / Main | NO | < 1 ms/stroke |
| Terrain undo snapshot (zlib) | **Main** | Brief | < 5 ms |
| **Mask PNG load on project open** | **Main** | **YES** | 50–200 ms/layer |
| **Mask rescale on settings change** | **Main** | **YES** | 10–50 ms/layer |
| .blend inspection (Blender) | Worker | NO | 2–10 s |
| Mask PNG export (pipeline step) | Worker | NO | 100–500 ms total |
| project.json write | Worker | NO | < 10 ms |
| Blender validation script | Worker | NO | 2–10 s |
| Blender generation (batch/GN) | Worker | NO | 10–40 s |
| Blender final export | Worker | NO | 2–10 s |

### 1.3 The Core UX Problem: Monolithic Pipeline

Every click of **"Generate"** (or **"Validate"**) runs the same monolithic sequence on a single worker:

```
Click "Generate"
    └── PipelineWorker.run()
            ├── STEP 1 — Export masks (PNG I/O, ~100–500 ms)
            ├── STEP 2 — Write project.json (~10 ms)
            ├── STEP 3 — Spawn Blender: blender_validate_project.py (2–10 s)
            └── STEP 4 — Spawn Blender: blender_generate_*.py (10–40 s)
```

**Problems with this design:**
1. **Re-validation every time.** If the user clicks Generate twice with no changes, Steps 1–3 run redundantly.
2. **Masks are re-exported every generate.** If only a generation parameter changed (not the masks), all PNGs are written again.
3. **No separation between "commit design" and "run Blender".** The user cannot say "I'm done designing, save my work" without immediately triggering a long Blender run.
4. **Validation is hidden inside Generate.** If validation fails inside a Generate run, the user waited 2–10 s before learning about the error.
5. **Minor UI-blocking operations** exist (mask load, mask rescale) but are not addressed.

---

## 2. Proposed Phase Architecture

Split the user journey into **three distinct phases** with clearly different computational costs:

```
PHASE A — DESIGN   (instant, all local, no Blender)
PHASE B — COMMIT   (fast, local I/O + optional Blender pre-check)
PHASE C — GENERATE (slow, background Blender, user can walk away)
```

### Phase A: Design (no change to core logic)
The user paints masks, draws roads, sculpts terrain, configures layers.
All operations are already fast or non-blocking. Minor optimisations apply
(async mask load, async rescale — see Section 4.1).

### Phase B: Commit Design
A new **"Save & Validate"** action replaces the current "Validate" button.

**What it does (all on a worker thread, no Blender):**
1. Export all layer masks as grayscale PNGs to the package directory.
2. Write `project.json` manifest.
3. Run **local pre-validation** (pure Python, zero Blender):
   - Required fields filled in?
   - `.blend` file accessible on disk?
   - Each enabled layer has a mask file?
   - Each enabled layer has a `layer_id` (collection path)?
   - Output path is writable?
4. Emit result immediately (< 500 ms total).
5. **Optionally** run the existing Blender validation subprocess if the user wants full collection-existence checks (the current "Validate" behaviour). This is a second pass, still on worker thread, but clearly optional and labelled "Deep Validate".

**What it does NOT do:** spawn Blender for generation.

**Invalidation rule:** the commit result is marked **stale** whenever the user changes:
- Any mask (brush stroke on any layer).
- Road geometry.
- Terrain heightfield.
- Any layer configuration (density, seed, collection ID, etc.).
- Map settings (resolution, dimensions).
- Source `.blend` path or output path.

### Phase C: Generate Map
The **"Generate"** button triggers only the Blender generation subprocess.

**Pre-conditions checked instantly on the main thread:**
- Is there a valid, non-stale commit in the current session? → If not, prompt user to commit first.
- Is the pipeline already busy? → Show busy indicator.

**What it does (on worker thread, fully background):**
1. If commit is stale → run Phase B automatically before proceeding (with user feedback).
2. If Blender validation was not run in Phase B → run it now (same as current behaviour).
3. Run Blender generation script.
4. Emit result.

The user can **switch tabs, paint masks on a new area, or read logs** while generation runs, because it is already on a separate thread. The goal is to make this feel like a background job, not a blocking step.

---

## 3. Detailed Implementation Plan

### Task 1 — Local Pre-Validation Layer (no Blender)

**New file:** `src/proc_map_designer/services/local_validation_service.py`

**Purpose:** validate all locally checkable conditions without spawning Blender.

```python
@dataclass
class LocalValidationResult:
    success: bool
    errors: list[str]
    warnings: list[str]

class LocalValidationService:
    def validate(self, project_state: ProjectState, mask_snapshots: ...) -> LocalValidationResult:
        errors = []
        warnings = []

        # 1. Required fields
        if not project_state.project_id:
            errors.append("Project ID is not set.")
        if not project_state.source_blend:
            errors.append("No source .blend file selected.")
        elif not Path(project_state.source_blend).is_file():
            errors.append(f"Source .blend not found: {project_state.source_blend}")
        if not project_state.output_blend:
            errors.append("No output path set.")
        else:
            output_dir = Path(project_state.output_blend).parent
            if not output_dir.exists():
                errors.append(f"Output directory does not exist: {output_dir}")

        # 2. Blender executable
        blender_exe = Path(project_state.blender_executable)
        if not blender_exe.is_file():
            errors.append(f"Blender executable not found: {blender_exe}")

        # 3. Layers
        enabled_layers = [l for l in project_state.layers if l.enabled]
        if not enabled_layers:
            warnings.append("No enabled layers. Generation will produce an empty scene.")
        for layer in enabled_layers:
            if not layer.layer_id:
                errors.append(f"Layer '{layer.display_name}' has no collection ID set.")
            if layer.generation_mode == "procedural":
                # Check mask exists in snapshots
                if layer.layer_id not in mask_snapshots or mask_snapshots[layer.layer_id] is None:
                    warnings.append(f"Layer '{layer.display_name}' has no painted mask.")

        # 4. Map settings
        ms = project_state.map_settings
        if ms.width_m <= 0 or ms.height_m <= 0:
            errors.append("Map dimensions must be positive.")
        if ms.mask_width < 64 or ms.mask_height < 64:
            warnings.append("Mask resolution is very low (< 64 px). Object placement may be inaccurate.")

        return LocalValidationResult(success=len(errors) == 0, errors=errors, warnings=warnings)
```

**Integration points:**
- Called from the worker at the start of Phase B **before** any PNG I/O.
- Errors surface immediately (< 10 ms) in the UI via the existing log/signal mechanism.
- If local validation fails, the worker stops and does NOT export masks or call Blender.

**Files to modify:** none structurally; add the new service and wire it in `app.py`.

---

### Task 2 — Commit State Tracking (Staleness Detection)

**New field in `ProjectState`:**

```python
# src/proc_map_designer/domain/project_state.py

@dataclass
class CommitState:
    committed_at: str | None = None   # ISO timestamp of last successful commit
    manifest_path: str | None = None  # path to project.json written in last commit
    blender_validated: bool = False    # True if Blender validation ran and passed
    stale: bool = True                 # True when design changed since last commit
```

`ProjectState` gains a `commit_state: CommitState` field.

**Staleness triggers** — call `project_state.commit_state.stale = True` whenever:
- A brush stroke ends on any layer mask.
- A road is added, deleted, or modified.
- The terrain heightfield is modified.
- Any `LayerState` field changes (density, seed, collection ID, enabled, etc.).
- `MapSettings` changes (resolution, dimensions, grid size).
- `source_blend` or `output_blend` changes.

These are already mutation points in `MainWindow` (where signals are handled). No new code path is needed — just set the staleness flag in the existing handlers.

**Files to modify:**
- `src/proc_map_designer/domain/project_state.py` — add `CommitState` dataclass and field.
- `src/proc_map_designer/ui/main_window.py` — set `stale = True` in existing mutation handlers.
- `src/proc_map_designer/infrastructure/project_repository.py` — persist/load `commit_state`.

---

### Task 3 — Separate "Commit Design" Worker

**New worker class:** `CommitWorker` (analogous to existing `PipelineWorker`).

**New pipeline service method:**
`GenerationPipelineService.commit_design(project, package_dir, mask_exporter, local_validator, log, state)`

```
CommitWorker.run():
    1. state("local_validating")
       result = LocalValidationService.validate(project, mask_snapshots)
       if not result.success:
           emit failed(errors)
           return

    2. state("exporting_masks")
       ExportPackageService.export_package(project, package_dir, mask_exporter)
       # PNG I/O for all layers — same as current export step
       # Total: 100–500 ms on worker thread

    3. [Optional — only if user chose "Deep Validate" or if blender_validated is False]
       state("blender_validating")
       ValidationService.validate_package(manifest_path)
       # Blender subprocess: 2–10 s

    4. state("committed")
       project.commit_state.committed_at = now()
       project.commit_state.stale = False
       project.commit_state.blender_validated = deep_validate_ran
       emit finished(CommitResult)
```

**UI integration in `MainWindow`:**
- Add/rename the existing "Validate" button to **"Save & Validate"**.
- Wire it to `_commit_design()` which creates and starts `CommitWorker`.
- Show the same progress spinner / status pills as the current pipeline.
- On success: update `commit_state`, show green "Committed" pill, enable "Generate" button.
- On failure: show red error(s) in log panel. "Generate" button stays disabled.

**Files to modify:**
- `src/proc_map_designer/services/generation_pipeline_service.py` — add `commit_design()` method.
- `src/proc_map_designer/ui/main_window.py` — add `_commit_design()`, `CommitWorker`, update button wiring.

---

### Task 4 — Guard "Generate" with Commit State

**In `MainWindow._generate_pipeline()`** (currently `_validate_pipeline` and `_generate_pipeline`):

```python
def _generate_pipeline(self) -> None:
    commit = self._project_state.commit_state

    if commit.stale or commit.manifest_path is None:
        # Auto-commit, then generate
        self._commit_then_generate()
        return

    if not commit.blender_validated:
        # Blender validation not yet run — run it now before generating
        self._start_pipeline_operation("validate_then_generate")
        return

    # Commit is fresh and Blender-validated — skip straight to generation
    self._start_pipeline_operation("generate_only")
```

**New pipeline operation `"generate_only"`** in `GenerationPipelineService`:

```python
def generate_only(self, manifest_path: str, backend_id: str, project, log, state) -> LatestOutputInfo:
    """Skip export and validation; go straight to Blender generation."""
    state("generating")
    result = self._generation_service.generate(backend_id, manifest_path)
    state("completed")
    return LatestOutputInfo(status="completed", ...)
```

This means a second "Generate" click with unchanged design skips:
- PNG export (~100–500 ms)
- Blender validation (~2–10 s)

And goes **directly to Blender generation** (~10–40 s).

**Files to modify:**
- `src/proc_map_designer/services/generation_pipeline_service.py` — add `generate_only()`.
- `src/proc_map_designer/ui/main_window.py` — update `_generate_pipeline()` logic.

---

### Task 5 — Async Mask Load on Project Open

**Current behaviour (blocks main thread):**

```python
# layer_mask_manager.py — called synchronously in MainWindow._open_project()
def load_from_project_layers(self, layers, project_dir):
    for layer in layers:
        mask = QImage(str(mask_path))  # disk I/O on main thread
        layer.mask_image = mask
```

**Proposed behaviour:**

1. Create a `MaskLoadWorker(QThread)` that loads all mask PNGs from disk.
2. Show a "Loading project…" spinner in the canvas area while loading.
3. Emit `masks_loaded(dict[layer_id, QImage])` signal when done.
4. Main thread receives the signal and sets masks into `LayerMaskManager`.

**Implementation sketch:**

```python
# New class: MaskLoadWorker (in layer_mask_manager.py or a new workers.py)
class MaskLoadWorker(QObject):
    masks_loaded = Signal(dict)   # dict[layer_id, QImage]
    failed = Signal(str)

    def __init__(self, layers, project_dir):
        super().__init__()
        self._layers = layers
        self._project_dir = project_dir

    def run(self):
        result = {}
        for layer in self._layers:
            path = self._project_dir / "masks" / f"..._{layer.layer_id}.png"
            if path.exists():
                result[layer.layer_id] = QImage(str(path))
        self.masks_loaded.emit(result)
```

**Files to modify:**
- `src/proc_map_designer/ui/canvas/layer_mask_manager.py` — extract I/O into worker, add `load_async()` method.
- `src/proc_map_designer/ui/main_window.py` — use async load on `_open_project()`.

---

### Task 6 — Async Mask Rescale on Map Settings Change

**Current behaviour (blocks main thread):**

```python
# layer_mask_manager.py
def set_map_settings(self, map_settings):
    for layer in self._layers.values():
        layer.mask_image = mask.scaled(new_width, new_height, ...)  # Qt rescale, main thread
```

**Proposed behaviour:**

1. `set_map_settings()` immediately stores the new `MapSettings`.
2. Kicks off a `MaskRescaleWorker(QThread)` with the current masks and new resolution.
3. Canvas shows a "Rescaling…" overlay during the operation.
4. Worker emits `rescale_done(dict[layer_id, QImage])` when finished.
5. Main thread receives and applies the new images.

**Files to modify:**
- `src/proc_map_designer/ui/canvas/layer_mask_manager.py` — add `rescale_async()`.
- `src/proc_map_designer/ui/main_window.py` — call `rescale_async()` instead of synchronous `set_map_settings()`.
- `src/proc_map_designer/ui/canvas/canvas_view.py` — show "Rescaling…" overlay.

---

### Task 7 — Decouple Final Export from Generation

The **"Final Export"** step (runs `blender_export_final_map.py`) is already a separate button, which is good. No change needed to its logic.

**One improvement:** after a successful Generate, auto-prompt the user: "Generation complete. Run Final Export now?" instead of silently waiting. This avoids the user not knowing the generation finished.

**Files to modify:**
- `src/proc_map_designer/ui/main_window.py` — add a non-blocking notification on generation success that offers the "Final Export" action.

---

### Task 8 — Generation Progress Estimation

Blender generation emits log lines to stdout but currently there is no progress percentage — the spinner just spins indefinitely.

**Improvement:** parse known Blender log patterns to estimate progress.

```python
# In PipelineWorker or BlenderRunner:
PROGRESS_PATTERNS = [
    (r"Loading project manifest", 5),
    (r"Loading mask for layer", 15),   # per-layer, accumulate
    (r"Planning placements", 40),
    (r"Placing instances", 60),        # per-layer, accumulate
    (r"Applying roads", 80),
    (r"Saving output file", 90),
    (r"Generation complete", 100),
]
```

When a log line matches a pattern, emit a `progress(int)` signal to update a progress bar.

**Files to modify:**
- `src/proc_map_designer/infrastructure/blender_runner.py` — add progress parsing in the stdout reader thread.
- `src/proc_map_designer/ui/main_window.py` — connect progress signal to a `QProgressBar` in the header/status bar.

---

### Task 9 — Remove Double Validation in Generate

**Current behaviour:** `generate_project()` always runs both export AND validation before generating.

**After Task 4**, the `generate_only` path eliminates this. But also remove the redundant re-validation inside `generate_project` when the user explicitly clicked "Validate" moments ago:

In `GenerationPipelineService.generate_project()`:

```python
# After export:
if skip_validation:  # project.commit_state.blender_validated and not stale
    log("Skipping Blender validation (already validated, no changes since).")
else:
    validation_report = self._validate_manifest(manifest_path)
    if not validation_report.success:
        raise ValidationError(...)
```

Pass `skip_validation=True` when the commit is fresh.

**Files to modify:**
- `src/proc_map_designer/services/generation_pipeline_service.py` — add `skip_validation` parameter to `generate_project()`.
- `src/proc_map_designer/ui/main_window.py` — pass flag based on `commit_state`.

---

## 4. New Button / UX Flow

### Revised Stepper / Action Buttons

| Step | Action | What happens | Duration |
|------|--------|-------------|---------|
| 1. Setup | Select .blend | Async inspection (Blender) | 2–10 s (background) |
| 2. Design | Paint / roads / terrain | All local, no Blender | Instant |
| 3. Commit | **Save & Validate** | Local pre-check + mask export + (opt.) Blender validation | 0.5–12 s (background) |
| 4. Generate | **Generate Map** | Blender generation only (if committed & validated) | 10–40 s (background) |
| 5. Export | **Final Export** | Blender consolidation | 2–10 s (background) |

**Key UX invariant:**  
Steps 3 and 4 are separate; the user can commit (confirm their design) and then kick off generation and walk away. If they paint more after committing, the commit is automatically marked stale and the next Generate will auto-recommit before generating.

---

## 5. What Must NOT Change

To preserve all existing functionality, the following must remain untouched in behaviour:

| What | Why |
|------|-----|
| Blender subprocess arguments | Scripts parse specific `--project`, `--output`, `--backend` flags |
| `blender_validate_project.py` logic | Full validation still runs on first commit or when requested |
| `blender_generate_python_batch.py` | No changes to Blender-side generation algorithms |
| `blender_generate_geometry_nodes.py` | No changes to Blender-side GN pipeline |
| `placement_planner.py` determinism | Seeded algorithm must not change (reproducibility guarantee) |
| `project.json` schema | Scripts depend on exact JSON structure |
| `LatestOutputInfo` dataclass | Serialised to disk; backwards-compatible changes only |
| Test suite | All existing tests must remain green |
| Road / terrain serialisation | No change to persistence format |

---

## 6. File Change Summary

| File | Change Type | Task |
|------|-------------|------|
| `src/proc_map_designer/services/local_validation_service.py` | **NEW** | Task 1 |
| `src/proc_map_designer/domain/project_state.py` | Add `CommitState` dataclass + field | Task 2 |
| `src/proc_map_designer/ui/main_window.py` | Staleness flags, new buttons, `CommitWorker`, async loaders | Tasks 2, 3, 4, 5, 6, 7, 8 |
| `src/proc_map_designer/services/generation_pipeline_service.py` | Add `commit_design()`, `generate_only()`, `skip_validation` param | Tasks 3, 4, 9 |
| `src/proc_map_designer/ui/canvas/layer_mask_manager.py` | Async load & rescale | Tasks 5, 6 |
| `src/proc_map_designer/ui/canvas/canvas_view.py` | "Rescaling…" overlay | Task 6 |
| `src/proc_map_designer/infrastructure/blender_runner.py` | Progress pattern parsing | Task 8 |
| `src/proc_map_designer/infrastructure/project_repository.py` | Persist `commit_state` | Task 2 |
| `app.py` | Wire `LocalValidationService` into DI | Task 1 |

**Scripts (in `scripts/`) — NO CHANGES.** All Blender-side code is unchanged.

---

## 7. Implementation Order (Recommended)

Tasks are ordered by risk and dependency. Start with the lowest-risk, highest-impact changes.

```
Task 1 — LocalValidationService          (new file, zero risk, immediate UX win)
Task 2 — CommitState tracking            (domain-only change, no UI impact yet)
Task 9 — Remove double validation        (single flag in pipeline service)
Task 3 — CommitWorker + Commit Design    (new worker, separates UX phases)
Task 4 — Guard Generate with CommitState (wires Tasks 2+3 to the Generate button)
Task 5 — Async mask load                 (fixes main-thread block on project open)
Task 6 — Async mask rescale              (fixes main-thread block on settings change)
Task 7 — Final Export auto-prompt        (small UX notification change)
Task 8 — Progress estimation             (purely additive, no logic change)
```

---

## 8. Testing Checklist

For each task, verify:

- [ ] **Task 1:** Local validation catches missing .blend, missing collection ID, and invalid output path before any PNG is written.
- [ ] **Task 2:** Modifying a mask marks `commit_state.stale = True`. Loading a project restores `commit_state` from JSON.
- [ ] **Task 3:** "Save & Validate" completes in < 2 s without Blender when all local checks pass. With "Deep Validate" enabled, Blender validation runs as before.
- [ ] **Task 4:** A second "Generate" with no design changes skips export and validation and reaches the Blender generation step directly.
- [ ] **Task 5:** Opening a project with 4 layers does not freeze the canvas. Masks appear progressively.
- [ ] **Task 6:** Changing map resolution shows a brief "Rescaling…" indicator and the canvas does not freeze.
- [ ] **Task 7:** After generation completes, a non-blocking notification appears offering "Final Export".
- [ ] **Task 8:** The progress bar advances during generation instead of spinning indefinitely.
- [ ] **Task 9:** When `skip_validation=True`, no Blender validation subprocess is spawned.
- [ ] **All:** Existing unit tests pass unchanged. A full Generate run on a sample project produces the same `working_map.blend` as before.
- [ ] **All:** The `project.json` written by the new commit flow is byte-for-byte identical to the one written by the current export step (same schema, same paths).

---

## 9. Risk Assessment

| Task | Risk | Mitigation |
|------|------|-----------|
| Task 1 | Low — new service, additive | Cover with unit tests |
| Task 2 | Low — new dataclass field, default `stale=True` so nothing skips by accident | Ensure JSON serialisation round-trips correctly |
| Task 3 | Medium — new worker class, refactor of main_window | Mirror existing InspectionWorker / PipelineWorker pattern exactly |
| Task 4 | Medium — changes Generate flow logic | Ensure fallback path auto-recommits when stale |
| Task 5 | Medium — async load, Qt signal from worker | Use same pattern as InspectionWorker; protect with mutex if masks are accessed during load |
| Task 6 | Medium — async rescale, canvas overlay | Disable brush while rescaling; re-enable on signal |
| Task 7 | Low — UI notification only | Use non-modal QMessageBar or status pill, not a blocking QDialog |
| Task 8 | Low — additive log parsing | Patterns are optional; if none match, progress stays at 0 (existing spinner) |
| Task 9 | Low — single boolean flag | Default `skip_validation=False` so existing behaviour is unchanged unless flag is explicitly set |
