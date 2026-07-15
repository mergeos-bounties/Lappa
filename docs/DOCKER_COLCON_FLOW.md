# IDE Open Package → Docker Colcon Flow

This guide walks through the end-to-end path for editing, building, and launching a ROS2 package inside Lappa's Docker-based workflow.

## Overview

Lappa provides a **Docker colcon build** pipeline that lets you:

1. Open a ROS2 package in the IDE
2. Edit source files with syntax highlighting
3. Build inside a Docker container (no local ROS2 install required)
4. Launch and test the package

## Prerequisites

- **Docker Desktop** or **Docker Engine** running
- **Lappa** installed (`pip install lappa` or build from source)
- Internet connection (for first-time Docker image pull)

## Step 1: Open a package

```bash
# From Lappa IDE menu: File → Open Package
# Or via CLI:
lappa open ~/my_ros2_ws/src/my_package
```

Lappa detects the package type by reading `package.xml` and `CMakeLists.txt` (or `setup.py`).

## Step 2: Edit source files

The IDE provides:

- **Syntax highlighting** for C++, Python, XML, and launch files
- **IntelliSense** for ROS2 message types (via `rosidl` introspection)
- **File tree** showing `src/`, `launch/`, `config/`, `test/` directories

Common files you'll edit:

| File | Purpose |
| --- | --- |
| `src/my_node.cpp` | Main node source |
| `launch/my_launch.py` | Launch file |
| `config/params.yaml` | Runtime parameters |
| `package.xml` | Dependencies |
| `CMakeLists.txt` | Build configuration |

## Step 3: Build with Docker colcon

Lappa uses a Docker container with ROS2 pre-installed. The build command:

```bash
# Via Lappa IDE: Build → Build Package (Docker)
# Or via CLI:
lappa build --docker
```

Under the hood, Lappa runs:

```bash
docker run --rm \
  -v ~/my_ros2_ws:/ros2_ws \
  -w /ros2_ws \
  ros:humble \
  bash -c "colcon build --packages-select my_package"
```

### Build options

```bash
# Build with specific ROS distro
lappa build --docker --distro jazzy

# Build and run tests
lappa build --docker --test

# Clean build
lappa build --docker --clean

# Build in release mode
lappa build --docker --cmake-args -DCMAKE_BUILD_TYPE=Release
```

## Step 4: Launch the package

```bash
# Via Lappa IDE: Run → Launch Package
# Or via CLI:
lappa launch --docker my_package my_launch.py
```

This maps the built workspace into the container and runs:

```bash
docker run --rm -it \
  -v ~/my_ros2_ws/install:/ros2_ws/install \
  -v ~/my_ros2_ws/log:/ros2_ws/log \
  ros:humble \
  ros2 launch my_package my_launch.py
```

## Step 5: Debug and iterate

1. Edit source files in the IDE
2. Rebuild with `lappa build --docker`
3. Relaunch with `lappa launch --docker`
4. Check logs in the IDE's output panel or `~/my_ros2_ws/log/`

## Docker image management

```bash
# Pull the default ROS2 image
lappa docker pull

# List available distros
lappa docker distros

# Use a custom image
lappa build --docker --image my_registry/ros2:custom
```

## Troubleshooting

| Issue | Solution |
| --- | --- |
| Docker not running | Start Docker Desktop / `sudo systemctl start docker` |
| Image pull fails | Check internet connection; try `docker pull ros:humble` manually |
| Permission denied | Add user to docker group: `sudo usermod -aG docker $USER` |
| Build fails with missing deps | Add dependencies to `package.xml` and rebuild |
| Port conflict | Stop other ROS2 processes or use `--remap` args |

## File structure

```
my_ros2_ws/
├── src/
│   └── my_package/
│       ├── package.xml
│       ├── CMakeLists.txt
│       ├── src/
│       │   └── my_node.cpp
│       ├── launch/
│       │   └── my_launch.py
│       ├── config/
│       │   └── params.yaml
│       └── test/
│           └── test_my_node.py
├── build/
├── install/
└── log/
```
