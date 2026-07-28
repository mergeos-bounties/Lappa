"""Tests for lappa path resample CLI and core resample logic."""

import json
import math
import os
import sys
from pathlib import Path

import pytest

# Add the server package to path (repo root / packages/server/src)
_server_src = os.path.join(os.path.dirname(__file__), "..", "packages", "server", "src")
if _server_src not in sys.path:
    sys.path.insert(0, _server_src)

from lappa.cli import _path_points_from_fixture, _path_stats, _resample


FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# _resample unit tests
# ---------------------------------------------------------------------------

class TestResampleFunction:
    """Unit tests for the _resample() function."""

    def test_straight_line_step_equals_length(self):
        """A 10m line resampled at 10m should yield only the two endpoints."""
        pts = [(0.0, 0.0), (10.0, 0.0)]
        result = _resample(pts, step_m=10.0)
        assert len(result) == 2
        assert result[0] == (0.0, 0.0)
        assert result[1] == (10.0, 0.0)

    def test_straight_line_step_half_length(self):
        """A 10m line resampled at 5m should yield 3 points (0, 5, 10)."""
        pts = [(0.0, 0.0), (10.0, 0.0)]
        result = _resample(pts, step_m=5.0)
        assert len(result) == 3
        assert result[0] == (0.0, 0.0)
        assert result[1] == (5.0, 0.0)
        assert result[2] == (10.0, 0.0)

    def test_straight_line_step_quarter_length(self):
        """A 10m line resampled at 2.5m should yield 5 points."""
        pts = [(0.0, 0.0), (10.0, 0.0)]
        result = _resample(pts, step_m=2.5)
        assert len(result) == 5
        assert result[0] == (0.0, 0.0)
        assert result[1] == (2.5, 0.0)
        assert result[2] == (5.0, 0.0)
        assert result[3] == (7.5, 0.0)
        assert result[4] == (10.0, 0.0)

    def test_diagonal_line(self):
        """3-4-5 triangle: 5m hypotenuse, step 2.5m → 3 points."""
        pts = [(0.0, 0.0), (3.0, 4.0)]
        result = _resample(pts, step_m=2.5)
        # 5m / 2.5 = 2 intervals → 3 points
        assert len(result) == 3
        # First point at origin
        assert abs(result[0][0]) < 1e-9 and abs(result[0][1]) < 1e-9
        # Midpoint should be at ~1.5, 2.0 (half of 3,4)
        assert abs(result[1][0] - 1.5) < 0.01
        assert abs(result[1][1] - 2.0) < 0.01
        # Last point should be the original end
        assert abs(result[2][0] - 3.0) < 1e-9
        assert abs(result[2][1] - 4.0) < 1e-9

    def test_zigzag_preserves_endpoints(self):
        """First and last points must always be present."""
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
        result = _resample(pts, step_m=0.5)
        assert result[0] == (0.0, 0.0)
        assert result[-1] == (3.0, 0.0)

    def test_single_point_returns_copy(self):
        """A single point should return a list containing just that point."""
        pts = [(0.0, 0.0)]
        result = _resample(pts, step_m=0.5)
        assert result == [(0.0, 0.0)]

    def test_negative_step_raises(self):
        """Negative step_m should raise ValueError."""
        pts = [(0.0, 0.0), (1.0, 0.0)]
        with pytest.raises(ValueError, match="step_m must be positive"):
            _resample(pts, step_m=-1.0)

    def test_zero_step_raises(self):
        """Zero step_m should raise ValueError."""
        pts = [(0.0, 0.0), (1.0, 0.0)]
        with pytest.raises(ValueError, match="step_m must be positive"):
            _resample(pts, step_m=0.0)

    def test_figure_eight_closed_loop(self):
        """Resample a figure-eight loop; verify start=end."""
        pts = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0), (1.0, -1.0),
               (0.0, 0.0), (-1.0, 1.0), (-2.0, 0.0), (-1.0, -1.0), (0.0, 0.0)]
        result = _resample(pts, step_m=0.5)
        assert len(result) >= 2
        # Start and end should both be at origin
        assert abs(result[0][0]) < 1e-9 and abs(result[0][1]) < 1e-9
        assert abs(result[-1][0]) < 1e-9 and abs(result[-1][1]) < 1e-9

    def test_short_segments_skipped(self):
        """Degenerate segments (zero-length) should be skipped."""
        pts = [(0.0, 0.0), (0.0, 0.0), (5.0, 0.0)]
        result = _resample(pts, step_m=1.0)
        assert len(result) == 6  # 0,1,2,3,4,5
        assert result[0] == (0.0, 0.0)
        assert result[-1] == (5.0, 0.0)

    def test_resample_preserves_order(self):
        """Resampled points must be monotonic along the polyline."""
        pts = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
        result = _resample(pts, step_m=0.5)
        for i in range(len(result) - 1):
            assert result[i] != result[i + 1] or len(result) == 1


