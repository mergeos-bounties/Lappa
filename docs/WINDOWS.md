# Windows Quickstart

## Prerequisites

1. Python 3.11+ installed
2. Docker Desktop (optional)

## Installation

```powershell
# Clone the repo
git clone https://github.com/mergeos-bounties/Lappa.git
cd Lappa

# Install dependencies
pip install -r requirements.txt
```

## Running

```powershell
# Without Docker
python -m lappa --port 8080

# With Docker
docker-compose up
```

## Ports

- **8080**: Main API
- **5432**: PostgreSQL (if using Docker)

## Common Issues

1. **Port already in use**: Change port in config
2. **Docker not starting**: Restart Docker Desktop
3. **Permission denied**: Run as Administrator

## Screenshots

![Windows Terminal](docs/screenshots/windows-terminal.png)
![Docker Desktop](docs/screenshots/docker-desktop.png)
