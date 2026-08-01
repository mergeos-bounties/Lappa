#!/bin/bash
# Hot-reload launcher for Lappa in Docker
# Watches packages/ for changes and triggers incremental colcon build + node restart

set -e

SRC_DIR="${SRC_DIR:-/workspace}"
CONTAINER="${CONTAINER:-lappa-dev}"
PACKAGES="${PACKAGES:-}"

echo "=== Lappa Hot-Reload ==="
echo "src_dir: $SRC_DIR"
echo "container: $CONTAINER"
echo "packages: ${PACKAGES:-all}"

if [ -n "$PACKAGES" ]; then
    exec python3 -c "
from packages.hotreload.watcher import docker_watch
docker_watch('$SRC_DIR', '$CONTAINER', '$PACKAGES'.split(','))
"
else
    exec python3 -c "
from packages.hotreload.watcher import docker_watch
docker_watch('$SRC_DIR', '$CONTAINER')
"
fi
