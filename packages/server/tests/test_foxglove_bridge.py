"""Tests for foxglove_bridge module."""

import pytest
from lappa.foxglove_bridge import (
    FoxgloveState,
    check_bridge,
    get_panel_config,
    get_offline_html,
    _STATE,
)


class TestFoxgloveState:
    def test_initial_state(self):
        state = FoxgloveState()
        assert state.connected is False
        assert state.bridge_url == "ws://localhost:9090"
        assert state.last_error == ""

    def test_snapshot(self):
        state = FoxgloveState()
        snap = state.snapshot()
        assert snap["connected"] is False
        assert "bridge_url" in snap
        assert "last_error" in snap


class TestFoxgloveBridge:
    def test_get_panel_config(self):
        config = get_panel_config()
        assert config["panel_id"] == "foxglove"
        assert "connection" in config
        assert "docker_running" in config
        assert "status" in config
        assert "connected" in config["status"]

    def test_get_panel_config_has_offline_reason(self):
        config = get_panel_config()
        if not config["status"]["connected"]:
            assert config["status"]["offline_reason"] in (
                "docker_down", "bridge_unreachable", ""
            )

    def test_get_offline_html(self):
        html = get_offline_html()
        assert "Foxglove Bridge Offline" in html
        assert "rosbridge" in html.lower()
        assert "lappa docker" in html.lower()
