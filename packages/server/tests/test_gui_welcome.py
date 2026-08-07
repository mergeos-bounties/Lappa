"""Qt first-run welcome behavior."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from lappa.gui.main_window import WELCOME_SETTINGS_KEY, MainWindow


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


def test_welcome_is_shown_once_after_entering_workbench(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("lappa.gui.main_window.docker_bridge.status", _docker_unavailable)
    settings = QSettings(str(tmp_path / "lappa-test.ini"), QSettings.Format.IniFormat)
    settings.clear()

    first = MainWindow(settings=settings)
    assert first.page_stack.currentWidget() is first.welcome_page
    assert settings.value(WELCOME_SETTINGS_KEY, False) is False

    first._enter_workbench()
    assert first.page_stack.currentWidget() is first.workbench_page
    assert settings.value(WELCOME_SETTINGS_KEY, False, type=bool) is True
    first.close()

    second = MainWindow(settings=settings)
    assert second.page_stack.currentWidget() is second.workbench_page
    second.close()
    app.processEvents()
