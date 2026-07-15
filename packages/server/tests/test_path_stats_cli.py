from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from lappa.cli import app


FIXTURES = Path(__file__).parent / "fixtures"


def test_path_stats_cli_reports_length_and_net_displacement() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["path", "stats", "--file", str(FIXTURES / "sample_path_square_loop.json")],
    )

    assert result.exit_code == 0
    assert "'points': 5" in result.output
    assert "'path_length_m': 20.0" in result.output
    assert "'net_displacement_m': 0.0" in result.output


def test_path_stats_cli_accepts_straight_line_fixture_without_length_field() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["path", "stats", "--file", str(FIXTURES / "sample_path_line.json")],
    )

    assert result.exit_code == 0
    assert "'points': 3" in result.output
    assert "'path_length_m': 4.0" in result.output
    assert "'net_displacement_m': 4.0" in result.output
