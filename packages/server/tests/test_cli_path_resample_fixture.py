"""CLI smoke test for `lappa path resample --step-m` (Fixes #52).

Exercises the resample subcommand on an existing fixture in JSON mode and
validates the machine-readable output, plus fixture file round-trip via --out.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from lappa.cli import app

FIXTURE_DIR = Path(__file__).parent / "fixtures"

runner = CliRunner()


def _line_fixture() -> Path:
    return FIXTURE_DIR / "sample_path_line.json"


def _zigzag_fixture() -> Path:
    return FIXTURE_DIR / "sample_path_zigzag.json"


def _run_resample(fixture: Path, step_m: float, out: Path | None = None) -> CliRunner.CliResult:
    base_cmd = ["path", "resample", "--json", "--file", str(fixture), "--step-m", str(step_m)]
    if out is not None:
        base_cmd.extend(["--out", str(out)])
    return runner.invoke(app, base_cmd)


class TestPathResampleCLI:
    @pytest.mark.parametrize("step_m", [0.5, 1.0, 0.25])
    def test_resample_json_output(self, step_m: float, tmp_path: Path) -> None:
        """Machine-readable JSON contains stats and a points array."""
        result = _run_resample(_line_fixture(), step_m)
        assert result.exit_code == 0, result.output
        payload: dict[str, Any] = json.loads(result.stdout)
        assert "step_m" in payload
        assert "points" in payload
        assert "path_length_m" in payload
        assert "original_length_m" in payload
        assert "resampled_points" in payload

        points = payload["resampled_points"]
        assert isinstance(points, list) and len(points) >= 2
        assert points[0] == [0.0, 0.0]
        assert points[-1] == [4.0, 0.0]

    def test_resample_preserves_length(self, tmp_path: Path) -> None:
        """Resampling a straight 4m line keeps total length == 4m (±0.01m)."""
        result = _run_resample(_line_fixture(), 0.3)
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert abs(payload["path_length_m"] - 4.0) < 0.01

    def test_resample_output_fixture_fixture(self, tmp_path: Path) -> None:
        """--out writes a valid JSON fixture and the count matches --json."""
        out_file = tmp_path / "resampled_line.json"
        result = _run_resample(_line_fixture(), 0.5, out=out_file)
        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert out_file.exists()
        fixture = json.loads(out_file.read_text(encoding="utf-8"))
        assert "points" in fixture and "step_m" in fixture and "source" in fixture
        assert len(fixture["points"]) == payload["points"]

    def test_resample_zigzag_fixture(self, tmp_path: Path) -> None:
        """Resample a non-trivial multi-segment fixture end-to-end."""
        result = _run_resample(_zigzag_fixture(), 1.0)
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["points"] > 1
        assert payload["path_length_m"] > 0.0
