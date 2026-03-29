# Procedural Map Designer (Milestone 1 + 2 + 3 + 4)

App desktop externa en Python + PySide6 para preparar mapas procedurales para Blender.

## Funcionalidades actuales

- Inspección de `.blend` mediante Blender en `subprocess` (sin parsing binario manual).
- Gestión de proyectos JSON versionados (`schema_version`).
- Configuración de mapa lógico y resolución raster interna.
- Canvas 2D pintable por capas (subcollections):
  - selección de layer activa `category/subcollection`
  - paleta jerárquica por familia: `vegetation/*` comparte tono base con variaciones suaves
  - pincel circular
  - tamaño e intensidad ajustables
  - modo pintar / borrar
  - visibilidad por capa
  - limpiar capa activa
  - overlay coloreado por capa
  - zoom con rueda y pan con botón central del mouse
- Persistencia de máscaras por capa como PNG en carpeta `masks/`.

## Arquitectura relevante (Milestone 4)

```text
src/proc_map_designer/
├─ domain/
│  ├─ models.py
│  ├─ project_state.py
│  ├─ coordinates.py
│  └─ validators.py
├─ infrastructure/
│  ├─ blender_runner.py
│  ├─ project_repository.py
│  └─ settings.py
├─ services/
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
```

## Requisitos

- Linux
- Python 3.11+
- Blender instalado

## Instalación

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución

```bash
python main.py
```

## Flujo recomendado

1. `Proyecto > Nuevo proyecto`
2. `Configurar Blender`
3. `Seleccionar .blend`
4. Seleccionar layer activa en el árbol (ej: `vegetation/pino`)
5. Pintar en canvas con botón izquierdo
6. Cambiar a otra layer y pintar distinto
7. `Proyecto > Guardar` / `Guardar como...`
8. Cerrar y reabrir proyecto para verificar rehidratación completa

## Formato de almacenamiento de máscaras

Cada capa se guarda como PNG en:

```text
<project_dir>/masks/<index>_<layer_id_sanitized>.png
```

En el JSON del proyecto, cada `LayerState` incluye:
- `layer_id` (ej: `vegetation/pino`)
- `name`
- `visible`
- `opacity`
- `color_hex`
- `mask_data_path` (ruta relativa al proyecto)

## Esquema de proyecto JSON (campos clave)

- `schema_version`
- `project_id`
- `project_name`
- `source_blend`
- `blender_executable`
- `created_at`
- `updated_at`
- `collection_tree`
- `map_settings`
- `layers`
- `generation_settings`

Ejemplo:
- `examples/sample_project.json`

## Pruebas manuales sugeridas (Milestone 4)

1. Pintura por capas:
- Cargar `.blend` con subcollections.
- Seleccionar `vegetation/pino`, pintar.
- Seleccionar `vegetation/arbusto`, pintar en otra zona.
- Verificar que cada capa conserva su máscara independiente.

2. Borrado:
- Con capa activa, cambiar a modo `Borrar`.
- Pasar pincel sobre zona pintada y confirmar reducción/eliminación.

3. Visibilidad:
- Desmarcar capa en árbol y comprobar que su overlay desaparece.
- Marcarla de nuevo y confirmar restauración.

4. Zoom y pan:
- Usar rueda para zoom in/out.
- Arrastrar con botón central para pan.
- Pintar tras mover/zoom y comprobar que responde correctamente.

5. Persistencia:
- Guardar proyecto.
- Cerrar app.
- Abrir proyecto JSON.
- Confirmar restauración de overlays, capas, visibilidad y mapa.

## Tests automáticos

```bash
python -m unittest discover -s tests -v
```

Incluye:
- serialización/deserialización de `ProjectState`
- validación de esquema
- transformaciones de coordenadas
- parsing del runner de Blender
- ciclo básico de máscaras (`LayerMaskManager`)
