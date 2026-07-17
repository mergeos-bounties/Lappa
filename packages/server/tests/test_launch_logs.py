"""Cursor-based launch log streaming and secret redaction."""

from lappa import docker_bridge
from lappa.config import DOCKER_DIR


def setup_function():
    docker_bridge.clear_launch_logs()


def teardown_function():
    docker_bridge.clear_launch_logs()
    with docker_bridge._STATE.lock:
        docker_bridge._STATE.mode = "idle"


def test_native_log_cursor_returns_only_new_events():
    docker_bridge.record_native_log("preview started")
    first = docker_bridge.launch_logs(poll_docker=False)

    assert [event["text"] for event in first["events"]] == ["preview started"]
    assert first["cursor"] == 1

    docker_bridge.record_native_log("preview stopped")
    second = docker_bridge.launch_logs(after=first["cursor"], poll_docker=False)

    assert [event["text"] for event in second["events"]] == ["preview stopped"]
    assert second["events"][0]["source"] == "native"


def test_launch_logs_redact_common_credentials_before_delivery():
    docker_bridge.record_native_log(
        "token=super-secret password: hunter2 Authorization=BearerValue "
        "Authorization: Bearer spaced-secret Bearer abc.def.ghi "
        "https://alice:secret@example.test/path "
        "github_pat_abcdefghijklmnopqrstuvwxyz123456"
    )

    text = docker_bridge.launch_logs(poll_docker=False)["events"][0]["text"]

    assert "super-secret" not in text
    assert "hunter2" not in text
    assert "BearerValue" not in text
    assert "spaced-secret" not in text
    assert "abc.def.ghi" not in text
    assert "alice:secret" not in text
    assert "github_pat_" not in text
    assert text.count("[REDACTED]") >= 6


def test_docker_tail_polling_deduplicates_overlap(monkeypatch):
    samples = iter(
        [
            (0, "node ready\npublishing odom\n", ""),
            (0, "node ready\npublishing odom\nmap updated\n", ""),
        ]
    )
    monkeypatch.setattr(docker_bridge, "docker_available", lambda: True)
    monkeypatch.setattr(docker_bridge, "_exec_ros2_ws", lambda *args, **kwargs: next(samples))
    with docker_bridge._STATE.lock:
        docker_bridge._STATE.mode = "docker_launch"

    first = docker_bridge.launch_logs()
    second = docker_bridge.launch_logs(after=first["cursor"])

    assert [event["text"] for event in first["events"]] == [
        "node ready",
        "publishing odom",
    ]
    assert [event["text"] for event in second["events"]] == ["map updated"]


def test_ros2_helper_exposes_bounded_log_tail_command():
    helper = (DOCKER_DIR / "ros2_ws.sh").read_text(encoding="utf-8")

    assert "cmd_logs()" in helper
    assert 'tail -n "$line_count" /tmp/lappa_ros2_launch.log' in helper
    assert "logs) shift; cmd_logs" in helper
