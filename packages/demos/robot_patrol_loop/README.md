# Robot Patrol Loop Demo

Sample patrol loop with trajectory notes and expected metrics.

## Overview

Demonstrates a basic warehouse aisle patrol pattern using simulated robot trajectories.

## Expected Metrics

| Metric | Value |
|--------|-------|
| Patrol duration | ~30s per loop |
| Waypoints | 4 corners + 2 mid-aisle |
| Max speed | 0.5 m/s |
| Obstacle detection | Enabled |

## Usage

```bash
# Run simulation with patrol loop
ros2 launch lappa_sim patrol_loop.launch.py

# Record trajectory data
ros2 bag record /trajectory /odom
```

## Trajectory Notes

- Starts at origin, moves clockwise
- Each waypoint held for 2 seconds
- Smooth transitions via spline interpolation
- Obstacle avoidance triggers emergency stop at <0.3m

## Evidence

See `test_patrol_loop.py` for smoke test coverage.
