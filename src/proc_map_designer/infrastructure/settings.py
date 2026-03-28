from __future__ import annotations

import os
from typing import Literal

from PySide6.QtCore import QSettings


class AppSettings:
    _BLENDER_EXECUTABLE_KEY = "blender/executable_path"

    def __init__(self) -> None:
        self._settings = QSettings()

    def get_blender_executable(self) -> str | None:
        path, _ = self.get_blender_path_and_source()
        return path

    def get_blender_path_and_source(self) -> tuple[str | None, Literal["settings", "env", "none"]]:
        stored_path = str(self._settings.value(self._BLENDER_EXECUTABLE_KEY, "", type=str)).strip()
        if stored_path:
            return stored_path, "settings"

        env_path = os.getenv("BLENDER_EXECUTABLE", "").strip()
        if env_path:
            return env_path, "env"

        return None, "none"

    def set_blender_executable(self, path: str) -> None:
        self._settings.setValue(self._BLENDER_EXECUTABLE_KEY, path.strip())

