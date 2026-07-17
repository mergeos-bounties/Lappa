# Sim Coordinate Frame Conventions

This document describes the coordinate frame conventions used in Lappa simulations.

## Overview

Lappa uses a right-handed coordinate system consistent with ROS2 and common robotics conventions.

## Frame Hierarchy

```
world (fixed frame)
  └── map
        └── odom
              └── base_link
                    ├── base_footprint
                    ├── laser_link
                    └── camera_link
```

## Axis Definitions

| Axis | Direction | Unit | Description |
|------|-----------|------|-------------|
| X | Forward | meters | Forward direction of the robot |
| Y | Left | meters | Left direction of the robot |
| Z | Up | meters | Upward direction |

## Rotation Conventions

- **Roll**: Rotation around X-axis (positive = left tilt)
- **Pitch**: Rotation around Y-axis (positive = nose up)
- **Yaw**: Rotation around Z-axis (positive = left turn)

## Units

| Quantity | Unit | Description |
|----------|------|-------------|
| Position | meters (m) | X, Y, Z coordinates |
| Orientation | radians (rad) | Roll, Pitch, Yaw angles |
| Linear velocity | m/s | Speed along axes |
| Angular velocity | rad/s | Rotational speed |

## Common Frame Names

| Frame | Description |
|-------|-------------|
| `world` | Fixed reference frame |
| `map` | Map-level frame |
| `odom` | Odometry frame |
| `base_link` | Robot base frame |
| `base_footprint` | Ground projection of base_link |
| `laser_link` | Laser scanner frame |
| `camera_link` | Camera frame |

## Transform Examples

### Static Transform (base_link → laser_link)
```yaml
Translation:
  x: 0.1
  y: 0.0
  z: 0.2
Rotation:
  x: 0.0
  y: 0.0
  z: 0.0
  w: 1.0
```

### Dynamic Transform (odom → base_link)
```yaml
Translation:
  x: 1.0
  y: 0.5
  z: 0.0
Rotation:
  x: 0.0
  y: 0.0
  z: 0.0
  w: 1.0
```

## References

- [ROS2 TF2 Documentation](https://docs.ros.org/en/rolling/Tutorials/Intermediate/Tf2/)
- [REP 105: Coordinate Frames](https://www.ros.org/reps/rep-0105.html)
