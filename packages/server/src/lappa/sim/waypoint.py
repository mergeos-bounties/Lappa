"""Waypoint marker loader with JSON Schema validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SCHEMA_PATH = Path(__file__).parent / "waypoint_schema.json"
_SCHEMA: dict[str, Any] | None = None


def _load_schema() -> dict[str, Any]:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA


def validate_waypoint(data: dict[str, Any]) -> list[str]:
    """Validate a waypoint dict against the schema. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    schema = _load_schema()
    required = schema.get("required", [])
    props = schema.get("properties", {})

    for field in required:
        if field not in data:
            errors.append(f"missing required field: {field}")

    for key, value in data.items():
        if key not in props:
            errors.append(f"unknown field: {key}")
            continue
        prop = props[key]
        ptype = prop.get("type", "")
        if ptype == "string" and not isinstance(value, str):
            errors.append(f"{key}: expected string, got {type(value).__name__}")
        elif ptype == "number" and not isinstance(value, (int, float)):
            errors.append(f"{key}: expected number, got {type(value).__name__}")
        elif ptype == "array":
            if not isinstance(value, list):
                errors.append(f"{key}: expected array, got {type(value).__name__}")
            elif prop.get("items", {}).get("type") == "string":
                for i, item in enumerate(value):
                    if not isinstance(item, str):
                        errors.append(f"{key}[{i}]: expected string, got {type(item).__name__}")
        if "minimum" in prop and isinstance(value, (int, float)) and value < prop["minimum"]:
            errors.append(f"{key}: {value} < minimum {prop['minimum']}")

    return errors


def load_waypoints(path: Path) -> list[dict[str, Any]]:
    """Load and validate all waypoint markers from a JSON file.
    Returns list of validated waypoints. Raises ValueError on parse/validation errors.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        items = raw.get("waypoints", raw.get("markers", [raw]))
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError(f"unexpected JSON structure: {type(raw).__name__}")

    waypoints: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        errs = validate_waypoint(item)
        if errs:
            raise ValueError(f"waypoint {idx}: {'; '.join(errs)}")
        waypoints.append(item)
    return waypoints
