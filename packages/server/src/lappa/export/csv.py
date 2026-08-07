"""Rich CSV export for Lappa trajectories."""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable, Mapping
from io import StringIO
from pathlib import Path
from typing import Any

CSV_FIELDS = (
    "timestamp",
    "x",
    "y",
    "z",
    "velocity",
    "acceleration",
    "jerk",
    "rotation_x",
    "rotation_y",
    "rotation_z",
)


def _number(point: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = point.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
    return default


def trajectory_csv_text(trajectory: Iterable[Mapping[str, Any]]) -> str:
    """Return a deterministic CSV with derived motion columns when needed."""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    previous_time: float | None = None
    previous_velocity = 0.0
    previous_acceleration = 0.0
    for point in trajectory:
        timestamp = _number(point, "timestamp", "t")
        linear_x = _number(point, "linear_x")
        linear_y = _number(point, "linear_y")
        velocity = _number(
            point,
            "velocity",
            default=math.hypot(linear_x, linear_y),
        )
        dt = timestamp - previous_time if previous_time is not None else 0.0
        derived_acceleration = (velocity - previous_velocity) / dt if dt > 1e-9 else 0.0
        acceleration = _number(
            point,
            "acceleration",
            default=derived_acceleration,
        )
        derived_jerk = (acceleration - previous_acceleration) / dt if dt > 1e-9 else 0.0
        writer.writerow(
            {
                "timestamp": timestamp,
                "x": _number(point, "x"),
                "y": _number(point, "y"),
                "z": _number(point, "z"),
                "velocity": velocity,
                "acceleration": acceleration,
                "jerk": _number(point, "jerk", default=derived_jerk),
                "rotation_x": _number(point, "rotation_x", "rx"),
                "rotation_y": _number(point, "rotation_y", "ry"),
                "rotation_z": _number(point, "rotation_z", "rz", "theta"),
            }
        )
        previous_time = timestamp
        previous_velocity = velocity
        previous_acceleration = acceleration
    return output.getvalue()


def export_trajectory_csv(trajectory: Iterable[Mapping[str, Any]], output_path: str | Path) -> Path:
    """Write a rich trajectory CSV and return the resolved output path."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(trajectory_csv_text(trajectory), encoding="utf-8")
    return output


def generate_sample_trajectory() -> list[dict[str, float]]:
    """Return deterministic sample points for examples and smoke tests."""
    return [
        {"timestamp": 0, "x": 0, "y": 0, "z": 0, "velocity": 0},
        {"timestamp": 1, "x": 1, "y": 0, "z": 0, "velocity": 1},
        {"timestamp": 2, "x": 3, "y": 0, "z": 0, "velocity": 2},
        {"timestamp": 3, "x": 6, "y": 0, "z": 0, "velocity": 3},
    ]
