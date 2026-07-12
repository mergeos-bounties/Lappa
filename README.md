# Lappa

**Lappa** is a **ROS2 package IDE** for Windows-first workflows: open a package, edit, **hot-reload**, and **simulate** without installing a full ROS2 desktop on the host.

| Layer | Role |
| --- | --- |
| **Lappa IDE** | Professional browser IDE (editor, explorer, sim, package, 3D models) |
| **Lappa Server** | Workspace API, multi-distro ROS2, packager, 3D mesh gen, sim, Docker |
| **Demos** | Ready ROS2-style packages: 2-wheel, 3-wheel omni, ackermann, arm base |
| **Docker runtime** | Optional ROS2 container (**Humble / Iron / Jazzy / Kilted / Rolling**) |

Org: [mergeos-bounties](https://github.com/mergeos-bounties) · MergeOS MRG bounties · Project `prj_0352`.

## Screenshots

Live capture from `lappa serve` (native sim, no host ROS2):

### IDE overview — robot demos

![Lappa IDE overview with demo list](docs/screenshots/ide-overview.png)

### Differential drive (2-wheel)

![Diff drive 2w sim with trail](docs/screenshots/sim-diff-drive.png)

### Omnidirectional 3-wheel

![Omni 3w holonomic sim](docs/screenshots/sim-omni-3w.png)

### Planar arm (2-DOF)

![Simple arm kinematics](docs/screenshots/sim-arm.png)

### Docker show mode panel

![Docker show mode status](docs/screenshots/docker-panel.png)

### Tricycle 3-wheel

![Tricycle steered base](docs/screenshots/sim-tricycle.png)

Re-capture locally:

```powershell
# terminal 1
cd packages/server
lappa serve --port 8840

# terminal 2
python scripts/capture_screenshots.py
```

## Why Lappa

- **No host ROS2 required** for demos — built-in kinematics sim streams pose / twist / laser to the IDE.
- **ROS2 version picker** — target Humble, Iron, Jazzy, Kilted, or Rolling; Dockerfiles rewrite for the distro.
- **Package bundler** — zip one or many ROS2 packages with `lappa_manifest.json` for colcon install.
- **3D model lab** — procedural OBJ meshes (chassis, wheel, arm link, lidar dome…) attach into `meshes/` + URDF.
- **Docker show mode** when Docker Desktop is available — mount the package, run nodes, hot-reload sources.
- **Hot reload** watches package files and restarts or patches the active sim session.
- **Professional IDE chrome** — activity bar, split panes, Monaco editor, dark theme, robot canvas.

## ROS2 versions

```powershell
lappa ros2 list
lappa ros2 set jazzy
lappa ros2 get
```

| Id | Image | Notes |
| --- | --- | --- |
| `humble` | `ros:humble-ros-base` | Default LTS (Ubuntu 22.04) |
| `iron` | `ros:iron-ros-base` | Legacy |
| `jazzy` | `ros:jazzy-ros-base` | LTS Ubuntu 24.04 |
| `kilted` | `ros:kilted-ros-base` | Interim |
| `rolling` | `ros:rolling-ros-base` | Bleeding edge |

In the IDE: **title bar → ROS2 dropdown**. Docker start regenerates `packages/docker/Dockerfile` for that distro.

## Package bundles

```powershell
lappa package list
lappa package bundle -p diff_drive_2w -p omni_3w --distro humble
lappa package bundles
```

Or IDE → **📦 Package** → select packages → **Create bundle zip**. Downloads under `.workspaces/bundles/`.

Zip layout:

```text
src/<pkg>/...
lappa_manifest.json
README_BUNDLE.md
```

## 3D models

```powershell
lappa model presets
lappa model create chassis --name my_base
lappa model attach diff_drive_2w my_base
lappa model list
```

Presets: `box`, `cylinder`, `sphere`, `wheel`, `chassis`, `arm_link`, `lidar_dome`.

IDE → **🧊 Models** → generate OBJ → **Attach to active package** (writes `meshes/*.obj` + patches `urdf/robot.urdf`). Include meshes when you **bundle** the package.

## Download binaries (Windows / Linux)

GitHub Releases ship standalone builds (no Python install):

| File | Platform |
| --- | --- |
| `lappa-windows-x64.exe` | Windows 10/11 |
| `lappa-linux-x64` | Linux x64 |

```powershell
# Windows — double-click or:
.\lappa-windows-x64.exe
# opens http://127.0.0.1:8840  (data in .\lappa_data\)
.\lappa-windows-x64.exe demo
```

```bash
chmod +x lappa-linux-x64
./lappa-linux-x64
./lappa-linux-x64 ros2 list
```

**Build locally:** see [docs/RELEASE.md](docs/RELEASE.md)

```powershell
# Windows
pwsh scripts\build_release.ps1
# → dist\release\lappa-windows-x64.exe
```

```bash
# Linux
bash scripts/build_release.sh
# → dist/release/lappa-linux-x64
```

Tag `v*` on GitHub → Actions builds both OS and attaches assets to the Release.

## Quick start (Windows, offline, from source)

*For a full Windows setup guide including Docker, see [docs/WINDOWS.md](docs/WINDOWS.md).*

```powershell
cd D:\ThanhTrucSolutions\Lappa\packages\server
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"

lappa demo
lappa serve --port 8840
# or: lappa desktop   # serve + open browser
```

Open **http://127.0.0.1:8840** — IDE loads with demo packages.

```powershell
# CLI
lappa demos list
lappa workspace open demos/diff_drive_2w
lappa sim start --demo diff_drive_2w
lappa sim status
lappa docker status
```

### CLI demo output (offline)

```text
demos: 5  (ackermann_4w, diff_drive_2w, omni_3w, simple_arm, tricycle_3w)
  ackermann_4w: x=0.1  theta≈0.04
  diff_drive_2w: x=0.1  theta≈0.05
  omni_3w: strafe y>0
  simple_arm: FK tip updates
  tricycle_3w: steered arc
docker available=true  daemon=false  (native sim still runs)
Lappa demo complete (offline native sim).
```

## Docker sim (optional)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```powershell
# From repo root
docker compose -f packages/docker/docker-compose.yml up --build
# or from IDE: Docker → Start runtime
```

The container mounts the active workspace and can run `ros2 launch` for demos. Without Docker, the **native sim** still runs fully offline.

## Demos

| Id | Robot | Notes |
| --- | --- | --- |
| `diff_drive_2w` | Differential 2-wheel | Classic mobile base + lidar rays |
| `omni_3w` | Holonomic 3-wheel | Strafe + rotate |
| `tricycle_3w` | Tricycle / 3-wheel | Steering geometry |
| `ackermann_4w` | Ackermann car-like | Steering angle + wheelbase |
| `simple_arm` | Planar 2-DOF arm | Joint angles (sim) |

Each demo is a ROS2-style package under `packages/demos/` (`package.xml`, `launch/`, `urdf/`, Python nodes).

## Layout

```
packages/
  server/     # Python CLI + FastAPI
  ide/        # Static professional IDE (served by server)
  demos/      # Sample ROS2 packages
  docker/     # ROS2 Humble runtime image + compose
docs/screenshots/
docs/BOUNTY.md
scripts/capture_screenshots.py
```

## MergeOS bounties

1. Star this repo + [mergeos](https://github.com/mergeos-bounties/mergeos)
2. Claim a `bounty` issue
3. Claim on MergeOS [issue #1](https://github.com/mergeos-bounties/mergeos/issues/1)
4. PR to **Lappa** `master` with tests / screenshots
5. Credit MRG 25 / 50 / 100 / 200

See [docs/BOUNTY.md](docs/BOUNTY.md).

## License

MIT
