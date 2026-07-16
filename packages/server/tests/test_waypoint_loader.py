"""Tests for waypoint marker loader and schema."""

from __future__ import annotations

import json
from pathlib import Path

from lappa.sim.waypoint import validate_waypoint, load_waypoints


def test_validate_valid_minimal() -> None:
    errs = validate_waypoint({"name": "dock_a", "x": 1.0, "y": 2.0, "tags": ["dock"]})
    assert errs == []


def test_validate_valid_full() -> None:
    errs = validate_waypoint({
        "name": "patrol_1", "x": 5.0, "y": 3.0,
        "theta": 1.57, "tags": ["patrol", "aisle"], "radius_m": 0.5
    })
    assert errs == []


def test_validate_missing_required() -> None:
    errs = validate_waypoint({"x": 1.0, "y": 2.0})
    assert any("name" in e for e in errs)
    assert any("tags" in e for e in errs)


def test_validate_wrong_type() -> None:
    errs = validate_waypoint({"name": "test", "x": "abc", "y": 2.0, "tags": []})
    assert any("x" in e for e in errs)


def test_validate_below_minimum() -> None:
    errs = validate_waypoint({"name": "test", "x": 1.0, "y": 2.0, "tags": [], "radius_m": -1})
    assert any("radius_m" in e for e in errs)


def test_load_valid_file(tmp_path: Path) -> None:
    f = tmp_path / "markers.json"
    data = {"waypoints": [
        {"name": "a", "x": 0, "y": 0, "tags": ["start"]},
        {"name": "b", "x": 1, "y": 1, "tags": ["end"]},
    ]}
    f.write_text(json.dumps(data))
    wpts = load_waypoints(f)
    assert len(wpts) == 2


def test_load_list(tmp_path: Path) -> None:
    f = tmp_path / "list.json"
    data = [{"name": "a", "x": 0, "y": 0, "tags": ["x"]}]
    f.write_text(json.dumps(data))
    assert len(load_waypoints(f)) == 1


def test_load_invalid_raises(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text(json.dumps([{"name": "bad", "x": "not", "y": 0}]))
    import pytest
    with pytest.raises(ValueError, match="x"):
        load_waypoints(f)
