"""Foxglove / rosbridge web panel stub.

Provides an optional panel connecting to rosbridge when Docker runtime is up.
Shows offline message with reconnect guidance when bridge is down.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import httpx

from lappa.docker_bridge import status as docker_status


class FoxgloveState:
    """Thread-safe state for the Foxglove rosbridge connection."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connected: bool = False
        self._bridge_url: str = "ws://localhost:9090"
        self._last_check: float = 0.0
        self._last_error: str = ""
        self._topics: list[dict[str, Any]] = []
        self._services: list[dict[str, Any]] = []
        self._parameters: list[dict[str, Any]] = []

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._connected

    @connected.setter
    def connected(self, value: bool) -> None:
        with self._lock:
            self._connected = value

    @property
    def bridge_url(self) -> str:
        with self._lock:
            return self._bridge_url

    @bridge_url.setter
    def bridge_url(self, value: str) -> None:
        with self._lock:
            self._bridge_url = value

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    @last_error.setter
    def last_error(self, value: str) -> None:
        with self._lock:
            self._last_error = value

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "connected": self._connected,
                "bridge_url": self._bridge_url,
                "last_error": self._last_error,
                "last_check": self._last_check,
                "topics_count": len(self._topics),
                "services_count": len(self._services),
            }


_STATE = FoxgloveState()

ROSBIRDGE_DEFAULT_PORT = 9090
ROSBIRDGE_DEFAULT_HOST = "localhost"


def check_bridge() -> dict[str, Any]:
    """Check rosbridge connectivity and return status."""
    docker = docker_status()
    docker_running = docker.get("running", False)
    bridge_url = _STATE.bridge_url

    result: dict[str, Any] = {
        "bridge_url": bridge_url,
        "docker_running": docker_running,
        "connected": False,
        "message": "",
        "topics": [],
    }

    if not docker_running:
        _STATE.connected = False
        _STATE.last_error = "Docker runtime is not running. Start the ROS2 runtime to enable Foxglove bridge."
        result["message"] = _STATE.last_error
        result["offline_reason"] = "docker_down"
        return result

    # Try to connect to rosbridge via HTTP API
    http_url = bridge_url.replace("ws://", "http://").replace("wss://", "https://")
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{http_url}/")
            if resp.status_code == 200:
                _STATE.connected = True
                _STATE.last_error = ""
                result["connected"] = True
                result["message"] = "Connected to rosbridge. Foxglove panel is live."
                return result
    except httpx.ConnectError:
        _STATE.connected = False
        _STATE.last_error = (
            f"Cannot reach rosbridge at {bridge_url}. "
            "Ensure rosbridge_server is running in the Docker container."
        )
    except Exception as exc:
        _STATE.connected = False
        _STATE.last_error = f"Rosbridge connection error: {exc}"

    _STATE._last_check = time.time()
    result["connected"] = _STATE.connected
    result["message"] = _STATE.last_error
    result["offline_reason"] = "bridge_unreachable"
    return result


def get_panel_config() -> dict[str, Any]:
    """Return the Foxglove panel configuration for the web IDE."""
    docker = docker_status()
    docker_running = docker.get("running", False)
    bridge_status = check_bridge() if docker_running else {"connected": False, "message": "Docker runtime is not running."}

    return {
        "panel_id": "foxglove",
        "title": "Foxglove Bridge",
        "icon": "satellite",
        "connection": {
            "type": "rosbridge",
            "url": _STATE.bridge_url,
            "connected": bridge_status.get("connected", False),
        },
        "docker_running": docker_running,
        "docker_status": {
            "state": docker.get("state", "unknown"),
            "container_status": docker.get("container_status", "unknown"),
            "ros2_distro": docker.get("ros2_distro", ""),
        },
        "status": {
            "connected": bridge_status.get("connected", False),
            "message": bridge_status.get("message", ""),
            "offline_reason": bridge_status.get("offline_reason", ""),
        },
    }


def get_offline_html() -> str:
    """Return HTML for the offline state shown in the Foxglove panel."""
    return """<div class="foxglove-offline">
  <div class="offline-icon">&#x1F6F0;</div>
  <h3>Foxglove Bridge Offline</h3>
  <p>The rosbridge connection is not available.</p>
  <div class="offline-steps">
    <p><strong>To enable the Foxglove panel:</strong></p>
    <ol>
      <li>Start the Docker ROS2 runtime: <code>lappa docker start</code></li>
      <li>Launch a demo: <code>lappa docker launch --demo diff_drive_2w</code></li>
      <li>Ensure rosbridge_server is running on port 9090</li>
    </ol>
  </div>
  <p class="offline-note">The native kinematics sim continues to work offline.</p>
</div>"""

