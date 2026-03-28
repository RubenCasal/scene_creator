from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Protocol


class BlenderPathProvider(Protocol):
    def get_blender_executable(self) -> str | None:
        ...


class BlenderExecutionError(RuntimeError):
    """Raised when Blender execution fails or returns invalid data."""


class BlenderRunner:
    JSON_START = "__BLEND_JSON_START__"
    JSON_END = "__BLEND_JSON_END__"

    def __init__(self, settings: BlenderPathProvider, timeout_seconds: int = 45) -> None:
        self._settings = settings
        self._timeout_seconds = timeout_seconds

    def run_script_for_blend(self, blend_file: Path, script_path: Path) -> dict[str, Any]:
        if not blend_file.exists():
            raise BlenderExecutionError(f"El archivo .blend no existe: {blend_file}")
        if not script_path.exists():
            raise BlenderExecutionError(f"No se encontró el script auxiliar: {script_path}")

        blender_executable = self._settings.get_blender_executable()
        if not blender_executable:
            raise BlenderExecutionError(
                "No hay ruta a Blender configurada. Define BLENDER_EXECUTABLE o configúrala en la GUI."
            )

        command = [
            blender_executable,
            "-b",
            str(blend_file),
            "--python",
            str(script_path),
            "--",
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise BlenderExecutionError(
                f"No se pudo ejecutar Blender con la ruta '{blender_executable}'."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise BlenderExecutionError(
                f"Blender tardó más de {self._timeout_seconds} segundos en responder."
            ) from exc

        payload: dict[str, Any] | None = None
        if completed.stdout:
            try:
                payload = self.extract_payload_from_stdout(completed.stdout)
            except BlenderExecutionError:
                if completed.returncode == 0:
                    raise

        if completed.returncode != 0:
            payload_error = ""
            if payload:
                payload_error = str(payload.get("error", "")).strip()
            stderr_message = completed.stderr.strip()
            detail = payload_error or stderr_message or "sin detalles adicionales."
            raise BlenderExecutionError(
                f"Blender finalizó con código {completed.returncode}: {detail}"
            )

        if payload is None:
            raise BlenderExecutionError(
                "Blender no devolvió JSON válido. Revisa que el script auxiliar se haya ejecutado correctamente."
            )

        if payload.get("error"):
            raise BlenderExecutionError(str(payload["error"]))

        return payload

    @classmethod
    def extract_payload_from_stdout(cls, stdout: str) -> dict[str, Any]:
        start = stdout.find(cls.JSON_START)
        end = stdout.find(cls.JSON_END)
        if start == -1 or end == -1 or end <= start:
            raise BlenderExecutionError("No se encontraron marcadores JSON en la salida de Blender.")

        json_block = stdout[start + len(cls.JSON_START) : end].strip()
        if not json_block:
            raise BlenderExecutionError("El bloque JSON devuelto por Blender está vacío.")

        try:
            payload = json.loads(json_block)
        except json.JSONDecodeError as exc:
            raise BlenderExecutionError(f"JSON inválido recibido desde Blender: {exc}") from exc

        if not isinstance(payload, dict):
            raise BlenderExecutionError("La respuesta JSON de Blender no es un objeto.")

        return payload

