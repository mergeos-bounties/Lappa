# Lappa E2E Demo: Edit Teleop → Hot-Reload → Sim Moves

> **Issue #15** — [200 MRG] Record reproducible E2E on Windows with evidence.
>
> This guide walks through the full edit → hot-reload → simulation feedback loop
> on Lappa, covering both the **native kinematics sim** (no ROS2 required) and the
> **Docker ROS2 launch** path.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Path A: Native Sim (no Docker)](#path-a-native-sim-no-docker)
  - [A1. Install Lappa](#a1-install-lappa)
  - [A2. Start the Native Sim](#a2-start-the-native-sim)
  - [A3. Edit Teleop (Trigger Hot-Reload)](#a3-edit-teleop-trigger-hot-reload)
  - [A4. Observe Sim Moves](#a4-observe-sim-moves)
  - [A5. Verify Hot-Reload Detection](#a5-verify-hot-reload-detection)
- [Path B: Docker ROS2 Launch](#path-b-docker-ros2-launch)
  - [B1. Start Docker Runtime](#b1-start-docker-runtime)
  - [B2. Build & Launch in Docker](#b2-build--launch-in-docker)
  - [B3. Edit Sources (Mounted Live)](#b3-edit-sources-mounted-live)
  - [B4. Rebuild & Relaunch](#b4-rebuild--relaunch)
- [Path C: Full GUI (Qt IDE)](#path-c-full-gui-qt-ide)
- [Verification Script](#verification-script)
- [Expected Outputs & Evidence](#expected-outputs--evidence)
- [Troubleshooting](#troubleshooting)
- [Internal Architecture](#internal-architecture)

---

## Overview

Lappa's E2E workflow has three stages:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  ① EDIT      │ ──▶ │  ② HOT-RELOAD│ ──▶ │  ③ SIM MOVES │
│  teleop.py   │     │  file watch  │     │  /cmd_vel →  │
│  in IDE/CLI  │     │  auto-detect │     │  /odom /scan │
└──────────────┘     └──────────────┘     └──────────────┘
```

- **Teleop sources** live in `packages/demos/<name>/<name>/teleop.py`
- **Hot-reload** is a background thread (`SimSession.start_watch_unlocked`) that
  polls the package directory every 0.5 s for file changes
- **Sim engines** consume `/cmd_vel` commands and integrate pose (x, y, theta),
  publishing synthetic odometry and lidar scans

The same edit→reload→move loop works across **five robot types**:

| Demo ID | Kind | Wheels | Unique Feature |
| --- | --- | --- | --- |
| `diff_drive_2w` | diff | 2 | Baseline — simplest teleop |
| `omni_3w` | omni | 3 | Holonomic lateral motion |
| `tricycle_3w` | tricycle | 3 | Ackermann steering + SLAM bridge |
| `ackermann_4w` | ackermann | 4 | Car-like steering |
| `simple_arm` | arm | joints | Planar robotic arm |

This guide uses `diff_drive_2w` as the canonical example.

---

## Prerequisites

| Requirement | Minimum | Check |
| --- | --- | --- |
| Python | 3.11+ | `python --version` |
| Git | any | `git --version` |
| Docker Desktop | (optional, Path B) | `docker ps` |
| Disk space | ~500 MB | — |

---

## Path A: Native Sim (no Docker)

The native sim uses Lappa's built-in kinematics engines. **No ROS2 or Docker
installation is required.** Hot-reload works out of the box — the file watcher
starts automatically when `lappa sim start` is called.

### A1. Install Lappa

```powershell
# Windows (PowerShell)
cd packages\server
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[gui,dev]"

# Verify
lappa version
# → {"version": "0.4.31"}
```

### A2. Start the Native Sim

```bash
# Start diff_drive_2w sim (starts file watcher automatically)
lappa sim start --demo diff_drive_2w
```

**Expected output:**
```json
{
  "state": {
    "running": true,
    "message": "native sim running",
    "kind": "diff",
    "x": 0.0, "y": 0.0, "theta": 0.0
  },
  "hot_reload": true,
  "reload_count": 0,
  "logs": [
    "[HH:MM:SS] sim start demo=diff_drive_2w mode=native",
    "[HH:MM:SS] hot-reload watch started"
  ]
}
```

> **Key:** `"hot_reload": true` confirms the file watcher is active. The
> `reload_count` is 0 — no changes detected yet.

### A3. Edit Teleop (Trigger Hot-Reload)

Open `packages/demos/diff_drive_2w/diff_drive_2w/teleop.py` in any editor and
make a small change. For example, change the synthetic lidar wall distance:

```python
# BEFORE (line ~82):
base = 3.0 + 0.2 * math.sin(self.x + self.y)

# AFTER:
base = 5.0 + 0.2 * math.sin(self.x + self.y)  # push wall to 5m
```

Save the file (`Ctrl+S`).

### A4. Observe Sim Moves

While the sim is running, send velocity commands and observe the robot moving:

```bash
# Send a forward + rotate command
lappa sim cmd --lx 0.4 --az 0.3

# Check status (robot should be moving)
lappa sim status

# Let it run a few ticks, then check trajectory
lappa sim summary
```

**Expected output (after a few seconds):**
```json
{
  "demo": "diff_drive_2w",
  "kind": "diff",
  "running": true,
  "pose": {"x": 0.1523, "y": 0.0421, "theta": 0.0872},
  "n_joints": 0,
  "n_lidar": 36,
  "lidar_min": 4.98,
  "trajectory": {
    "points": 23,
    "distance_m": 0.1847,
    "duration_s": 0.92,
    "avg_speed_mps": 0.2008
  }
}
```

> **Note the `lidar_min` ~4.98** — this reflects the edit we made (wall moved
> from 3m to 5m). The hot-reload was detected and the sim is now using the
> updated value.

### A5. Verify Hot-Reload Detection

```bash
lappa sim status
```

Look for:
```json
{
  "hot_reload": true,
  "reload_count": 1,
  "last_reload_at": 1722...
}
```

The `reload_count` incremented and `last_reload_at` is populated — confirming
the file watcher detected the edit.

**Full log:**
```bash
lappa sim status | python -c "import sys,json; d=json.load(sys.stdin); [print(l) for l in d.get('logs',[])]"
```

Expected log entry:
```
[HH:MM:SS] hot-reload teleop.py
```

### Stop and Export

```bash
# Export trajectory as CSV
lappa sim trajectory --out trajectory_after_edit.csv

# Stop sim
lappa sim stop
```

---

## Path B: Docker ROS2 Launch

For real `ros2 launch` with rclpy nodes, use the Docker bridge. Source files
are **mounted live** into the container — edits on the host are immediately
visible to the ROS2 node on the next rebuild.

### B1. Start Docker Runtime

```powershell
# Ensure Docker Desktop is running
docker ps

# Start Lappa's ROS2 container
lappa docker start
```

**Expected output:**
```json
{
  "ok": true,
  "container": "lappa-ros2",
  "status": "running",
  "mounted": "/ws/src"
}
```

### B2. Build & Launch in Docker

```bash
# Build the demo package with colcon
lappa docker build --demo diff_drive_2w

# Launch with ros2 launch
lappa docker launch --demo diff_drive_2w
```

Under the hood, this runs:
```bash
docker exec lappa-ros2 bash -c "
  source /opt/ros/humble/setup.bash &&
  colcon build --packages-select diff_drive_2w &&
  source install/setup.bash &&
  ros2 launch diff_drive_2w sim.launch.py
"
```

The teleop node publishes `/odom` and `/scan`, subscribes to `/cmd_vel`.

### B3. Edit Sources (Mounted Live)

The demo package sources at `packages/demos/diff_drive_2w/` are mounted at
`/ws/src/diff_drive_2w/` inside the container. Any edit on the host is
immediately visible inside the container (bind mount).

Edit `teleop.py` to change the demo label or scan range count:

```python
# Change number of lidar rays (line ~77):
n = 72  # was 36 — double the angular resolution
```

### B4. Rebuild & Relaunch

```bash
# Stop current launch
lappa docker launch-stop

# Rebuild with edits
lappa docker build --demo diff_drive_2w

# Relaunch
lappa docker launch --demo diff_drive_2w
```

The ROS2 node now publishes 72-ray scans instead of 36.

**Verify with docker logs:**
```bash
docker logs lappa-ros2 --tail 20
```

Expected:
```
[diff_drive_2w] ROS2 node up · kind=diff · /cmd_vel → /odom /scan
```

---

## Path C: Full GUI (Qt IDE)

The full desktop experience ties everything together:

```powershell
cd packages\server
.\.venv\Scripts\activate
lappa-gui
```

### GUI Walkthrough

1. **Welcome Screen** — Choose "Open ROS Package" → navigate to
   `packages/demos/diff_drive_2w`
2. **Editor Pane** — Double-click `diff_drive_2w/teleop.py` in the Explorer
   tree. The source opens with syntax highlighting.
3. **Edit** — Change `base = 3.0` to `base = 5.0` on line 82. Save (`Ctrl+S`).
4. **Show Simulation** — Click the "Show Simulation" button in the activity
   rail. The right pane shows the RViz-style viewport.
5. **Teleop** — Use `W`/`S` for forward/back, `A`/`D` for rotate,
   `Space` for brake. The robot moves in real-time.
6. **Observe Hot-Reload** — The lidar circle jumps from 3m radius to 5m radius
   (the hot-reload applied the edit without restarting the sim).
7. **Docker Tab** — Switch to the ROS2/Docker tab, select a distro, and click
   "Launch Demo" to run the same package with real ROS2.

### Screenshots Guide

For evidence, capture these screens:

| # | What to capture | What it shows |
| --- | --- | --- |
| 1 | `lappa sim start` output | Hot-reload active, reload_count=0 |
| 2 | Editor with `teleop.py` open, line 82 changed | The edit being made |
| 3 | `lappa sim status` after edit | reload_count=1, hot-reload detected |
| 4 | `lappa sim summary` after commands | Robot pose changed, lidar_min=5.0 |
| 5 | `lappa sim trajectory --out` CSV | Trajectory data exported |
| 6 | GUI: editor pane + sim viewport | Full desktop experience |
| 7 | `docker logs lappa-ros2 --tail 10` | Docker ROS2 node output |

---

## Verification Script

Run the automated verification:

```bash
python scripts/verify_e2e_workflow.py
```

This script:
1. Checks Python 3.11+ is available
2. Verifies Lappa is installed (`lappa version`)
3. Lists available demos (`lappa list-demos`)
4. Starts a native sim session (`lappa sim start --demo diff_drive_2w`)
5. Makes a test edit to `teleop.py` (increases lidar wall distance)
6. Sends velocity commands (`lappa sim cmd`)
7. Waits for hot-reload detection
8. Checks status confirms `reload_count >= 1` and robot has moved
9. Exports trajectory CSV
10. Restores the original `teleop.py`
11. Prints a pass/fail summary

---

## Expected Outputs & Evidence

### Native Sim Evidence

```
✅ Hot-reload enabled:         hot_reload=true
✅ File change detected:        reload_count=1, last_reload_at=...
✅ Sim moves after cmd:         pose.x != 0.0 or pose.y != 0.0
✅ Lidar reflects edit:         lidar_min ~5.0 (was ~3.0)
✅ Trajectory exported:         trajectory_after_edit.csv
```

### Docker Evidence

```
✅ Docker daemon running:       docker ps
✅ Container started:            lappa-ros2 (running)
✅ Build succeeded:              colcon build --packages-select diff_drive_2w
✅ Launch active:                ROS2 node up · /cmd_vel → /odom /scan
✅ Edit visible in container:    n=72 rays (was 36)
✅ Relaunch with new code:       node restart with updated params
```

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: lappa` | Not installed | `pip install -e ".[gui,dev]"` from `packages/server/` |
| `hot_reload: false` in status | Sim not started via `sim start` | Use `lappa sim start --demo <name>` (not `lappa demo`) |
| `reload_count` stays 0 after edit | File watcher polling delay (0.5 s) | Wait 1-2 seconds, then check again |
| Docker `Cannot connect` | Docker Desktop not running | Start Docker Desktop, wait for engine |
| `colcon build` fails | Missing ROS2 deps in image | Run `lappa docker start` to rebuild image |
| `Port 8080 in use` | Another Lappa instance | Kill old process or change port |

---

## Internal Architecture

### Hot-Reload Mechanism

The hot-reload system lives in `packages/server/src/lappa/sim/session.py`:

```python
class SimSession:
    hot_reload = True          # enabled by default
    reload_count = 0           # increments on each detected change
    last_reload_at = None      # timestamp of last reload

    def start(self, ...):
        if self.hot_reload and self.package:
            self.start_watch_unlocked()  # spawns background thread

    def start_watch_unlocked(self):
        # Scans package directory every 0.5s
        # Compares mtime of each file
        # Calls notify_file_change(rel_path) on change
```

### Teleop→Sim Data Flow

```
Keyboard/GUI (WASD)  ──▶  /cmd_vel (Twist)  ──▶  SimEngine.step()
                                                      │
                           ┌──────────────────────────┘
                           ▼
                    integrate pose:
                    x += cos(θ)*vx*dt
                    y += sin(θ)*vx*dt
                    θ += wz*dt
                           │
                           ▼
                    publish state:
                    {x, y, theta, twist, lidar, joints}
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         /odom msg    /scan msg    trajectory CSV
```

### Docker Mount Architecture

```
Host: packages/demos/              Container: /ws/src/
├── diff_drive_2w/                 ├── diff_drive_2w/
│   ├── teleop.py  ◀── bind mount ──▶  │   ├── teleop.py
│   ├── snapshot.py                     │   ├── snapshot.py
│   └── launch/                         │   └── launch/
│       └── sim.launch.py               │       └── sim.launch.py
```

---

*Guide generated for Lappa issue #15 — E2E video: edit teleop → hot-reload → sim moves*
