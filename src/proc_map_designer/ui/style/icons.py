from __future__ import annotations

from typing import Final

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_ICON_PATHS: Final[dict[str, str]] = {
    "new": "M12 5v14M5 12h14",
    "open": "M4 8h5l2 2h9v8H4z M4 8V6h5l2 2",
    "save": "M6 4h10l2 2v14H6z M9 4v6h6 M9 18h6",
    "settings": "M12 8.5A3.5 3.5 0 1 0 12 15.5A3.5 3.5 0 1 0 12 8.5 M12 2v3 M12 19v3 M4.93 4.93l2.12 2.12 M16.95 16.95l2.12 2.12 M2 12h3 M19 12h3 M4.93 19.07l2.12-2.12 M16.95 7.05l2.12-2.12",
    "validate": "M5 12l4 4L19 6",
    "generate": "M8 6l10 6-10 6z",
    "open_result": "M5 7h14v10H5z M9 11h6 M12 8v6",
    "export": "M12 4v12 M7 11l5 5 5-5 M5 20h14",
    "clear": "M6 7h12 M9 7V5h6v2 M8 7l1 12h6l1-12",
}


def load_svg_icon(name: str, size: int = 20, color: str = "#ffffff") -> QIcon:
    path_data = _ICON_PATHS[name]
    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none'>
      <path d='{path_data}' stroke='{color}' stroke-width='1.9' stroke-linecap='round' stroke-linejoin='round'/>
    </svg>
    """
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
