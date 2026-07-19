# Differential Tracked Robot Demo

## Setup

```bash
ros2 launch lappa_demo differential_tracked.launch.py
```

## Description

Simulates a differential-drive tracked robot navigating a simple course.
Left and right track velocities are controlled independently.

## Topics

- `/cmd_vel` — Twist input
- `/odom` — Odometry output
- `/tf` — Transform tree

## Parameters

- `wheel_separation`: 0.4m
- `max_linear_speed`: 0.5 m/s
- `max_angular_speed`: 1.0 rad/s
