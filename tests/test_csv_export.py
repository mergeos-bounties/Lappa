"""Tests for CSV export."""

import csv
from pathlib import Path
from lappa.export.csv import export_trajectory_csv, generate_sample_trajectory

def test_export_csv(tmp_path):
    trajectory = generate_sample_trajectory()
    output = tmp_path / 'trajectory.csv'
    
    export_trajectory_csv(trajectory, output)
    
    with open(output) as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    assert len(rows) == 5  # header + 4 data rows
    assert rows[0] == ['timestamp', 'x', 'y', 'z', 'velocity', 'acceleration', 'jerk', 'rotation_x', 'rotation_y', 'rotation_z']
