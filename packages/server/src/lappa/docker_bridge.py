"""Docker ROS2 bridge: container lifecycle + launch demo packages.

Native kinematics sim works offline. Docker is the path for real
``ros2 launch <pkg> sim.launch.py`` against mounted package sources so
IDE edits from the Qt package editor land in the container without
rebuilding the image every time.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from lappa.config import DEMOS_ROOT, DOCKER_DIR
from lappa.ros2_versions import dockerfile_for, get_selected

CONTAINER_NAME = "lappa-ros2"
DOCKER_INSTALL_URL = "https://docs.docker.com/desktop/setup/install/windows-install/"


class _LaunchState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.demo: str | None = None
        self.proc: subprocess.Popen | None = None
        self.started_at: float | None = None
        self.last_log: str = ""
        self.mode: str = "idle"  # idle | docker_runtime | docker_launch
        self.log_events: deque[dict[str, Any]] = deque(maxlen=2000)
        self.next_log_seq = 1
        self.docker_tail: list[str] = []


_STATE = _LaunchState()

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"authorization)\b(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_AUTHORIZATION_VALUE = re.compile(
    r"(?i)\bAuthorization(\s*[:=]\s*)(?:(?:Bearer|Basic)\s+)?[^\s,;]+"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)[^/\s:@]+:[^@\s/]+@")
_KNOWN_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[A-Z0-9]{16})\b"
)


def redact_log_text(text: str) -> str:
    """Remove common credentials before log text reaches an API or IDE widget."""
    clean = _AUTHORIZATION_VALUE.sub(r"Authorization\1[REDACTED]", str(text))
    clean = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", clean)
    clean = _BEARER_TOKEN.sub("Bearer [REDACTED]", clean)
    clean = _URL_CREDENTIALS.sub(r"\1[REDACTED]@", clean)
    return _KNOWN_TOKEN.sub("[REDACTED]", clean)


def _append_log(text: str, *, source: str, stream: str = "stdout") -> None:
    lines = str(text or "").splitlines()
    if not lines:
        return
    with _STATE.lock:
        for line in lines:
            event = {
                "seq": _STATE.next_log_seq,
                "time": time.time(),
                "source": source,
                "stream": stream,
                "text": redact_log_text(line),
            }
            _STATE.log_events.append(event)
            _STATE.next_log_seq += 1


def record_native_log(text: str, *, stream: str = "stdout") -> None:
    """Publish a native-simulation message to the shared IDE launch-log stream."""
    _append_log(text, source="native", stream=stream)


def clear_launch_logs() -> None:
    """Reset the in-memory stream. Primarily useful for a fresh IDE/test session."""
    with _STATE.lock:
        _STATE.log_events.clear()
        _STATE.next_log_seq = 1
        _STATE.docker_tail = []


def _ingest_docker_tail(text: str) -> None:
    """Append only the new suffix from a repeatedly-polled Docker log tail."""
    new_lines = [redact_log_text(line) for line in str(text or "").splitlines()]
    if not new_lines:
        return
    with _STATE.lock:
        previous = _STATE.docker_tail
        overlap = 0
        for size in range(min(len(previous), len(new_lines)), 0, -1):
            if previous[-size:] == new_lines[:size]:
                overlap = size
                break
        _STATE.docker_tail = new_lines[-250:]
        for line in new_lines[overlap:]:
            _append_log(line, source="docker", stream="stdout")


def launch_logs(
    after: int = 0,
    limit: int = 200,
    *,
    poll_docker: bool = True,
) -> dict[str, Any]:
    """Return redacted launch-log events after a cursor, optionally polling Docker."""
    after = max(0, int(after))
    limit = max(1, min(int(limit), 500))
    with _STATE.lock:
        should_poll = poll_docker and _STATE.mode == "docker_launch"
    if should_poll and docker_available():
        code, out, err = _exec_ros2_ws(["logs", "250"], timeout=10.0)
        if code == 0:
            _ingest_docker_tail(out)
        elif err:
            _append_log(err, source="docker", stream="stderr")
    with _STATE.lock:
        matching = [dict(event) for event in _STATE.log_events if event["seq"] > after]
        events = matching[:limit]
        cursor = events[-1]["seq"] if events else after
        earliest = _STATE.log_events[0]["seq"] if _STATE.log_events else None
    return {
        "events": events,
        "cursor": cursor,
        "has_more": len(matching) > len(events),
        "truncated": bool(earliest is not None and after and after < earliest - 1),
    }


def docker_available() -> bool:
    return shutil.which("docker") is not None


def docker_desktop_path() -> Path | None:
    """Return the Docker Desktop executable when installed on Windows."""
    candidates = [
        Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        / "Docker"
        / "Docker"
        / "Docker Desktop.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "Docker Desktop.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


def open_docker_desktop() -> dict[str, Any]:
    path = docker_desktop_path()
    if path is None:
        return {
            "ok": False,
            "error": "Docker Desktop was not found on this computer.",
            "install_url": DOCKER_INSTALL_URL,
        }
    try:
        subprocess.Popen([str(path)], close_fds=True)  # noqa: S603
    except OSError as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}
    return {
        "ok": True,
        "message": "Docker Desktop is starting. Refresh status when the engine is ready.",
        "path": str(path),
    }


def _run(
    args: list[str],
    timeout: float = 20.0,
    *,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=env,
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return 1, "", str(e)


def apply_ros2_dockerfile(distro: str | None = None) -> dict[str, Any]:
    """Write packages/docker/Dockerfile for the selected (or given) ROS2 distro."""
    selected = get_selected() if not distro else None
    code = distro or (selected["id"] if selected else "humble")
    text = dockerfile_for(code)
    path = DOCKER_DIR / "Dockerfile"
    path.write_text(text, encoding="utf-8")
    stamp = DOCKER_DIR / "ros2_distro.txt"
    stamp.write_text(code + "\n", encoding="utf-8")
    return {
        "ok": True,
        "distro": code,
        "dockerfile": str(path),
        "image_tag": f"lappa-ros2:{code}",
    }


def status() -> dict[str, Any]:
    """Return layered Docker readiness without hiding partial installation states."""
    selected = get_selected()
    distro = selected.get("id", "humble")
    image = f"lappa-ros2:{distro}"
    compose_file = DOCKER_DIR / "docker-compose.yml"
    desktop_path = docker_desktop_path()
    launch_hint = {
        "compose": str(compose_file),
        "suggested": [
            f"docker compose -f {compose_file} up --build -d",
            "lappa docker launch --demo diff_drive_2w",
            "# pipeline: source ROS -> colcon build -> ros2 launch <pkg> sim.launch.py",
            f"# inside: source /opt/ros/{distro}/setup.bash && /ros2_ws.sh status",
        ],
        "native_fallback": "lappa sim start --demo diff_drive_2w",
        "bridge": (
            "IDE packages/demos -> /ws/src; Docker loads ROS2, colcon-builds the "
            "ament package, then ros2 launch <pkg> sim.launch.py"
        ),
    }
    cli_path = shutil.which("docker")
    base: dict[str, Any] = {
        "available": bool(cli_path),
        "cli_path": cli_path,
        "cli_version": None,
        "compose_available": False,
        "compose_version": None,
        "daemon": False,
        "server_version": None,
        "context": None,
        "image_present": None,
        "container_exists": None,
        "container_status": "not checked",
        "container_health": None,
        "running": False,
        "compose_file": str(compose_file),
        "compose_file_exists": compose_file.is_file(),
        "docker_desktop_path": str(desktop_path) if desktop_path else None,
        "install_url": DOCKER_INSTALL_URL,
        "ros2_distro": distro,
        "image": image,
        "docker_base": selected.get("docker_image"),
        "launch": launch_hint,
    }

    def session_snapshot(
        *,
        container_running: bool = False,
        launch_running: bool = False,
        detected_demo: str | None = None,
    ) -> dict[str, Any]:
        with _STATE.lock:
            return {
                "mode": (
                    "docker_launch"
                    if launch_running
                    else "docker_runtime"
                    if container_running
                    else "idle"
                ),
                "demo": detected_demo or _STATE.demo,
                "started_at": _STATE.started_at,
                "running": launch_running,
                "last_log": _STATE.last_log[-1500:],
            }

    if not cli_path:
        return {
            **base,
            "state": "not_installed",
            "message": "Docker is not installed. Install Docker Desktop to run ROS2 containers.",
            "guidance": "Native simulation remains available without Docker.",
            "ready_for_start": False,
            "ready_for_launch": False,
            "session": session_snapshot(),
        }

    vcode, vout, _ = _run(["docker", "--version"], timeout=5.0)
    if vcode == 0:
        base["cli_version"] = vout.strip()
    compose_code, compose_out, _ = _run(
        ["docker", "compose", "version", "--short"], timeout=5.0
    )
    base["compose_available"] = compose_code == 0
    base["compose_version"] = compose_out.strip() if compose_code == 0 else None
    context_code, context_out, _ = _run(["docker", "context", "show"], timeout=5.0)
    base["context"] = context_out.strip() if context_code == 0 else None

    code, out, err = _run(
        ["docker", "info", "--format", "{{json .ServerVersion}}"], timeout=8.0
    )
    daemon = code == 0
    base["daemon"] = daemon
    if daemon:
        raw_server = out.strip()
        try:
            base["server_version"] = json.loads(raw_server)
        except json.JSONDecodeError:
            base["server_version"] = raw_server.strip('"') or None
    else:
        detail = (err or out or "Docker engine is not running.").strip()
        return {
            **base,
            "state": "engine_stopped",
            "message": "Docker CLI is installed, but the Docker Desktop engine is not running.",
            "guidance": (
                "Open Docker Desktop and wait for the engine to report Running, then refresh."
                if desktop_path
                else "Start the Docker engine, then refresh status."
            ),
            "detail": detail[-1200:],
            "ready_for_start": False,
            "ready_for_launch": False,
            "session": session_snapshot(),
        }

    image_code, image_out, _ = _run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"], timeout=8.0
    )
    image_present = image_code == 0 and bool(image_out.strip())
    container_code, container_out, _ = _run(
        ["docker", "inspect", CONTAINER_NAME, "--format", "{{json .State}}"], timeout=8.0
    )
    container_exists = container_code == 0
    container_state: dict[str, Any] = {}
    if container_exists:
        try:
            container_state = json.loads(container_out.strip())
        except json.JSONDecodeError:
            container_state = {}
    container_status = str(container_state.get("Status") or "not created")
    health = container_state.get("Health") or {}
    container_health = health.get("Status") if isinstance(health, dict) else None
    running = container_status == "running"
    detected_launch = False
    detected_demo: str | None = None
    if running:
        probe_code, probe_out, _ = _run(
            [
                "docker",
                "exec",
                CONTAINER_NAME,
                "bash",
                "-lc",
                "pid=$(cat /tmp/lappa_ros2_launch.pid 2>/dev/null || true); "
                "if [ -n \"$pid\" ] && kill -0 \"$pid\" 2>/dev/null; then "
                "printf 'running|%s|%s' \"$pid\" "
                "\"$(cat /tmp/lappa_ros2_launch.demo 2>/dev/null || true)\"; "
                "else printf 'idle||'; fi",
            ],
            timeout=8.0,
        )
        if probe_code == 0:
            launch_parts = probe_out.strip().split("|", 2)
            detected_launch = bool(launch_parts and launch_parts[0] == "running")
            if len(launch_parts) == 3 and launch_parts[2]:
                detected_demo = launch_parts[2]
    base.update(
        {
            "image_present": image_present,
            "container_exists": container_exists,
            "container_status": container_status,
            "container_health": container_health,
            "running": running,
        }
    )
    if running and container_health == "unhealthy":
        state = "container_unhealthy"
        message = "The Lappa ROS2 container is running, but its healthcheck is failing."
        guidance = "Restart the runtime and inspect the diagnostic log before launching ROS2."
    elif running and container_health == "starting":
        state = "container_starting"
        message = "The Lappa ROS2 container is starting."
        guidance = "Wait for the healthcheck to become Healthy, then launch the package."
    elif running:
        state = "ready"
        message = "Docker runtime is ready for ROS2 launch."
        guidance = "Launch the active bundled package or inspect the current ROS2 session."
    elif image_present:
        state = "container_stopped"
        message = "The Lappa ROS2 image is built, but its container is stopped."
        guidance = "Start the runtime, then launch the active package."
    else:
        state = "image_missing"
        message = "Docker is ready. The Lappa ROS2 image has not been built yet."
        guidance = "Start the runtime once to build the selected ROS2 image."
    return {
        **base,
        "state": state,
        "message": message,
        "guidance": guidance,
        "ready_for_start": bool(base["compose_available"] and base["compose_file_exists"]),
        "ready_for_launch": running
        and container_health not in {"starting", "unhealthy"},
        "session": session_snapshot(
            container_running=running,
            launch_running=detected_launch,
            detected_demo=detected_demo,
        ),
    }


def start_runtime(workspace: Path | None = None) -> dict[str, Any]:
    _append_log("Starting Docker ROS2 runtime", source="docker")
    st = status()
    if not st["available"]:
        return {"ok": False, **st}
    if not st["daemon"]:
        return {"ok": False, "error": "Docker daemon not running", **st}
    if not st.get("compose_available"):
        return {
            "ok": False,
            "error": "Docker Compose is not available. Update Docker Desktop and try again.",
            **st,
        }
    applied = apply_ros2_dockerfile()
    compose = DOCKER_DIR / "docker-compose.yml"
    if not compose.is_file():
        return {"ok": False, "error": f"missing {compose}"}
    compose_env = os.environ.copy()
    compose_env["LAPPA_ROS2_IMAGE"] = applied["image_tag"]
    compose_env["LAPPA_ROS_DISTRO"] = applied["distro"]
    code, out, err = _run(
        ["docker", "compose", "-f", str(compose), "up", "-d", "--build"],
        timeout=600.0,
        env=compose_env,
    )
    _append_log(out, source="docker")
    _append_log(err, source="docker", stream="stderr")
    with _STATE.lock:
        if code == 0:
            _STATE.mode = "docker_runtime"
    return {
        "ok": code == 0,
        "code": code,
        "stdout": out[-2000:],
        "stderr": err[-2000:],
        "dockerfile": applied,
        "status": status(),
        "mount": "packages/demos -> /ws/src (live IDE edits)",
    }


def stop_runtime() -> dict[str, Any]:
    _append_log("Stopping Docker ROS2 runtime", source="docker")
    stop_launch()
    compose = DOCKER_DIR / "docker-compose.yml"
    if not compose.is_file():
        return {"ok": False, "error": "missing compose"}
    code, out, err = _run(
        ["docker", "compose", "-f", str(compose), "down"], timeout=60.0
    )
    with _STATE.lock:
        _STATE.mode = "idle"
        _STATE.demo = None
    return {
        "ok": code == 0,
        "stdout": out[-1000:],
        "stderr": err[-1000:],
        "status": status(),
    }


def _ensure_container() -> dict[str, Any]:
    st = status()
    if st.get("running") and st.get("container_health") != "unhealthy":
        return {"ok": True, "status": st}
    if st.get("running"):
        return {
            "ok": False,
            "error": "Docker container is unhealthy. Rebuild the runtime before launching ROS2.",
            "status": st,
        }
    return start_runtime()


def _resolve_launch(demo: str) -> tuple[str, str] | None:
    """Return (package_name, launch_file_basename) for a demo package."""
    root = DEMOS_ROOT / demo
    if not root.is_dir():
        return None
    launch_dir = root / "launch"
    if not launch_dir.is_dir():
        return None
    for name in ("sim.launch.py", "sim.launch.xml", "bringup.launch.py"):
        if (launch_dir / name).is_file():
            # ament package name usually matches folder
            pkg = demo
            xml = root / "package.xml"
            if xml.is_file():
                try:
                    import xml.etree.ElementTree as ET

                    n = ET.parse(xml).getroot().findtext("name")
                    if n:
                        pkg = n.strip()
                except Exception:  # noqa: BLE001
                    pass
            return pkg, name
    # any launch file
    for p in sorted(launch_dir.glob("*.launch.py")):
        return demo, p.name
    return None


def _exec_ros2_ws(args: list[str], timeout: float = 300.0) -> tuple[int, str, str]:
    """Run /ros2_ws.sh inside the container (ROS loaded + colcon tools)."""
    return _run(
        ["docker", "exec", CONTAINER_NAME, "/ros2_ws.sh", *args],
        timeout=timeout,
    )


def build_package(demo: str | None = None) -> dict[str, Any]:
    """``colcon build`` one or all packages under /ws/src (needs container up)."""
    st = status()
    if not st.get("running"):
        up = start_runtime()
        if not up.get("ok") and not status().get("running"):
            return {
                "ok": False,
                "error": "container not running; run lappa docker start first",
                "detail": up,
            }
    args = ["build"]
    if demo:
        resolved = _resolve_launch(demo)
        pkg = resolved[0] if resolved else demo
        args.append(pkg)
    code, out, err = _exec_ros2_ws(args, timeout=600.0)
    return {
        "ok": code == 0,
        "code": code,
        "stdout": out[-4000:],
        "stderr": err[-2000:],
        "message": "colcon build finished" if code == 0 else "colcon build failed",
    }


def launch_demo(demo: str, *, ensure_up: bool = True, rebuild: bool = True) -> dict[str, Any]:
    """Load ROS2 in Docker, colcon-build the ament package, then ``ros2 launch <pkg>``.

    Pipeline (what the user expects)::

        /opt/ros/$DISTRO  ->  colcon build --packages-select <pkg>
                          ->  source /ws/install/setup.bash
                          ->  ros2 launch <pkg> sim.launch.py

    IDE edits under packages/demos are the same sources at /ws/src.
    """
    demo = (demo or "").strip()
    if not demo:
        return {"ok": False, "error": "demo name required"}
    if not (DEMOS_ROOT / demo).is_dir():
        return {"ok": False, "error": f"unknown demo package: {demo}"}

    resolved = _resolve_launch(demo)
    if not resolved:
        return {
            "ok": False,
            "error": f"no launch file under packages/demos/{demo}/launch",
            "native_fallback": f"lappa sim start --demo {demo}",
        }
    pkg, launch_file = resolved
    selected = get_selected()
    distro = selected.get("id", "humble")
    _append_log(
        f"Preparing ros2 launch {pkg} {launch_file} (ROS_DISTRO={distro})",
        source="docker",
    )

    if ensure_up:
        up = _ensure_container()
        if not up.get("ok"):
            return {
                "ok": False,
                "error": up.get("error") or up.get("message") or "container not up",
                "native_fallback": f"lappa sim start --demo {demo}",
                "detail": up,
            }

    stop_launch()

    # Real ROS2 package path: build then ros2 launch <package> <file>
    if rebuild:
        _append_log(f"colcon build --packages-select {pkg}", source="docker")
        bcode, bout, berr = _exec_ros2_ws(["build", pkg], timeout=600.0)
        build_log = (bout + "\n" + berr).strip()
        _append_log(bout, source="docker")
        _append_log(berr, source="docker", stream="stderr")
        if bcode != 0:
            with _STATE.lock:
                _STATE.last_log = build_log[-2000:]
            return {
                "ok": False,
                "demo": demo,
                "package": pkg,
                "ros2_distro": distro,
                "stage": "colcon_build",
                "code": bcode,
                "stdout": bout[-3000:],
                "stderr": berr[-2000:],
                "message": (
                    f"colcon build failed for {pkg}; image must include ROS2+colcon "
                    "(rebuild: lappa docker start after distro change)"
                ),
                "native_fallback": f"lappa sim start --demo {demo}",
                "status": status(),
            }
    else:
        build_log = "rebuild skipped"

    lcode, lout, lerr = _exec_ros2_ws(["launch", pkg, launch_file], timeout=120.0)
    log = (lout + "\n" + lerr).strip()
    _append_log(lout, source="docker")
    _append_log(lerr, source="docker", stream="stderr")
    # Confirm ROS sees the package / nodes
    scode, sout, serr = _exec_ros2_ws(["status"], timeout=40.0)
    ros_status = (sout + "\n" + serr).strip()

    ok = lcode == 0 and (
        f"{pkg}" in ros_status
        or "teleop" in ros_status
        or "/odom" in ros_status
        or "/joint" in ros_status
        or "launch_state=running" in ros_status
    )
    with _STATE.lock:
        _STATE.demo = demo if ok else None
        _STATE.started_at = time.time() if ok else None
        _STATE.last_log = (build_log[-800:] + "\n" + log)[-2500:]
        if ok:
            _STATE.mode = "docker_launch"

    return {
        "ok": ok,
        "demo": demo,
        "package": pkg,
        "launch_file": launch_file,
        "command": f"ros2 launch {pkg} {launch_file}",
        "pipeline": [
            f"source /opt/ros/{distro}/setup.bash",
            f"colcon build --packages-select {pkg}",
            "source /ws/install/setup.bash",
            f"ros2 launch {pkg} {launch_file}",
        ],
        "container": CONTAINER_NAME,
        "ros2_distro": distro,
        "code": lcode,
        "stdout": lout[-2500:],
        "stderr": lerr[-1500:],
        "ros2_status": ros_status[-2000:],
        "status_code": scode,
        "message": (
            f"ROS2 package '{pkg}' built and launched in Docker "
            f"(ros2 launch {pkg} {launch_file})"
            if ok
            else "ros2 launch failed; see stdout/stderr. Native sim remains available."
        ),
        "native_fallback": f"lappa sim start --demo {demo}",
        "status": status(),
    }


def stop_launch() -> dict[str, Any]:
    """Stop ros2 launch processes inside the container via /ros2_ws.sh stop."""
    _append_log("Stopping ROS2 launch", source="docker")
    with _STATE.lock:
        demo = _STATE.demo
        if _STATE.proc is not None and _STATE.proc.poll() is None:
            try:
                _STATE.proc.terminate()
            except OSError:
                pass
        _STATE.proc = None
        if _STATE.mode == "docker_launch":
            _STATE.mode = "docker_runtime"

    if not docker_available():
        return {"ok": True, "stopped": False, "reason": "no docker"}

    code, out, err = _exec_ros2_ws(["stop"], timeout=20.0)
    _append_log(out, source="docker")
    _append_log(err, source="docker", stream="stderr")
    with _STATE.lock:
        _STATE.last_log = (out + err).strip() or _STATE.last_log
        if _STATE.mode == "docker_launch":
            _STATE.mode = "docker_runtime"
    return {
        "ok": code == 0,
        "demo": demo,
        "code": code,
        "stdout": out[-500:],
        "stderr": err[-500:],
        "status": status(),
    }


def launch_status() -> dict[str, Any]:
    st = status()
    ros = {}
    if st.get("running"):
        code, out, err = _exec_ros2_ws(["status"], timeout=30.0)
        ros = {"code": code, "output": (out + err)[-2000:]}
    return {
        "session": st.get("session"),
        "container_running": st.get("running"),
        "available": st.get("available"),
        "daemon": st.get("daemon"),
        "ros2_distro": st.get("ros2_distro"),
        "ros2": ros,
    }


def publish_twist(
    linear_x: float = 0.0,
    linear_y: float = 0.0,
    angular_z: float = 0.0,
) -> dict[str, Any]:
    """Publish one geometry_msgs/Twist command to the active Docker launch."""
    st = status()
    session = st.get("session") or {}
    if not st.get("running") or not session.get("running"):
        return {
            "ok": False,
            "error": "No active ROS2 Docker launch is available for /cmd_vel.",
            "status": st,
        }
    values = (float(linear_x), float(linear_y), float(angular_z))
    args = ["twist", *(f"{value:.4f}" for value in values)]
    code, out, err = _exec_ros2_ws(args, timeout=15.0)
    return {
        "ok": code == 0,
        "code": code,
        "twist": {
            "linear_x": values[0],
            "linear_y": values[1],
            "angular_z": values[2],
        },
        "stdout": out[-800:],
        "stderr": err[-800:],
        "error": None if code == 0 else (err or out or "ROS2 /cmd_vel publish failed").strip(),
    }


def set_auto_explore(enabled: bool) -> dict[str, Any]:
    """Enable or stop autonomous mapping on the active ROS2 launch."""
    st = status()
    session = st.get("session") or {}
    if not st.get("running") or not session.get("running"):
        return {
            "ok": False,
            "control": "auto_explore",
            "enabled": bool(enabled),
            "error": "No active ROS2 Docker launch is available for auto mapping.",
            "status": st,
        }
    code, out, err = _exec_ros2_ws(
        ["auto-map", "on" if enabled else "off"],
        timeout=15.0,
    )
    return {
        "ok": code == 0,
        "code": code,
        "control": "auto_explore",
        "enabled": bool(enabled),
        "stdout": out[-800:],
        "stderr": err[-800:],
        "error": None
        if code == 0
        else (err or out or "ROS2 auto mapping control failed").strip(),
    }


def show_info() -> dict[str, Any]:
    selected = get_selected()
    return {
        "title": "Docker loads ROS2 -> colcon build package -> ros2 launch",
        "ros2_distro": selected,
        "steps": [
            "1. IDE opens packages/demos/<pkg> (same tree Docker mounts at /ws/src)",
            "2. lappa docker start: image has /opt/ros/$DISTRO + colcon",
            "3. lappa docker launch --demo <pkg> runs: colcon build + ros2 launch <pkg> sim.launch.py",
            "4. Nodes/topics are real ROS2 (/cmd_vel, /odom, /scan; SLAM adds /map)",
            "5. Offline fallback: lappa sim start --demo <pkg> (native kinematics)",
        ],
        "status": status(),
        "compose": json.dumps({"file": str(DOCKER_DIR / "docker-compose.yml")}),
    }
