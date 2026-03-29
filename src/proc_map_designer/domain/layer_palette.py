from __future__ import annotations

import hashlib
import re


HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def split_layer_id(layer_id: str) -> tuple[str, str]:
    cleaned = layer_id.strip()
    if not cleaned:
        return "default", "default"

    parts = [part.strip() for part in cleaned.split("/") if part.strip()]
    if not parts:
        return "default", "default"
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], parts[-1]


def base_hue_for_category(category: str) -> int:
    normalized = (category or "default").strip().lower() or "default"
    digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 360


def sibling_hue_offset(sibling_index: int) -> int:
    index = max(0, int(sibling_index))
    if index == 0:
        return 0
    step = (index + 1) // 2
    sign = -1 if index % 2 == 1 else 1
    return sign * 7 * step


def variant_color_for_sibling(category: str, sibling_index: int) -> str:
    base_hue = base_hue_for_category(category)
    hue = (base_hue + sibling_hue_offset(sibling_index)) % 360
    saturation = 170
    value = 255
    return _hsv_to_hex(hue, saturation, value)


def is_valid_hex_color(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    return HEX_COLOR_RE.match(value.strip()) is not None


def _hsv_to_hex(hue: int, saturation: int, value: int) -> str:
    h = max(0, min(359, int(hue)))
    s = max(0, min(255, int(saturation)))
    v = max(0, min(255, int(value)))

    c = (v * s) // 255
    h_mod = h % 360
    x = (c * (60 - abs((h_mod % 120) - 60))) // 60
    m = v - c

    if h_mod < 60:
        rp, gp, bp = c, x, 0
    elif h_mod < 120:
        rp, gp, bp = x, c, 0
    elif h_mod < 180:
        rp, gp, bp = 0, c, x
    elif h_mod < 240:
        rp, gp, bp = 0, x, c
    elif h_mod < 300:
        rp, gp, bp = x, 0, c
    else:
        rp, gp, bp = c, 0, x

    r = rp + m
    g = gp + m
    b = bp + m
    return f"#{r:02x}{g:02x}{b:02x}"

