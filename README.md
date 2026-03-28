# Procedural Map Designer - Milestone 1

Aplicación desktop externa (Python + PySide6) para inspeccionar archivos `.blend` desde fuera de Blender y visualizar la jerarquía de collections.

## Qué incluye este milestone

- Selector de archivo `.blend` en GUI.
- Configuración de la ruta al ejecutable de Blender:
  - desde botón `Configurar Blender`, o
  - variable de entorno `BLENDER_EXECUTABLE`.
- Ejecución de Blender en `subprocess` con script auxiliar Python (`scripts/inspect_blend_collections.py`).
- Comunicación por JSON en stdout con delimitadores seguros.
- Árbol de collections en panel lateral (subcollections y cantidad de objetos).
- Placeholder de canvas 2D en panel central.
- Barra de estado + panel de logs + manejo de errores.
- Modelo tipado con `dataclasses`:
  - `CollectionNode`
  - `BlendInspectionResult`
- Estructura por capas:
  - `ui/`
  - `services/`
  - `domain/`
  - `infrastructure/`

## Estructura del proyecto

```text
scene_generator/
├─ main.py
├─ requirements.txt
├─ README.md
├─ scripts/
│  └─ inspect_blend_collections.py
├─ src/
│  └─ proc_map_designer/
│     ├─ app.py
│     ├─ domain/
│     │  └─ models.py
│     ├─ infrastructure/
│     │  ├─ blender_runner.py
│     │  └─ settings.py
│     ├─ services/
│     │  └─ inspection_service.py
│     └─ ui/
│        └─ main_window.py
└─ tests/
   ├─ test_blender_runner.py
   └─ test_models.py
```

## Requisitos

- Linux
- Python 3.11+
- Blender instalado (probado con ejecución por CLI)

## Instalación

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configurar Blender

Opción A (recomendada para primera ejecución):

1. Abrir la app.
2. Pulsar `Configurar Blender`.
3. Seleccionar el ejecutable de Blender (`blender`).

Opción B (variable de entorno):

```bash
export BLENDER_EXECUTABLE=/ruta/a/blender
```

## Ejecutar la app

```bash
python main.py
```

## Flujo de uso

1. Pulsar `Seleccionar .blend`.
2. Elegir archivo válido.
3. La app lanza Blender en background y recibe JSON con collections.
4. Se actualiza el árbol en el panel izquierdo usando la jerarquía enlazada a la escena activa.
5. Si existen roots `vegetation` o `building`, se resaltan visualmente.

Si Blender no está disponible o falla, la GUI muestra un error claro y no crashea.

## Tests básicos

```bash
python -m unittest discover -s tests -v
```
