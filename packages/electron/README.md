# Lappa Desktop — Electron Shell

Electron desktop wrapper for the Lappa ROS2 robotics IDE. Bundles the FastAPI server and web IDE into a native desktop application.

## Windows Build Steps

### Prerequisites

1. **Python 3.11+** — [Download](https://www.python.org/downloads/)
   - Ensure `python` is on PATH
2. **Node.js 18+** — [Download](https://nodejs.org/)
3. **Git** — [Download](https://git-scm.com/download/win)

### Setup

```powershell
# Clone the repository
git clone https://github.com/mergeos-bounties/Lappa.git
cd Lappa

# Install Python dependencies
pip install -e packages/server[api,gui]

# Install Node dependencies
cd packages/electron
npm install
```

### Run (Development)

```powershell
# From packages/electron/
npm start
```

This launches the Lappa server on `http://127.0.0.1:8199` and opens the Electron window.

### Build Distribution

```powershell
# Windows NSIS installer
npm run dist:win

# Output: packages/electron/dist/Lappa IDE Setup X.X.X.exe
```

### Manual Verification

1. Install from the generated `.exe` installer
2. Launch "Lappa IDE" from Start Menu
3. The server starts automatically and the IDE window opens
4. Verify `/health` endpoint responds (the IDE sidebar shows package list)

### Troubleshooting

- **"Python not found"**: Ensure Python 3.11+ is installed and on PATH
- **Server fails to start**: Run `pip install -e packages/server[api,gui]` manually
- **Port 8199 in use**: Edit `SERVER_PORT` in `main.js`

---

Closes #14
