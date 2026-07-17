"""Qt launch-log panel smoke test."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from lappa import docker_bridge  # noqa: E402
from lappa.gui.main_window import MainWindow  # noqa: E402


def _docker_unavailable() -> dict:
    return {
        "available": False,
        "daemon": False,
        "compose_available": False,
        "image_present": None,
        "container_exists": None,
        "container_status": "not checked",
        "container_health": None,
        "running": False,
        "state": "not_installed",
        "message": "Docker is not installed.",
        "guidance": "Native simulation remains available.",
        "ready_for_start": False,
        "ready_for_launch": False,
        "session": {"mode": "idle", "running": False},
    }


def test_launch_log_panel_renders_redacted_native_event(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(docker_bridge, "status", _docker_unavailable)
    docker_bridge.clear_launch_logs()
    docker_bridge.record_native_log("token=do-not-display preview ready")

    window = MainWindow(show_welcome=False)
    window._apply_launch_logs(docker_bridge.launch_logs(poll_docker=False))
    rendered = window.launch_log.toPlainText()

    assert "[native/stdout]" in rendered
    assert "[REDACTED]" in rendered
    assert "do-not-display" not in rendered
    window.close()
    app.processEvents()
