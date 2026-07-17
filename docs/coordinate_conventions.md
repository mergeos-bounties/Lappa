# Sim Coordinate Frame Conventions (Wave 2)

## Overview

This document describes the coordinate system conventions used in Lappa simulation fixtures and path planning examples.

## Units

- **Position**: meters (m)
- **Angle**: radians (rad)
- **Velocity**: meters per second (m/s)
- **Angular velocity**: radians per second (rad/s)

## Coordinate System

- **Origin** (`0, 0`): World frame reference point
- **X-axis**: Forward direction (robot heading)
- **Y-axis**: Left direction (90° counter-clockwise from X)
- **Z-axis**: Upward direction (right-hand rule)

## Path Fixture Conventions

All path fixtures follow these rules:

1. Positions are in meters from world origin
2. Angles are in radians, measured counter-clockwise from X-axis
3. Velocities are instantaneous (per timestep)
4. Negative Y values indicate rightward movement

## Example

```
# Patrol loop fixture
waypoint_1: {x: 2.0, y: 0.0, theta: 0.0}    # 2m forward
waypoint_2: {x: 2.0, y: 2.0, theta: 1.57}   # 2m left (π/2 rad)
waypoint_3: {x: 0.0, y: 2.0, theta: 3.14}   # 2m backward (π rad)
waypoint_4: {x: 0.0, y: 0.0, theta: 4.71}   # back to origin (3π/2 rad)
```

## References

- ROS 2 REP 103: Uniform Standard for Physical Robot Metadata
- REP 105: Standard for Units Symbolism
- Lappa main README: [link to main documentation]
