# Multi-Robot Session Sim

## Setup

```bash
ros2 launch lappa_sim multi_robot.launch.py num_robots:=2
```

## Description

Spawns two robot bases in a shared Gazebo world.
Each robot has its own namespace and tf tree.

## Namespaces

- `/robot1/*`
- `/robot2/*`

## Topics per robot

- `/<ns>/cmd_vel`
- `/<ns>/odom`
- `/<ns>/scan`

## World

Empty world with two starting positions 3m apart.
