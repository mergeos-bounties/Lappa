# Windows Quickstart

**Lappa** is optimized for Windows-first workflows. This guide covers how to get up and running on Windows with Python, and optionally Docker Desktop for full ROS2 container support.

## 1. Prerequisites (Python only, no ROS2)

You do not need a host ROS2 installation to run the Lappa IDE or the built-in native simulator.

1. **Python**: Install [Python 3.10+](https://www.python.org/downloads/windows/).
2. **Git**: Install [Git for Windows](https://gitforwindows.org/).

Clone the repository and run the setup:

```powershell
git clone https://github.com/mergeos-bounties/Lappa.git
cd Lappa\packages\server
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

Start the IDE:

```powershell
lappa serve --port 8840
# Or use `lappa desktop` to automatically open your browser
```

Navigate to **http://127.0.0.1:8840** in your browser.

## 2. Docker Desktop (Optional ROS2 runtime)

If you want to run actual ROS2 nodes, use Docker Desktop to spin up a ROS2 container.

1. **Install Docker Desktop**: Download and install from [Docker's website](https://www.docker.com/products/docker-desktop/).
2. Ensure Docker Desktop is running in the background.

To start the Docker simulator:

```powershell
# From the root of the Lappa repository
docker compose -f packages\docker\docker-compose.yml up --build
```

Alternatively, from the Lappa IDE, navigate to **Docker → Start runtime**.

### Notes on Docker on Windows
- Ensure **WSL 2 based engine** is checked in Docker Desktop Settings for better performance.
- The active workspace is mounted automatically, allowing you to edit files on Windows while they run inside the Linux ROS2 container.

## 3. Ports
By default, the Lappa server runs on port **8840**. If this port is in use, specify another:
```powershell
lappa serve --port 8080
```

## Screenshots

Lappa provides a native Windows feel in the browser. See the [README](../README.md#screenshots) for visual examples of the IDE, including the 3D visualizer and Docker show mode panel.
