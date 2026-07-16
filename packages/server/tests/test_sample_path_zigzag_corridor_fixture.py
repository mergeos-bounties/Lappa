"""Zigzag Corridor path fixture smoke."""

from __future__ import annotations

import json
import math
from pathlib import Path


def test_sample_path_zigzag_corridor() -> None:
    p = Path(__file__).parent / "fixtures" / "sample_path_zigzag_corridor.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    pts = data["points"]
    assert len(pts) >= 4
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    assert abs(length - float(data["path_length_m"])) < 1e-6
    net = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
    assert abs(net - float(data["expected_net_displacement_m"])) < 1e-3
