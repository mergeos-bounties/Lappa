"""Ground-truth occupancy world tests for the tricycle SLAM demo."""

from __future__ import annotations

import sys
from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parents[2] / "demos" / "tricycle_3w"
sys.path.insert(0, str(DEMO_ROOT))

from tricycle_3w.slam_bridge import _display_map_cells
from tricycle_3w.teleop import (
    WAREHOUSE_WAYPOINTS,
    OccupancyWorld,
)


def test_clearpath_warehouse_world_loads_with_ros_metadata():
    world = OccupancyWorld.from_yaml(DEMO_ROOT / "worlds" / "warehouse.yaml")

    assert (world.width, world.height) == (1006, 1674)
    assert world.resolution == 0.03
    assert (world.origin_x, world.origin_y) == (-15.1, -25.0)
    assert world.is_clear(0.0, 0.0, 0.27)
    assert not world.is_clear(-8.0, -5.0, 0.27)
    assert 0.1 <= world.ray_distance(0.0, 0.0, 0.0, 8.0) <= 8.0


def test_warehouse_exploration_route_is_clear_and_plannable():
    world = OccupancyWorld.from_yaml(DEMO_ROOT / "worlds" / "warehouse.yaml")
    current = (0.0, 0.0)

    for waypoint in WAREHOUSE_WAYPOINTS:
        assert world.is_clear(*waypoint, 0.27), waypoint
        path = world.plan_path(current, waypoint, 0.27)
        assert path, waypoint
        assert path[-1] == waypoint
        current = waypoint


def test_warehouse_assets_preserve_upstream_attribution():
    source = (DEMO_ROOT / "worlds" / "SOURCES.md").read_text(encoding="utf-8")

    assert "clearpathrobotics/clearpath_nav2_demos" in source
    assert (DEMO_ROOT / "worlds" / "LICENSE-BSD-3-CLAUSE.txt").is_file()


def test_slam_bridge_keeps_walls_and_samples_free_cells():
    values = [0] * 10_000
    values[123] = 100
    values[9_999] = -1

    cells, occupied, free, stride = _display_map_cells(
        values,
        width=100,
        target_cells=100,
    )

    assert occupied == 1
    assert free == 9_998
    assert stride > 1
    assert [23, 1, 100] in cells
    assert len(cells) <= 110