# ---------------------------------------------------------------------------
# _path_stats unit tests
# ---------------------------------------------------------------------------

class TestPathStats:
    """Tests for the _path_stats() helper."""

    def test_straight_line_length(self):
        pts = [(0.0, 0.0), (3.0, 4.0)]
        stats = _path_stats(pts)
        assert stats["points"] == 2
        # 3-4-5 triangle → length 5
        assert abs(stats["path_length_m"] - 5.0) < 1e-4
        assert abs(stats["net_displacement_m"] - 5.0) < 1e-4

    def test_single_point_stats(self):
        pts = [(0.0, 0.0)]
        stats = _path_stats(pts)
        assert stats["points"] == 1
        assert stats["path_length_m"] == 0.0
        assert stats["net_displacement_m"] == 0.0

    def test_figure_eight_net_zero(self):
        """Closed loop has net displacement of zero."""
        pts = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0), (1.0, -1.0),
               (0.0, 0.0), (-1.0, 1.0), (-2.0, 0.0), (-1.0, -1.0), (0.0, 0.0)]
        stats = _path_stats(pts)
        assert stats["points"] == 9
        assert abs(stats["net_displacement_m"]) < 1e-4
        assert stats["path_length_m"] > 0


# ---------------------------------------------------------------------------
# _path_points_from_fixture tests
# ---------------------------------------------------------------------------

class TestFixtureLoader:
    """Tests for the _path_points_from_fixture() loader."""

    def test_load_figure_eight(self):
        pts = _path_points_from_fixture(FIXTURES_DIR / "figure_eight.json")
        assert len(pts) == 9
        assert pts[0] == (0.0, 0.0)
        assert pts[-1] == (0.0, 0.0)

    def test_load_straight_line(self):
        pts = _path_points_from_fixture(FIXTURES_DIR / "straight_line.json")
        assert len(pts) == 2
        assert pts[0] == (0.0, 0.0)
        assert pts[1] == (10.0, 0.0)

    def test_load_diagonal_line(self):
        pts = _path_points_from_fixture(FIXTURES_DIR / "diagonal_line.json")
        assert len(pts) == 2
        assert pts[0] == (0.0, 0.0)
        assert pts[1] == (3.0, 4.0)

    def test_load_zigzag(self):
        pts = _path_points_from_fixture(FIXTURES_DIR / "zigzag.json")
        assert len(pts) == 5

    def test_missing_file_raises(self):
        with pytest.raises(Exception):
            _path_points_from_fixture(Path("/nonexistent/file.json"))


# ---------------------------------------------------------------------------
# Integration tests: end-to-end resample from fixture
# ---------------------------------------------------------------------------

class TestResampleIntegration:
    """End-to-end: load fixture → resample → verify stats."""

    @pytest.mark.parametrize("fixture_name,step,expected_min_points", [
        ("figure_eight.json", 0.5, 10),
        ("straight_line.json", 2.0, 6),   # 10m / 2m = 5 intervals + 1
        ("diagonal_line.json", 1.0, 6),    # 5m / 1m = 5 intervals + 1
        ("zigzag.json", 0.5, 6),
    ])
    def test_resample_from_fixture(self, fixture_name, step, expected_min_points):
        path = FIXTURES_DIR / fixture_name
        pts = _path_points_from_fixture(path)
        result = _resample(pts, step_m=step)
        assert len(result) >= expected_min_points, (
            f"{fixture_name} resampled at {step}m: expected ≥{expected_min_points}, got {len(result)}"
        )
        # Stats should be computed correctly
        stats = _path_stats(result)
        assert stats["points"] == len(result)
        assert stats["path_length_m"] > 0