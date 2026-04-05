from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence


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
        return self.run_script_with_blend(
            blend_file=blend_file,
            script_path=script_path,
            script_args=[],
        )

    def run_script_with_blend(
        self,
        blend_file: Path,
        script_path: Path,
        script_args: Sequence[str],
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        if not blend_file.exists():
            raise BlenderExecutionError(f"El archivo .blend no existe: {blend_file}")
        if not script_path.exists():
            raise BlenderExecutionError(f"No se encontró el script auxiliar: {script_path}")

        blender_executable = self._require_blender_executable()

        command = [
            blender_executable,
            "-b",
            str(blend_file),
            "--python",
            str(script_path),
            "--",
            *[str(arg) for arg in script_args],
        ]

        return self._run_command(command, log_callback=log_callback)

    def run_script_headless(
        self,
        script_path: Path,
        script_args: Sequence[str],
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        if not script_path.exists():
            raise BlenderExecutionError(f"No se encontró el script auxiliar: {script_path}")

        blender_executable = self._require_blender_executable()

        command = [
            blender_executable,
            "-b",
            "--python",
            str(script_path),
            "--",
            *[str(arg) for arg in script_args],
        ]

        return self._run_command(command, log_callback=log_callback)

    def open_blend_interactive(self, blend_file: Path) -> None:
        if not blend_file.exists():
            raise BlenderExecutionError(f"El archivo .blend no existe: {blend_file}")

        blender_executable = self._require_blender_executable()

        try:
            subprocess.Popen(
                [blender_executable, str(blend_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise BlenderExecutionError(
                f"No se pudo ejecutar Blender con la ruta '{blender_executable}'."
            ) from exc

    def _require_blender_executable(self) -> str:
        blender_executable = self._settings.get_blender_executable()
        if not blender_executable:
            raise BlenderExecutionError(
                "No hay ruta a Blender configurada. Define BLENDER_EXECUTABLE o configúrala en la GUI."
            )
        return blender_executable

    def _run_command(
        self,
        command: Sequence[str],
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise BlenderExecutionError(
                f"No se pudo ejecutar Blender con el comando '{command[0]}'."
            ) from exc

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        payload: dict[str, Any] | None = None

        def read_stream(
            stream,
            sink: list[str],
        ) -> None:
            for line in stream:
                sink.append(line)
                if log_callback is not None:
                    message = line.rstrip()
                    if message and self.JSON_START not in message and self.JSON_END not in message:
                        log_callback(message)

        try:
            assert process.stdout is not None
            assert process.stderr is not None

            stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, stdout_lines), daemon=True)
            stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, stderr_lines), daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            return_code = process.wait(timeout=self._timeout_seconds)
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            raise BlenderExecutionError(
                f"Blender tardó más de {self._timeout_seconds} segundos en responder."
            ) from exc

        stdout_text = "".join(stdout_lines)
        stderr_text = "".join(stderr_lines)

        if stdout_text:
            try:
                payload = self.extract_payload_from_stdout(stdout_text)
            except BlenderExecutionError:
                if return_code == 0:
                    raise

        if return_code != 0:
            payload_error = ""
            if payload:
                payload_error = str(payload.get("error", "")).strip()
            stderr_message = stderr_text.strip()
            detail = payload_error or stderr_message or "sin detalles adicionales."
            raise BlenderExecutionError(
                f"Blender finalizó con código {return_code}: {detail}"
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
