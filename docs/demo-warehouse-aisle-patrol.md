# Demo: Warehouse Aisle Patrol

A loop trajectory that simulates a robot patrolling a warehouse aisle.

## Path

| Metric | Value |
|--------|-------|
| Aisle width | 1.5 m |
| Aisle length | 8.0 m |
| Path length | 19.0 m |
| Net displacement | 0.0 m (returns to start) |
| Waypoints | 5 |

## Waypoints

```
(0.0, 0.0)   → start at aisle bottom
(0.0, 8.0)   → drive up the aisle (forward 8m)
(1.5, 8.0)   → strafe across (1.5m)
(1.5, 0.0)   → drive back down (reverse 8m)
(0.0, 0.0)   → strafe back to start (1.5m), completing the loop
```

## Expected behavior

- The robot starts at one end of the aisle, drives to the far end, shifts laterally, returns, and shifts back.
- Total traverse: 19 m.
- The net displacement is zero: the robot returns exactly to its starting pose.
- This trajectory exercises forward, lateral, and turning motion in a constrained environment.

## Fixture

The path fixture is at `tests/fixtures/sample_path_warehouse_aisle_patrol.json`.
