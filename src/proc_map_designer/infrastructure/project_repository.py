from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class ProjectRepositoryError(RuntimeError):
    """Raised when project JSON cannot be read or written."""


class ProjectRepository:
    def load_json(self, file_path: Path) -> Mapping[str, Any]:
        if not file_path.exists():
            raise ProjectRepositoryError(f"No existe el archivo de proyecto: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProjectRepositoryError(f"No se pudo leer el proyecto: {exc}") from exc

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProjectRepositoryError(f"JSON inválido: {exc}") from exc

        if not isinstance(payload, dict):
            raise ProjectRepositoryError("El archivo de proyecto debe contener un objeto JSON.")

        return payload

    def save_json(self, file_path: Path, payload: Mapping[str, Any]) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            file_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise ProjectRepositoryError(f"No se pudo guardar el proyecto: {exc}") from exc

