from __future__ import annotations

from typing import Any, Mapping


def require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"'{field_name}' debe ser un objeto JSON.")
    return value


def require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"'{field_name}' debe ser una lista.")
    return value


def require_string(value: Any, field_name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"'{field_name}' debe ser un texto.")
    text = value.strip()
    if not allow_empty and not text:
        raise ValueError(f"'{field_name}' no puede estar vacío.")
    return text


def require_int(
    value: Any,
    field_name: str,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    if not isinstance(value, int):
        raise ValueError(f"'{field_name}' debe ser un entero.")
    if min_value is not None and value < min_value:
        raise ValueError(f"'{field_name}' debe ser >= {min_value}.")
    if max_value is not None and value > max_value:
        raise ValueError(f"'{field_name}' debe ser <= {max_value}.")
    return value


def require_float(
    value: Any,
    field_name: str,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"'{field_name}' debe ser numérico.")
    numeric = float(value)
    if min_value is not None and numeric < min_value:
        raise ValueError(f"'{field_name}' debe ser >= {min_value}.")
    if max_value is not None and numeric > max_value:
        raise ValueError(f"'{field_name}' debe ser <= {max_value}.")
    return numeric


def require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"'{field_name}' debe ser booleano.")
    return value

