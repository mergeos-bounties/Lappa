# Obstacle Map + Lidar Sim

## Setup

```bash
ros2 launch lappa_sim obstacle_lidar.launch.py
```

## Description

Gazebo world with box and cylinder obstacles.
Robot equipped with 360-degree lidar.

## Obstacles

- 5x box obstacles (0.5m cubes)
- 3x cylinder obstacles (0.3m radius)
- Random placement in 10x10m area

## Lidar

- 360 rays
- 10m range
- 1deg resolution
- Topic: `/scan`

## Map

Occupancy grid published on `/map`.
