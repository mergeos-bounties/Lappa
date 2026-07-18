# Obstacle Layer Fixture Format

## Overview

Defines the JSON schema for obstacle layers in Lappa simulations.

## Schema

```json
{
  "obstacle_layer": {
    "grid_size": [width, height, depth],
    "cell_size_m": 0.1,
    "obstacles": [
      {
        "id": "unique_id",
        "type": "static|dynamic",
        "position": [x, y, z],
        "dimensions": [w, h, d],
        "category": "barrier|cone|vehicle|person|other"
      }
    ],
    "metadata": {
      "timestamp": "ISO-8601",
      "scenario": "warehouse|outdoor|industrial",
      "generated_by": "fixture_generator"
    }
  }
}
```

## Acceptance Criteria

- Grid dimensions in meters (float)
- Cell size default 0.1m (configurable)
- At least 3 obstacles per fixture
- Category must be one of: barrier, cone, vehicle, person, other
- Type must be: static or dynamic

## Load Test

Run with `pytest tests/test_obstacle_layer.py` to validate schema compliance.
