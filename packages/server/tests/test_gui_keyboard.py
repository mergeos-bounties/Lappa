"""Qt keyboard teleop behavior."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtCore = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
QSettings = QtCore.QSettings
Qt = QtCore.Qt
QApplication = QtWidgets.QApplication
QPushButton = QtWidgets.QPushButton
QToolButton = QtWidgets.QToolButton

from lappa.config import DEMOS_ROOT  # noqa: E402
from lappa.gui.main_window import MainWindow, SimCanvas  # noqa: E402
from lappa.package_loader import load_package  # noqa: E402
from lappa.sim.session import SESSION  # noqa: E402


def _docker_unavailable() -> dict:
    return {
        "available": False,
        "daemon": False,
        "running": False,
        "state": "not_installed",
        "ready_for_start": False,
        "ready_for_launch": False,
        "session": {"mode": "idle", "running": False},
    }


def test_workbench_buttons_expose_tooltips_and_accessible_names(
    tmp_path, monkeypatch
):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("lappa.gui.main_window.docker_bridge.status", _docker_unavailable)
    settings = QSettings(str(tmp_path / "tooltips.ini"), QSettings.Format.IniFormat)
    window = MainWindow(show_welcome=False, settings=settings)

    push_buttons = [button for button in window.findChildren(QPushButton) if button.text()]
    tool_buttons = [
        button
        for button in window.findChildren(QToolButton)
        if not button.objectName().startswith("Scroll")
    ]

    assert push_buttons
    assert tool_buttons
    assert all(button.toolTip().strip() for button in push_buttons)
    assert all(button.accessibleName().strip() for button in push_buttons)
    assert all(button.toolTip().strip() for button in tool_buttons)
    assert all(button.accessibleName().strip() for button in tool_buttons)

    window.close()
    app.processEvents()


def test_command_palette_exposes_required_offline_actions(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("lappa.gui.main_window.docker_bridge.status", _docker_unavailable)
    settings = QSettings(str(tmp_path / "commands.ini"), QSettings.Format.IniFormat)
    window = MainWindow(show_welcome=False, settings=settings)

    palette_actions = window._command_palette_actions()
    assert {"Run Sim", "Stop", "Open Demo"}.issubset(palette_actions)
    assert any(label.startswith("Toggle Hot Reload") for label in palette_actions)
    assert any(action.shortcut().toString() == "Ctrl+Shift+P" for action in window.actions())

    original_hot_reload = SESSION.hot_reload
    window._toggle_hot_reload()
    assert SESSION.hot_reload is (not original_hot_reload)
    window._toggle_hot_reload()
    assert SESSION.hot_reload is original_hot_reload

    window.close()
    app.processEvents()


def test_keyboard_drives_native_tricycle_and_forwards_twist(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("lappa.gui.main_window.docker_bridge.status", _docker_unavailable)
    monkeypatch.setattr(
        "lappa.gui.main_window.workspace.active_package",
        lambda: load_package(DEMOS_ROOT / "tricycle_3w"),
    )
    settings = QSettings(str(tmp_path / "keyboard.ini"), QSettings.Format.IniFormat)
    window = MainWindow(show_welcome=False, settings=settings)

    assert "tricycle_3w" in window.demo_combo.currentText()
    assert window._editor_pkg is not None
    assert window._editor_pkg.name == "tricycle_3w"
    assert set(window.display_items) == {
        "grid",
        "robot",
        "laser",
        "map",
        "tf",
        "trail",
    }
    window._editor_pkg = None
    window._reload_workspace_packages(open_active=False)
    assert "tricycle_3w" in window.demo_combo.currentText()
    commands: list[tuple[float, float, float]] = []
    auto_map_commands: list[bool] = []
    window._queue_docker_twist = lambda x, y, z: commands.append((x, y, z))
    window._queue_docker_auto_map = auto_map_commands.append

    assert window._simulation_open is False
    assert window.sim_stack.currentWidget() is window.sim_placeholder
    window._drive_key_pressed(Qt.Key.Key_W.value)
    assert window._sim_running is False

    window._show_simulation()
    assert window._simulation_open is True
    assert window.sim_stack.currentWidget() is window.sim_content_page

    window._drive_key_pressed(Qt.Key.Key_W.value)
    window._drive_key_pressed(Qt.Key.Key_A.value)

    assert window._sim_running is True
    assert window.sl_lx.value() == 65
    assert window.sl_az.value() == 55
    assert commands[-1] == (0.65, 0.0, 0.55)
    assert window.drive_keycaps["forward"].property("active") is True
    assert window.drive_keycaps["left"].property("active") is True

    window._drive_key_released(Qt.Key.Key_W.value)
    window._drive_key_released(Qt.Key.Key_A.value)
    assert window.sl_lx.value() == 0
    assert window.sl_az.value() == 0
    assert commands[-1] == (0.0, 0.0, 0.0)

    window.auto_map_toggle.setChecked(True)
    window._tick_sim()
    assert window.auto_map_toggle.isChecked() is True
    assert window.sl_lx.value() > 0
    assert auto_map_commands == []
    assert "Native preview" in window.slam_status_label.text()

    window.canvas.state = {
        **window.canvas.state,
        "collision": True,
        "lidar": [2.0] * 180,
        "twist": {"linear_x": -0.2, "angular_z": 0.0},
    }
    recovery_speed, _recovery_steering = window._native_auto_map_command()
    assert recovery_speed > 0

    window.sim_stop()
    assert auto_map_commands[-1] is False
    window.close()
    app.processEvents()


def test_switching_package_closes_simulation_view(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("lappa.gui.main_window.docker_bridge.status", _docker_unavailable)
    settings = QSettings(str(tmp_path / "switch.ini"), QSettings.Format.IniFormat)
    window = MainWindow(show_welcome=False, settings=settings)
    window._show_simulation()

    current = window.demo_combo.currentIndex()
    target = next(
        index
        for index in range(window.demo_combo.count())
        if index != current
    )
    window.demo_combo.setCurrentIndex(target)

    assert window._simulation_open is False
    assert window._sim_running is False
    assert window.sim_stack.currentWidget() is window.sim_placeholder
    assert window.sim_placeholder_package.text() in window.demo_combo.currentText()
    window.close()
    app.processEvents()


def test_sim_canvas_applies_real_slam_toolbox_snapshot():
    app = QApplication.instance() or QApplication([])
    canvas = SimCanvas()
    canvas.set_slam_snapshot(
        {
            "source": "slam_toolbox",
            "map": {
                "width": 120,
                "height": 80,
                "resolution": 0.05,
                "origin": {"x": -3.0, "y": -2.0, "yaw": 0.0},
                "known_cells": 2,
                "cells": [[10, 11, 0], [12, 13, 100]],
            },
            "pose": {"x": 1.25, "y": -0.5, "theta": 0.4},
            "twist": {"linear_x": 0.3, "angular_z": 0.1},
            "scan": [1.0, 2.0, 3.0],
        }
    )

    assert canvas.map_source == "slam_toolbox"
    assert canvas.map_resolution == 0.05
    assert canvas.map_origin == (-3.0, -2.0, 0.0)
    assert canvas.mapped_cells == {(10, 11): 0, (12, 13): 100}
    assert canvas.state["x"] == 1.25
    assert canvas.state["map_source"] == "slam_toolbox"
    canvas.close()
    app.processEvents()
