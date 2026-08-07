"""Sample path fixture for sim metrics docs."""

from __future__ import annotations

import json
from pathlib import Path


def test_sample_path_fixture_closed_loop() -> None:
    p = Path(__file__).parent / "fixtures" / "sample_path.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    pts = data["points"]
    assert len(pts) >= 2
    assert pts[0] == pts[-1], "fixture should be a closed loop"
    assert data.get("expected_net_displacement_m") == 0.0
