"""Tests for polyline resample helper."""

from __future__ import annotations

import json

from lappa.cli import _resample, _path_stats


def test_resample_identity_short() -> None:
    """Resample with step larger than total length should keep endpoints."""
    pts = [(0.0, 0.0), (1.0, 0.0)]
    result = _resample(pts, 5.0)
    assert result == pts


def test_resample_step_half() -> None:
    """1m line with 0.5m step → 3 points (0, 0.5, 1)."""
    pts = [(0.0, 0.0), (1.0, 0.0)]
    result = _resample(pts, 0.5)
    assert len(result) == 3
    assert abs(result[0][0]) < 1e-12
    assert abs(result[1][0] - 0.5) < 1e-12
    assert abs(result[2][0] - 1.0) < 1e-12


def test_resample_preserves_length() -> None:
    """Resampled path length should be close to original."""
    pts = [(0.0, 0.0), (3.0, 4.0)]  # 5m line
    result = _resample(pts, 0.3)
    orig_len = _path_stats(pts)["path_length_m"]
    new_len = _path_stats(result)["path_length_m"]
    assert abs(new_len - orig_len) < 0.01


def test_resample_multi_segment() -> None:
    """L-shape: (0,0)→(3,0)→(3,4) → 7m total."""
    pts = [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]
    result = _resample(pts, 1.0)
    # Expect points at: (0,0), (1,0), (2,0), (3,0), (3,1), (3,2), (3,3), (3,4)
    assert len(result) == 8


def test_resample_s_curve() -> None:
    """S-curve fixture with 0.5m step."""
    pts = [
        (0.0, 1.0), (1.0, 1.2), (2.0, 1.8), (3.0, 2.2),
        (4.0, 2.0), (5.0, 1.5), (6.0, 1.0), (7.0, 0.8), (8.0, 1.0),
    ]
    result = _resample(pts, 0.5)
    assert len(result) > len(pts)
    # First and last must match
    assert abs(result[0][0] - pts[0][0]) < 1e-12
    assert abs(result[-1][0] - pts[-1][0]) < 1e-12


def test_resample_empty_or_single() -> None:
    assert _resample([], 0.5) == []
    assert _resample([(1.0, 2.0)], 0.5) == [(1.0, 2.0)]


def test_resample_negative_step() -> None:
    import pytest
    with pytest.raises(ValueError, match="positive"):
        _resample([(0.0, 0.0), (1.0, 0.0)], -0.1)


def test_resample_zero_step() -> None:
    import pytest
    with pytest.raises(ValueError, match="positive"):
        _resample([(0.0, 0.0), (1.0, 0.0)], 0.0)
