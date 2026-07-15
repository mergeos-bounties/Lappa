# Coordinate Conventions

Lappa's native simulation uses a **2D right-handed world frame** with all
linear quantities in **meters** and angular quantities in **radians**.

---

## World Frame

| Quantity | Unit | Description |
|----------|------|-------------|
| `x` | meters (m) | Horizontal position along the world X-axis (forward direction) |
| `y` | meters (m) | Horizontal position along the world Y-axis (leftward direction) |
| `theta` | radians (rad) | Orientation angle, measured counter-clockwise from the +X axis |
| `z` | meters (m) | Vertical position (reserved; always 0 in native sim) |

**Origin:** `(0.0, 0.0, 0.0)` — the world origin, located at the center of the
default 8 m x 8 m obstacle-bounded arena.

**Angle convention:** `theta = 0` points along the **+X** axis (to the right in
top-down view). Positive `theta` rotates **counter-clockwise** (standard
mathematical convention).

### Angle Wrapping

All angles are wrapped to `[-pi, +pi)` using:

```python
def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi
```

---

## Body Frame (Twist)

Velocity commands and state are expressed in the **robot body frame**:

| Field | Unit | Description |
|-------|------|-------------|
| `linear_x` (`vx`) | m/s | Forward velocity (robot's local X-axis) |
| `linear_y` (`vy`) | m/s | Lateral velocity (robot's local Y-axis; holonomic robots only) |
| `angular_z` (`w`) | rad/s | Rotational velocity (positive = counter-clockwise) |

### Body to World Integration

```
world_x  += (cos(theta) * vx - sin(theta) * vy) * dt
world_y  += (sin(theta) * vx + cos(theta) * vy) * dt
theta    += w * dt
```

For non-holonomic robots (diff-drive, tricycle, ackermann), `vy` is always 0
and the robot can only move in its forward direction.

---

## Robot Model Dimensions

| Model | Wheelbase / Reach | Robot Radius | Lidar Rays | Max Range |
|-------|-------------------|-------------|------------|-----------|
| `diff_drive_2w` | track = 0.32 m, r = 0.05 m | 0.20 m | 36 | 3.0 m |
| `omni_3w` | r = 0.04 m | 0.20 m | 36 | 3.0 m |
| `tricycle_3w` | L = 0.35 m | 0.22 m | 180 | 8.0 m |
| `ackermann_4w` | L = 0.50 m | 0.20 m | 36 | 3.0 m |
| `simple_arm` | l1 = 0.60 m, l2 = 0.50 m | -- | -- | -- |
| `mecanum_4w` | half-L=0.20 m, half-W=0.18 m, r=0.05 m | 0.20 m | 36 | 3.0 m |

---

## Path Fixtures and Trajectories

Path fixtures are sequences of waypoints that define a trajectory through the
world. Each waypoint is a dictionary with these keys (all in SI units):

| Key | Type | Unit | Description |
|-----|------|------|-------------|
| `t` / `timestamp` | float | seconds (s) | Elapsed time since sim start |
| `x` | float | meters (m) | World X position |
| `y` | float | meters (m) | World Y position |
| `z` | float | meters (m) | World Z position (0 in native sim) |
| `theta` / `rotation_z` | float | radians (rad) | Orientation angle |
| `linear_x` | float | m/s | Forward velocity in body frame |
| `linear_y` | float | m/s | Lateral velocity in body frame |
| `velocity` | float | m/s | Speed magnitude sqrt(vx^2 + vy^2) |

### Trajectory CSV Export Format

When exporting trajectories via `lappa.export.csv`, the output columns are:

```
timestamp, x, y, z, velocity, acceleration, jerk, rotation_x, rotation_y, rotation_z
```

Where `rotation_z` maps to `theta` in the simulation state.

### Sample Trajectory (meters)

```python
[
    {"timestamp": 0, "x": 0, "y": 0, "z": 0, "velocity": 0},
    {"timestamp": 1, "x": 1, "y": 0, "z": 0, "velocity": 1},
    {"timestamp": 2, "x": 3, "y": 0, "z": 0, "velocity": 2},
    {"timestamp": 3, "x": 6, "y": 0, "z": 0, "velocity": 3},
]
```

This represents straight-line motion along the +X axis at increasing speed.

---

## Obstacles

Obstacles are **axis-aligned bounding boxes** (AABB) defined in the **world
frame** as 4-tuples:

```
(cx, cy, half_width, half_height)   <-- all in meters
```

Where `(cx, cy)` is the center point and `half_width`/`half_height` are the
half-extents from the center.

### Default Arena

The default obstacle set defines an 8 m x 8 m bounded arena centered at the
origin, plus interior obstacles for denser lidar scenes:

```python
DEFAULT_OBSTACLES = [
    # Boundary walls (centered on edges, extending inward)
    ( 0.0,  4.0, 4.08, 0.08),   # north wall
    ( 0.0, -4.0, 4.08, 0.08),   # south wall
    ( 4.0,  0.0, 0.08, 4.08),   # east wall
    (-4.0,  0.0, 0.08, 4.08),   # west wall
    # Interior obstacles (various sizes)
    ( 2.0,  0.5, 0.35, 0.35),
    (-1.5,  1.2, 0.40, 0.25),
    # ... additional interior objects
]
```

---

## Lidar Scan Conventions

| Property | Default Value |
|----------|---------------|
| Ray count | 36 rays (360 degrees evenly spaced) |
| Max range | 3.0 meters |
| Angle 0 | Aligned with `theta` (robot forward) |
| Angle step | Counter-clockwise |
| Return | List of distances (meters); `max_range` if no hit |

The lidar origin is the robot's `(x, y)` position. Rays are cast in the world
frame at angles `theta + 2*pi*i/n` for `i = 0 ... n-1`.

---

## Collision Detection

Collisions are detected by checking whether the robot's bounding circle
(radius = `robot_radius`) overlaps with any obstacle AABB. The robot radius
varies by model (see table above).

```python
def _circle_hits_aabb(x, y, radius, obstacle) -> bool:
    cx, cy, half_w, half_h = obstacle
    nearest_x = max(cx - half_w, min(x, cx + half_w))
    nearest_y = max(cy - half_h, min(y, cy + half_h))
    return (x - nearest_x)**2 + (y - nearest_y)**2 < radius**2
```

---

## ROS2 / Real Robot Mapping

When bridging to real ROS2 (via Docker launch), Lappa maps its native state to
ROS2 messages:

| Native Field | ROS2 Message | Notes |
|-------------|-------------|-------|
| `x, y, theta` | `nav_msgs/Odometry.pose.pose` | 2D pose; Z = 0 |
| `linear_x, angular_z` | `geometry_msgs/Twist` | Velocity command |
| `lidar` | `sensor_msgs/LaserScan` | Ranges mapped to ROS angles |

The coordinate convention is compatible with ROS REP-103 (X forward, Y left,
Z up).

---

## Summary

| Dimension | Unit | Range / Convention |
|-----------|------|-------------------|
| Position (x, y) | meters | World frame; origin at center of 8 m arena |
| Orientation (theta) | radians | 0 = +X, positive = CCW, wrapped to [-pi, pi) |
| Velocity (linear) | m/s | Body frame; forward = +linear_x |
| Velocity (angular) | rad/s | Body frame; CCW = positive |
| Time (t) | seconds | Monotonic sim clock |
| Obstacles | meters | World-frame AABB (cx, cy, half_w, half_h) |
| Lidar range | meters | Max default 3.0 m |

All public APIs (`SimState`, trajectory export, HTTP API, CLI) consistently use
these SI units.
