"""Tests for rich trajectory CSV export."""

import csv

from lappa.export.csv import (
    CSV_FIELDS,
    export_trajectory_csv,
    generate_sample_trajectory,
    trajectory_csv_text,
)


def test_export_csv(tmp_path):
    output = export_trajectory_csv(generate_sample_trajectory(), tmp_path / "trajectory.csv")

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))

    assert len(rows) == 5
    assert rows[0] == list(CSV_FIELDS)


def test_rich_csv_derives_motion_and_rotation_columns():
    text = trajectory_csv_text(
        [
            {"t": 0, "x": 0, "y": 0, "theta": 0, "linear_x": 0},
            {"t": 1, "x": 1, "y": 0, "theta": 0.5, "linear_x": 2},
        ]
    )
    rows = list(csv.DictReader(text.splitlines()))

    assert float(rows[1]["velocity"]) == 2.0
    assert float(rows[1]["acceleration"]) == 2.0
    assert float(rows[1]["jerk"]) == 2.0
    assert float(rows[1]["rotation_z"]) == 0.5
