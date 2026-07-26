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


def test_launch_log_split_panes_separate_docker_from_native_with_ansi_color(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(docker_bridge, "status", _docker_unavailable)
    monkeypatch.setattr(docker_bridge, "docker_available", lambda: True)
    monkeypatch.setattr(
        docker_bridge,
        "_exec_ros2_ws",
        lambda *args, **kwargs: (0, "\x1b[31m[ERROR]\x1b[0m disk full\n", ""),
    )
    docker_bridge.clear_launch_logs()
    with docker_bridge._STATE.lock:
        docker_bridge._STATE.mode = "docker_launch"
    docker_bridge.record_native_log("preview ready")

    window = MainWindow(show_welcome=False)
    window._apply_launch_logs(docker_bridge.launch_logs())

    docker_text = window.launch_log_docker.toPlainText()
    native_text = window.launch_log_native.toPlainText()

    # split: each pane only carries its own source's events.
    assert "[ERROR] disk full" in docker_text
    assert "preview ready" not in docker_text
    assert "preview ready" in native_text
    assert "[ERROR]" not in native_text

    # ANSI: the raw escape bytes never reach the widget...
    assert "\x1b[" not in docker_text

    # ...because they were converted into real color, not just stripped.
    block = window.launch_log_docker.document().findBlock(docker_text.index("[ERROR]"))
    colors = set()
    it = block.begin()
    while not it.atEnd():
        fragment = it.fragment()
        if fragment.isValid():
            colors.add(fragment.charFormat().foreground().color().name())
        it += 1
    assert "#f87171" in colors

    with docker_bridge._STATE.lock:
        docker_bridge._STATE.mode = "idle"
    window.close()
    app.processEvents()
