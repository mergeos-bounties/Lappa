#!/usr/bin/env bash
# Lappa ROS2 workspace helper: source distro, colcon build package, ros2 launch.
# Usage (inside container):
#   /ros2_ws.sh build [pkg...]
#   /ros2_ws.sh launch <pkg> [launch_file]
#   /ros2_ws.sh status
#   /ros2_ws.sh logs [line_count]
#   /ros2_ws.sh stop
#   /ros2_ws.sh twist <linear_x> <linear_y> <angular_z>
#   /ros2_ws.sh auto-map <on|off>
# ROS setup files probe optional variables, so nounset cannot stay enabled here.
set -eo pipefail

WS="${LAPPA_WS:-/ws}"
DISTRO="${ROS_DISTRO:-humble}"
if [ -f /ws/ros2_distro.txt ]; then
  DISTRO="$(tr -d '[:space:]' < /ws/ros2_distro.txt || true)"
  DISTRO="${DISTRO:-humble}"
fi

source_ros() {
  if [ -f "/opt/ros/${DISTRO}/setup.bash" ]; then
    # shellcheck disable=SC1090
    source "/opt/ros/${DISTRO}/setup.bash"
  else
    echo "[lappa] ERROR: ROS2 distro not found at /opt/ros/${DISTRO}" >&2
    ls /opt/ros 2>/dev/null || true
    exit 2
  fi
  if [ -f "${WS}/install/setup.bash" ]; then
    # shellcheck disable=SC1091
    source "${WS}/install/setup.bash"
  fi
  export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
}

stop_recorded_launch() {
  local launch_pid=""
  local launch_pgid=""
  if [ -f /tmp/lappa_ros2_launch.pid ]; then
    launch_pid="$(cat /tmp/lappa_ros2_launch.pid 2>/dev/null || true)"
  fi
  if [ -f /tmp/lappa_ros2_launch.pgid ]; then
    launch_pgid="$(cat /tmp/lappa_ros2_launch.pgid 2>/dev/null || true)"
  fi

  if [ -n "$launch_pgid" ] && kill -0 -- "-${launch_pgid}" 2>/dev/null; then
    kill -TERM -- "-${launch_pgid}" 2>/dev/null || true
    for _ in $(seq 1 20); do
      if ! kill -0 -- "-${launch_pgid}" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
    if kill -0 -- "-${launch_pgid}" 2>/dev/null; then
      kill -KILL -- "-${launch_pgid}" 2>/dev/null || true
    fi
  elif [ -n "$launch_pid" ] && kill -0 "$launch_pid" 2>/dev/null; then
    # Compatibility with images created before process-group tracking.
    kill "$launch_pid" 2>/dev/null || true
  fi

  rm -f \
    /tmp/lappa_ros2_launch.pid \
    /tmp/lappa_ros2_launch.pgid \
    /tmp/lappa_ros2_launch.demo
}

cmd_build() {
  source_ros
  mkdir -p "${WS}/src" "${WS}/build" "${WS}/install" "${WS}/log"
  cd "${WS}"
  if [ "$#" -eq 0 ]; then
    echo "[lappa] colcon build (all packages under /ws/src)"
    colcon build --symlink-install --event-handlers console_direct+
  else
    echo "[lappa] colcon build --packages-select $*"
    colcon build --symlink-install --packages-select "$@" --event-handlers console_direct+
  fi
  # shellcheck disable=SC1091
  source "${WS}/install/setup.bash"
  echo "[lappa] build ok; packages:"
  ros2 pkg list 2>/dev/null | head -40 || true
}

cmd_launch() {
  local pkg="${1:-}"
  local launch_file="${2:-sim.launch.py}"
  if [ -z "$pkg" ]; then
    echo "usage: $0 launch <package> [launch_file]" >&2
    exit 1
  fi
  source_ros
  # Ensure package is built as ament package
  if ! ros2 pkg prefix "$pkg" >/dev/null 2>&1; then
    echo "[lappa] package $pkg not installed; building"
    cmd_build "$pkg"
    source_ros
  fi
  if ! ros2 pkg prefix "$pkg" >/dev/null 2>&1; then
    echo "[lappa] ERROR: ros2 does not see package '$pkg' after colcon build" >&2
    echo "[lappa] /ws/src contents:" >&2
    ls -la "${WS}/src" >&2 || true
    exit 3
  fi
  stop_recorded_launch
  echo "[lappa] ros2 launch ${pkg} ${launch_file}  (ROS_DISTRO=${DISTRO})"
  nohup setsid ros2 launch "$pkg" "$launch_file" > /tmp/lappa_ros2_launch.log 2>&1 &
  echo $! > /tmp/lappa_ros2_launch.pid
  echo $! > /tmp/lappa_ros2_launch.pgid
  echo "$pkg" > /tmp/lappa_ros2_launch.demo
  sleep 2
  local launch_pid
  launch_pid="$(cat /tmp/lappa_ros2_launch.pid 2>/dev/null || true)"
  if [ -z "$launch_pid" ] || ! kill -0 -- "-${launch_pid}" 2>/dev/null; then
    echo "[lappa] ERROR: ros2 launch exited during startup" >&2
    tail -n 60 /tmp/lappa_ros2_launch.log 2>/dev/null || true
    exit 4
  fi
  echo "[lappa] launch pid=${launch_pid} state=running"
  echo "[lappa] nodes:"
  ros2 node list 2>/dev/null || true
  echo "[lappa] topics:"
  ros2 topic list 2>/dev/null || true
  tail -n 30 /tmp/lappa_ros2_launch.log 2>/dev/null || true
}

