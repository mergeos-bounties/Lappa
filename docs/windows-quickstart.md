# Windows Quickstart — Lappa

> Step-by-step guide to install and run **Lappa** on Windows 10 / 11.

---

## Prerequisites

| Requirement | Notes |
| --- | --- |
| **Windows 10** (22H2+) or **Windows 11** | x86-64 only; ARM via x64 emulation is experimental |
| **Python 3.11+** | Download from [python.org](https://www.python.org/downloads/) — check **"Add to PATH"** during install |
| **Git** (optional) | [git-scm.com](https://git-scm.com/) or use `winget install Git.Git` |
| **Docker Desktop** (optional) | Required only for real ROS2 container mode — see [Docker notes](#docker-desktop-notes) |

---

## Install from source

### 1. Clone or download

```powershell
git clone https://github.com/mergeos-bounties/Lappa.git
cd Lappa
```

> No Git? Download the [latest ZIP](https://github.com/mergeos-bounties/Lappa/archive/refs/heads/main.zip) and extract.

### 2. Create a virtual environment

```powershell
cd packages\server
python -m venv .venv
.\.venv\Scripts\activate
```

### 3. Install Lappa

```powershell
pip install -e ".[dev,api,gui]"
```

### 4. Verify

```powershell
lappa version
```

You should see version output (e.g. `0.4.0`).

---

## Run

### Browser IDE (recommended)

```powershell
lappa serve --port 8840
```

Open **http://127.0.0.1:8840** in your browser. Load a demo from the explorer and press **▶ Run Sim**.

### Desktop GUI (native Qt)

```powershell
lappa-gui
```

### Offline smoke test

```powershell
lappa demo
```

---

## Docker Desktop notes

Docker is **optional** — the native kinematics sim works entirely offline without it. Use Docker only when you need real `ros2 launch` commands and full ROS2 distribution fidelity.

### Setup

1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. Launch Docker Desktop — **WSL 2 backend** is recommended
3. Verify:

   ```powershell
   docker --version
   docker compose version
   ```

### Start the ROS2 runtime

```powershell
# From repository root
docker compose -f packages/docker/docker-compose.yml up --build
```

Or use **Lappa IDE → Docker → Start runtime**.

### Notes

- Docker Desktop requires a restart after first install.
- Containers use the **host network** mode — the IDE at `localhost:8840` communicates directly.
- If you see **"Docker Desktop requires a newer WSL kernel"**, run `wsl --update` from an admin PowerShell.
- On resource-constrained machines, increase Docker Desktop memory to at least **4 GB** (Settings → Resources → Advanced).

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `python` not found | Re-run Python installer — check **"Add to PATH"** |
| `pip` fails with long-path error | Open PowerShell as Admin: `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force` |
| `lappa` command not found | Ensure `.venv\Scripts` is active — run `.\.venv\Scripts\activate` |
| Docker compose not found | Docker Desktop may still be starting; wait and retry |
| Port 8840 in use | `lappa serve --port 8841` |

---

## See also

- [README](../README.md) — full project overview
- [CLI reference](../README.md#cli-reference)
- [Docker setup](../README.md#docker-optional)
- [Roadmap](ROADMAP.md)
