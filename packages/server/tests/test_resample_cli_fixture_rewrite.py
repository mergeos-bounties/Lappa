"""CLI smoke tests for lappa path resample --step-m fixture rewrite.

Covers: --json output, --out fixture rewriting, stats --json, and
end-to-end resample → write → reread round-trip validation.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lappa.cli import app

FIXTURES = Path(__file__).parent / "fixtures"


def _run(*args: str) -> "CliRunnerResult":
    runner = CliRunner()
    return runner.invoke(app, list(args))


# ── path stats ────────────────────────────────────────────────


def test_path_stats_json_line_fixture() -> None:
    """--json emits a single JSON object with stats keys."""
    result = _run(
        "path", "stats", "--file", str(FIXTURES / "sample_path_line.json"), "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["points"] == 3
    assert data["path_length_m"] == 4.0
    assert data["net_displacement_m"] == 4.0


def test_path_stats_json_square_loop() -> None:
    """--json works for closed loops."""
    result = _run(
        "path", "stats", "--file", str(FIXTURES / "sample_path_square_loop.json"), "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["points"] == 5
    assert data["path_length_m"] == 20.0
    assert data["net_displacement_m"] == 0.0


def test_path_stats_json_hexagon_2m() -> None:
    """--json works for hexagon fixture."""
    result = _run(
        "path", "stats", "--file", str(FIXTURES / "sample_path_hexagon_2m.json"), "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["points"] > 0
    assert data["path_length_m"] > 0


# ── path resample --json ────────────────────────────────────────


def test_resample_json_line_default_step() -> None:
    """--json output contains all required fields."""
    result = _run(
        "path", "resample", "--file", str(FIXTURES / "sample_path_line.json"), "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "points" in data
    assert "path_length_m" in data
    assert "net_displacement_m" in data
    assert "step_m" in data
    assert "original_points" in data
    assert "original_length_m" in data


def test_resample_json_line_step_0_5() -> None:
    """4m line with 0.5m step → 9 points."""
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_line.json"),
        "--step-m",
        "0.5",
        "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["points"] == 9  # 0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0
    assert data["original_points"] == 3
    assert data["original_length_m"] == 4.0
    assert abs(data["path_length_m"] - 4.0) < 0.01


def test_resample_json_square_loop_step_1() -> None:
    """5x5 square loop with 1m step → 21 points."""
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_square_loop.json"),
        "--step-m",
        "1.0",
        "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    # 20m loop / 1m → 21 points (20 steps + endpoints)
    assert data["points"] == 21
    assert data["original_points"] == 5
    assert data["original_length_m"] == 20.0
    assert abs(data["path_length_m"] - 20.0) < 0.01


def test_resample_json_diamond_fixture() -> None:
    """Resample diamond fixture with 0.25m step."""
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_diamond.json"),
        "--step-m",
        "0.25",
        "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["points"] > data["original_points"]
    assert data["step_m"] == 0.25
    assert abs(data["path_length_m"] - data["original_length_m"]) < 0.1


def test_resample_json_l_shape_fixture() -> None:
    """Resample L-shape fixture."""
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_l_shape.json"),
        "--step-m",
        "0.3",
        "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["points"] >= data["original_points"]
    assert data["original_points"] > 0


# ── path resample --out (fixture rewrite) ───────────────────────


def test_resample_out_writes_valid_fixture(tmp_path: Path) -> None:
    """--out writes JSON fixture that can be reread by stats."""
    out_file = tmp_path / "out_resampled.json"
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_line.json"),
        "--step-m",
        "0.5",
        "--out",
        str(out_file),
    )
    assert result.exit_code == 0, result.output
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "name" in data
    assert "points" in data
    assert "path_length_m" in data
    assert "step_m" in data
    assert len(data["points"]) == 9


def test_resample_out_roundtrips_with_stats(tmp_path: Path) -> None:
    """Write resampled fixture, then read with stats --json → same length."""
    out_file = tmp_path / "roundtrip.json"

    # Write
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_square_loop.json"),
        "--step-m",
        "1.0",
        "--out",
        str(out_file),
    )
    assert result.exit_code == 0, result.output

    # Read back with stats
    result2 = _run(
        "path", "stats", "--file", str(out_file), "--json",
    )
    assert result2.exit_code == 0, result2.output
    data = json.loads(result2.output)
    assert abs(data["path_length_m"] - 20.0) < 0.02


def test_resample_out_json_combined(tmp_path: Path) -> None:
    """--json --out combined: JSON output includes out path."""
    out_file = tmp_path / "combined.json"
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_line.json"),
        "--step-m",
        "1.0",
        "--json",
        "--out",
        str(out_file),
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "out" in data
    assert str(out_file.resolve()) in data["out"]
    assert out_file.exists()


def test_resample_out_preserves_original_on_different_step(tmp_path: Path) -> None:
    """Output fixture contains different step_m than default."""
    out_file = tmp_path / "custom_step.json"
    _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_hexagon_2m.json"),
        "--step-m",
        "0.75",
        "--out",
        str(out_file),
    )
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["step_m"] == 0.75
    assert data["path_length_m"] > 0
    assert len(data["points"]) > 2


def test_resample_out_creates_parent_dirs(tmp_path: Path) -> None:
    """--out creates non-existent parent directories."""
    out_file = tmp_path / "nested" / "sub" / "output.json"
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_line.json"),
        "--step-m",
        "0.5",
        "--out",
        str(out_file),
    )
    assert result.exit_code == 0, result.output
    assert out_file.exists()


# ── edge cases ──────────────────────────────────────────────────


def test_resample_json_large_step_keeps_endpoints() -> None:
    """Step larger than total path length → 2 points (endpoints only)."""
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_line.json"),
        "--step-m",
        "100",
        "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["points"] == 2  # only endpoints


def test_resample_json_step_equals_segment(tmp_path: Path) -> None:
    """Write a fixture and verify it has unique name derived from filename."""
    out_file = tmp_path / "named.json"
    _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / "sample_path_diamond.json"),
        "--step-m",
        "0.5",
        "--out",
        str(out_file),
    )
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["name"] == "diamond"
    assert isinstance(data["points"], list)
    # All points are valid [x, y] pairs
    for pt in data["points"]:
        assert isinstance(pt, list)
        assert len(pt) == 2
        assert isinstance(pt[0], (int, float))
        assert isinstance(pt[1], (int, float))


# ── multi-fixture parametrized tests ────────────────────────────


SAMPLE_FIXTURES = [
    "sample_path_line.json",
    "sample_path_square_loop.json",
    "sample_path_diamond.json",
    "sample_path_l_shape.json",
    "sample_path_hexagon_2m.json",
    "sample_path_jagged.json",
    "sample_path_scurve.json",
    "sample_path_sawtooth.json",
    "sample_path_meander.json",
    "sample_path_ridge.json",
    "sample_path_figure_eight.json",
    "sample_path_rounded_rect.json",
    "sample_path_corridor_zigzag.json",
    "sample_path_l_corridor_loop.json",
]


@pytest.mark.parametrize("fixture_name", SAMPLE_FIXTURES)
def test_resample_json_all_fixtures_parseable(fixture_name: str) -> None:
    """Every sample fixture can be resampled via --json."""
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / fixture_name),
        "--step-m",
        "0.5",
        "--json",
    )
    assert result.exit_code == 0, f"Failed on {fixture_name}: {result.output}"
    data = json.loads(result.output)
    assert data["points"] >= 2
    assert data["path_length_m"] >= 0
    assert data["step_m"] == 0.5
    assert "original_points" in data
    assert "original_length_m" in data


@pytest.mark.parametrize("fixture_name", SAMPLE_FIXTURES)
def test_resample_out_all_fixtures_writable(fixture_name: str, tmp_path: Path) -> None:
    """Every sample fixture can be resampled and written to --out."""
    out_file = tmp_path / f"resampled_{fixture_name}"
    result = _run(
        "path",
        "resample",
        "--file",
        str(FIXTURES / fixture_name),
        "--step-m",
        "0.5",
        "--out",
        str(out_file),
    )
    assert result.exit_code == 0, f"Failed on {fixture_name}: {result.output}"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "name" in data
    assert "points" in data
    assert len(data["points"]) >= 2
    assert "step_m" in data
    assert "path_length_m" in data
