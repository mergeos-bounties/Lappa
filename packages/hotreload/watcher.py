"""File watcher that triggers incremental colcon build on save."""
import os
import time
import subprocess
import logging
from pathlib import Path
from typing import Set, Optional, Callable

logger = logging.getLogger(__name__)


class ColconWatcher:
    """Watch source directories for changes and trigger incremental colcon builds."""

    def __init__(
        self,
        src_dir: str,
        build_dir: str = "build",
        install_dir: str = "install",
        debounce_seconds: float = 1.0,
        exclude_patterns: Optional[Set[str]] = None,
    ):
        self.src_dir = Path(src_dir)
        self.build_dir = Path(build_dir)
        self.install_dir = Path(install_dir)
        self.debounce_seconds = debounce_seconds
        self.exclude_patterns = exclude_patterns or {
            "__pycache__", ".git", "build", "install", "log",
            "*.pyc", "*.swp", "*.swo", ".DS_Store",
        }
        self._last_event_time: float = 0.0
        self._pending_build: bool = False
        self._file_mtimes: dict = {}
        self._on_reload: Optional[Callable] = None

    def set_on_reload(self, callback: Callable):
        """Set callback to run after successful incremental build."""
        self._on_reload = callback

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path matches any exclude pattern."""
        parts = set(path.parts)
        for pat in self.exclude_patterns:
            if pat.startswith("*."):
                if path.suffix == pat[1:]:
                    return True
            elif pat in parts:
                return True
            elif pat in str(path):
                return True
        return False

    def _scan_files(self) -> dict:
        """Scan source directory and return file mtimes."""
        mtimes = {}
        for root, dirs, files in os.walk(self.src_dir):
            # Filter excluded directories
            dirs[:] = [d for d in dirs if not self._should_exclude(Path(root) / d)]
            for f in files:
                fp = Path(root) / f
                if not self._should_exclude(fp):
                    try:
                        mtimes[str(fp)] = os.path.getmtime(fp)
                    except OSError:
                        pass
        return mtimes

    def detect_changes(self) -> Set[str]:
        """Detect changed files since last scan. Returns set of changed file paths."""
        current = self._scan_files()
        changed = set()

        # New or modified files
        for path, mtime in current.items():
            if path not in self._file_mtimes or mtime > self._file_mtimes[path]:
                changed.add(path)

        # Deleted files
        for path in self._file_mtimes:
            if path not in current:
                changed.add(path)

        self._file_mtimes = current
        return changed

    def incremental_build(self, packages: Optional[list] = None) -> bool:
        """Run incremental colcon build."""
        cmd = ["colcon", "build"]
        if packages:
            cmd.extend(["--packages-select"] + packages)
        cmd.extend([
            "--cmake-args", "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
            "--symlink-install",
            "--continue-on-error",
        ])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.src_dir,
            )
            logger.info("Build %s", "OK" if result.returncode == 0 else f"FAILED ({result.returncode})")
            if result.returncode != 0:
                logger.error("Build stderr: %s", result.stderr[-500:])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("Build timed out after 300s")
            return False
        except FileNotFoundError:
            logger.error("colcon not found in PATH")
            return False

    def restart_node(self, container_name: str = "lappa-dev") -> bool:
        """Restart the node inside Docker container."""
        try:
            _ = subprocess.run(
                ["docker", "exec", container_name, "pkill", "-f", "lappa"],
                capture_output=True, text=True, timeout=10,
            )
            # pkill returns 0 if signal sent, 1 if no process matched (ok either way)
            logger.info("Node restart signal sent to %s", container_name)
            return True
        except subprocess.TimeoutExpired:
            logger.error("Docker exec timed out")
            return False
        except FileNotFoundError:
            logger.error("docker not found in PATH")
            return False

    def watch(self, interval: float = 2.0, max_iterations: Optional[int] = None):
        """Watch continuously for file changes and trigger builds."""
        logger.info("Watching %s (interval=%.1fs)", self.src_dir, interval)
        iteration = 0

        while max_iterations is None or iteration < max_iterations:
            changed = self.detect_changes()
            if changed:
                logger.info("Detected %d changed file(s): %s",
                           len(changed),
                           ", ".join(list(changed)[:5]))
                success = self.incremental_build()
                if success:
                    if self._on_reload:
                        self._on_reload()
                    self.restart_node()
            time.sleep(interval)
            iteration += 1


def watch_colcon_build(
    src_dir: str,
    packages: Optional[list] = None,
    debounce: float = 1.0,
):
    """Convenience function: watch src_dir and rebuild on changes."""
    watcher = ColconWatcher(src_dir, debounce_seconds=debounce)

    if packages:
        watcher.incremental_build = lambda pkgs=packages: (
            ColconWatcher.incremental_build(watcher, pkgs)
        )

    watcher.watch()


# Docker compose integration
def docker_watch(
    src_dir: str,
    container_name: str = "lappa-dev",
    packages: Optional[list] = None,
):
    """Watch and rebuild inside Docker context."""
    watcher = ColconWatcher(src_dir)
    watcher.set_on_reload(lambda: watcher.restart_node(container_name))
    watcher.watch()