cmd_status() {
  source_ros
  echo "ROS_DISTRO=${DISTRO}"
  echo "which ros2=$(command -v ros2 || echo missing)"
  ros2 --version 2>/dev/null || true
  echo "--- pkgs (lappa demos) ---"
  ros2 pkg list 2>/dev/null | grep -E 'diff_drive|omni|tricycle|ackermann|simple_arm' || echo "(none built yet)"
  echo "--- nodes ---"
  ros2 node list 2>/dev/null || true
  echo "--- topics ---"
  ros2 topic list 2>/dev/null || true
  if [ -f /tmp/lappa_ros2_launch.pid ]; then
    local launch_pid
    local launch_pgid
    launch_pid="$(cat /tmp/lappa_ros2_launch.pid)"
    launch_pgid="$(cat /tmp/lappa_ros2_launch.pgid 2>/dev/null || true)"
    echo "launch_pid=${launch_pid}"
    if [ -n "$launch_pgid" ]; then
      echo "launch_pgid=${launch_pgid}"
    fi
    if [ -n "$launch_pgid" ] && kill -0 -- "-${launch_pgid}" 2>/dev/null; then
      echo "launch_state=running"
      echo "launch_demo=$(cat /tmp/lappa_ros2_launch.demo 2>/dev/null || true)"
    elif [ -z "$launch_pgid" ] && kill -0 "$launch_pid" 2>/dev/null; then
      echo "launch_state=running"
      echo "launch_demo=$(cat /tmp/lappa_ros2_launch.demo 2>/dev/null || true)"
    else
      echo "launch_state=stopped"
    fi
  else
    echo "launch_state=idle"
  fi
  if [ -f /tmp/lappa_ros2_launch.log ]; then
    echo "--- launch log (tail) ---"
    tail -n 20 /tmp/lappa_ros2_launch.log
  fi
}

cmd_logs() {
  local line_count="${1:-200}"
  if ! [[ "$line_count" =~ ^[0-9]+$ ]]; then
    echo "usage: $0 logs [line_count]" >&2
    return 2
  fi
  line_count=$(( line_count > 500 ? 500 : line_count ))
  if [ -f /tmp/lappa_ros2_launch.log ]; then
    tail -n "$line_count" /tmp/lappa_ros2_launch.log
  fi
}

cmd_stop() {
  stop_recorded_launch
  echo "[lappa] stopped ros2 launch processes"
}

cmd_twist() {
  local linear_x="${1:-0.0}"
  local linear_y="${2:-0.0}"
  local angular_z="${3:-0.0}"
  source_ros
  local message
  message="{linear: {x: ${linear_x}, y: ${linear_y}, z: 0.0}, angular: {x: 0.0, y: 0.0, z: ${angular_z}}}"
  timeout 10 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "$message"
}

cmd_auto_map() {
  local requested="${1:-off}"
  local enabled="false"
  case "${requested,,}" in
    on|true|1) enabled="true" ;;
    off|false|0) enabled="false" ;;
    *) echo "usage: $0 auto-map {on|off}" >&2; return 2 ;;
  esac
  source_ros
  timeout 10 ros2 topic pub --once /lappa/auto_explore std_msgs/msg/Bool "{data: ${enabled}}"
}

case "${1:-}" in
  build) shift; cmd_build "$@" ;;
  launch) shift; cmd_launch "$@" ;;
  status) cmd_status ;;
  logs) shift; cmd_logs "$@" ;;
  stop) cmd_stop ;;
  twist) shift; cmd_twist "$@" ;;
  auto-map) shift; cmd_auto_map "$@" ;;
  *)
    echo "usage: $0 {build|launch|status|logs|stop|twist|auto-map} ..." >&2
    exit 1
    ;;
esac
