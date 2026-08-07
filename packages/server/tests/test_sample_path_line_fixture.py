"""Straight path fixture smoke."""

from __future__ import annotations

import json
import math
from pathlib import Path


def test_sample_path_line_displacement() -> None:
    p = Path(__file__).parent / "fixtures" / "sample_path_line.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    pts = data["points"]
    assert len(pts) >= 2
    x0, y0 = pts[0]
    x1, y1 = pts[-1]
    dist = math.hypot(x1 - x0, y1 - y0)
    assert abs(dist - float(data["expected_net_displacement_m"])) < 1e-6
