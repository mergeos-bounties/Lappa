"""Collision radius check helpers for path waypoint validation."""

from __future__ import annotations

CircleObstacle = tuple[float, float, float]  # (center_x, center_y, radius)


def point_in_circle(
    px: float, py: float, cx: float, cy: float, radius: float
) -> bool:
    """Return True if point (px, py) is inside the circle (cx, cy, radius)."""
    dx = px - cx
    dy = py - cy
    return dx * dx + dy * dy <= radius * radius


def flag_collisions(
    path: list[tuple[float, float]],
    obstacles: list[CircleObstacle],
) -> list[bool]:
    """Return a bool list, True where the path point intersects any obstacle.

    Parameters
    ----------
    path : list of (x, y) waypoints.
    obstacles : list of (center_x, center_y, radius) circular obstacles.

    Returns
    -------
    list[bool] of the same length as *path*, where *True* means the point
    lies inside at least one circular obstacle.
    """
    result: list[bool] = []
    for px, py in path:
        collides = any(
            point_in_circle(px, py, cx, cy, r) for cx, cy, r in obstacles
        )
        result.append(collides)
    return result


def first_collision(
    path: list[tuple[float, float]],
    obstacles: list[CircleObstacle],
) -> int | None:
    """Return the index of the first path point inside any circular obstacle,
    or None if the entire path is clear."""
    flags = flag_collisions(path, obstacles)
    for i, hit in enumerate(flags):
        if hit:
            return i
    return None
