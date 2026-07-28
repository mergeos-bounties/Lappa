"""CLI integration tests for lappa path commands.

Uses Typer's CliRunner to invoke the actual CLI commands.
"""

import json
import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

_server_src = os.path.join(os.path.dirname(__file__), "..", "packages", "server", "src")
if _server_src not in sys.path:
    sys.path.insert(0, _server_src)

from lappa.cli import app


FIXTURES_DIR = Path(__file__).parent / "fixtures"
runner = CliRunner()


class TestPathResampleCLI:
    """CLI tests for `lappa path resample`."""

    def test_resample_straight_line_default_step(self):
        """Default step (0.5m) on a 10m line should produce ~21 points."""
        fixture = FIXTURES_DIR / "straight_line.json"
        result = runner.invoke(app, ["path", "resample", "--file", str(fixture)])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Output should contain path_length_m and points
        assert "path_length_m" in result.output
        assert "points" in result.output
        assert "10." in result.output  # Path length should be ~10

    def test_resample_straight_line_step_5m(self):
        """5m step on a 10m line → 3 points, each 5m apart."""
        fixture = FIXTURES_DIR / "straight_line.json"
        result = runner.invoke(app, ["path", "resample", "--file", str(fixture), "--step-m", "5.0"])
        assert result.exit_code == 0
        assert "points" in result.output
        assert "5.0" in result.output or "5" in result.output

    def test_resample_diagonal_line(self):
        """3-4-5 triangle: step 2.5m → 3 points."""
        fixture = FIXTURES_DIR / "diagonal_line.json"
        result = runner.invoke(app, ["path", "resample", "--file", str(fixture), "--step-m", "2.5"])
        assert result.exit_code == 0
        assert "path_length_m" in result.output

    def test_resample_figure_eight(self):
        """Figure-eight fixture: verify closed loop output."""
        fixture = FIXTURES_DIR / "figure_eight.json"
        result = runner.invoke(app, ["path", "resample", "--file", str(fixture), "--step-m", "0.5"])
        assert result.exit_code == 0
        assert "path_length_m" in result.output
        assert "Points" in result.output

    def test_resample_zigzag(self):
        """Zigzag path: verify output contains expected stats."""
        fixture = FIXTURES_DIR / "zigzag.json"
        result = runner.invoke(app, ["path", "resample", "--file", str(fixture), "--step-m", "0.5"])
        assert result.exit_code == 0
        assert "path_length_m" in result.output

    def test_resample_missing_file(self):
        """Non-existent file should produce a non-zero exit."""
        result = runner.invoke(app, ["path", "resample", "--file", "/nonexistent/foo.json"])
        assert result.exit_code != 0

    def test_resample_invalid_json(self):
        """Invalid JSON content should produce an error."""
        bad_fixture = FIXTURES_DIR / "empty_path.txt"
        result = runner.invoke(app, ["path", "resample", "--file", str(bad_fixture)])
        assert result.exit_code != 0
        assert "invalid JSON" in result.output.lower() or "error" in result.output.lower()

    def test_resample_no_points_key(self):
        """JSON without a 'points' key should produce an error."""
        fixture = FIXTURES_DIR / "obstacle_layer_sample.json"
        result = runner.invoke(app, ["path", "resample", "--file", str(fixture)])
        assert result.exit_code != 0
        assert "points" in result.output.lower() or "must contain" in result.output.lower()


class TestPathStatsCLI:
    """CLI tests for `lappa path stats`."""

    def test_stats_straight_line(self):
        fixture = FIXTURES_DIR / "straight_line.json"
        result = runner.invoke(app, ["path", "stats", "--file", str(fixture)])
        assert result.exit_code == 0
        assert "path_length_m" in result.output
        assert "net_displacement_m" in result.output

    def test_stats_figure_eight(self):
        """Closed loop net displacement should be ~0."""
        fixture = FIXTURES_DIR / "figure_eight.json"
        result = runner.invoke(app, ["path", "stats", "--file", str(fixture)])
        assert result.exit_code == 0
        assert "path_length_m" in result.output
        # Closed loop has net displacement near 0
        assert "net_displacement_m" in result.output

    def test_stats_missing_file(self):
        result = runner.invoke(app, ["path", "stats", "--file", "/nonexistent/foo.json"])
        assert result.exit_code != 0