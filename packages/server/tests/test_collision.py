"""Tests for collision radius check helpers."""


from lappa.sim.collision import point_in_circle, flag_collisions, first_collision


def test_point_in_circle_inside() -> None:
    """Exact center should be inside."""
    assert point_in_circle(0.0, 0.0, 0.0, 0.0, 1.0) is True


def test_point_in_circle_on_boundary() -> None:
    """Point on radius boundary is considered inside."""
    assert point_in_circle(1.0, 0.0, 0.0, 0.0, 1.0) is True


def test_point_in_circle_outside() -> None:
    """Point outside circle should be False."""
    assert point_in_circle(3.0, 0.0, 0.0, 0.0, 1.0) is False


def test_point_in_circle_diagonal() -> None:
    """Diagonal distance check with tolerance."""
    d = 0.5
    # (0.5, 0.5) is distance ~0.707 from origin → inside radius 1
    assert point_in_circle(d, d, 0.0, 0.0, 1.0) is True
    assert point_in_circle(0.9, 0.0, 0.0, 0.0, 1.0) is True
    assert point_in_circle(1.1, 0.0, 0.0, 0.0, 1.0) is False


def test_point_in_circle_offset_center() -> None:
    """Circle not at origin."""
    assert point_in_circle(5.0, 5.0, 5.0, 5.0, 2.0) is True
    assert point_in_circle(7.0, 5.0, 5.0, 5.0, 2.0) is True  # on boundary
    assert point_in_circle(7.1, 5.0, 5.0, 5.0, 2.0) is False


def test_flag_collisions_all_clear() -> None:
    path = [(10.0, 10.0), (20.0, 20.0), (30.0, 30.0)]
    obstacles = [(0.0, 0.0, 1.0), (5.0, 5.0, 1.0)]
    assert flag_collisions(path, obstacles) == [False, False, False]


def test_flag_collisions_some_hit() -> None:
    path = [(10.0, 10.0), (0.0, 0.0), (30.0, 30.0)]
    obstacles = [(0.0, 0.0, 1.0)]
    assert flag_collisions(path, obstacles) == [False, True, False]


def test_flag_collisions_overlapping_obstacles() -> None:
    """Point inside overlapping obstacle pair."""
    path = [(1.5, 0.0)]
    obstacles = [(0.0, 0.0, 2.0), (2.0, 0.0, 0.5)]  # both cover (1.5, 0)
    assert flag_collisions(path, obstacles) == [True]


def test_first_collision_none() -> None:
    path = [(10.0, 10.0)]
    obstacles = [(0.0, 0.0, 1.0)]
    assert first_collision(path, obstacles) is None


def test_first_collision_found() -> None:
    path = [(10.0, 10.0), (0.5, 0.5), (20.0, 20.0), (0.0, 0.0)]
    obstacles = [(0.0, 0.0, 1.0)]
    # (0.5, 0.5) is first hit at index 1
    assert first_collision(path, obstacles) == 1


def test_empty_path() -> None:
    assert flag_collisions([], [(0.0, 0.0, 1.0)]) == []
    assert first_collision([], [(0.0, 0.0, 1.0)]) is None


def test_no_obstacles() -> None:
    path = [(0.0, 0.0), (1.0, 1.0)]
    assert flag_collisions(path, []) == [False, False]
