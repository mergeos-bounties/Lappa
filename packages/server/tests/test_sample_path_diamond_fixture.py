"""Diamond path fixture smoke."""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path


def test_sample_path_diamond() -> None:
    p = Path(__file__).parent / "fixtures" / "sample_path_diamond.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    pts = data["points"]
    assert len(pts) == 5
    length = 0.0
    for a, b in itertools.pairwise(pts):
        length += math.hypot(b[0] - a[0], b[1] - a[1])
    assert abs(length - float(data["path_length_m"])) < 1e-6
    # 4 * sqrt(8) = 4 * 2*sqrt(2) ≈ 11.3137
    assert abs(length - 8 * math.sqrt(2)) < 1e-5
    net = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
    assert abs(net - float(data["expected_net_displacement_m"])) < 1e-3
    assert data.get("closed") is True
