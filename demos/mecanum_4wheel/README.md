# Mecanum 4-Wheel Demo

## Setup

```bash
ros2 launch lappa_demo mecanum_4wheel.launch.py
```

## Description

Omni-directional movement using 4 mecanum wheels.
Supports forward, strafe, and rotation simultaneously.

## Wheel Configuration

```
FL  FR
  X
RL  RR
```

FL=45deg, FR=-45deg, RL=-45deg, RR=45deg

## Topics

- `/cmd_vel` — Twist (linear x/y + angular z)
- `/odom` — Odometry
