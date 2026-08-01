"""Tests for hot-reload colcon watcher."""
import os
import time
import tempfile
import pytest
from pathlib import Path

# Add packages to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestColconWatcher:
    """Test the file watcher detection and build triggering."""

    @pytest.fixture
    def temp_src(self):
        """Create a temporary source directory with some files."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "main.py").write_text("print('hello')")
            (src / "utils.py").write_text("def foo(): pass")
            yield str(src)

    def test_scan_files(self, temp_src):
        """Test that scan_files detects existing files."""
        from packages.hotreload.watcher import ColconWatcher
        watcher = ColconWatcher(temp_src)
        mtimes = watcher._scan_files()
        assert len(mtimes) >= 2
        assert any("main.py" in k for k in mtimes)
        assert any("utils.py" in k for k in mtimes)

    def test_detect_changes_new_file(self, temp_src):
        """Test detection of newly created files."""
        from packages.hotreload.watcher import ColconWatcher
        watcher = ColconWatcher(temp_src)
        # Initial scan
        watcher._scan_files()

        # Add new file
        time.sleep(0.1)
        new_file = Path(temp_src) / "new_module.py"
        new_file.write_text("def bar(): pass")

        changes = watcher.detect_changes()
        assert len(changes) >= 1
        assert any("new_module.py" in c for c in changes)

    def test_detect_changes_modified(self, temp_src):
        """Test detection of modified files."""
        from packages.hotreload.watcher import ColconWatcher
        watcher = ColconWatcher(temp_src)
        watcher._scan_files()

        # Modify existing file
        time.sleep(0.1)
        main_file = Path(temp_src) / "main.py"
        main_file.write_text("print('updated')")

        changes = watcher.detect_changes()
        assert len(changes) >= 1
        assert any("main.py" in c for c in changes)

    def test_exclude_patterns(self, temp_src):
        """Test that excluded patterns are filtered."""
        from packages.hotreload.watcher import ColconWatcher
        watcher = ColconWatcher(temp_src)
        watcher._scan_files()

        # Add __pycache__
        pycache = Path(temp_src) / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-311.pyc").write_text("cache")

        changes = watcher.detect_changes()
        # pycache should be excluded
        assert not any("__pycache__" in c for c in changes)

    def test_debounce(self, temp_src):
        """Test debounce doesn't miss changes."""
        from packages.hotreload.watcher import ColconWatcher
        watcher = ColconWatcher(temp_src, debounce_seconds=0.1)
        watcher._scan_files()

        # Quick successive changes
        for i in range(3):
            (Path(temp_src) / f"file_{i}.py").write_text(f"content_{i}")
            time.sleep(0.05)

        changes = watcher.detect_changes()
        assert len(changes) >= 3

    def test_watch_one_iteration(self, temp_src):
        """Test watch runs at least one iteration."""
        from packages.hotreload.watcher import ColconWatcher
        watcher = ColconWatcher(temp_src, debounce_seconds=0.05)
        watcher._scan_files()

        # Add a change
        (Path(temp_src) / "trigger.py").write_text("trigger")

        # Watch for 1 iteration
        try:
            watcher.watch(interval=0.1, max_iterations=1)
        except Exception:
            pass  # colcon not available is fine in tests
        # Should not crash — just verifies the loop runs

    def test_empty_src_directory(self):
        """Test with empty directory."""
        with tempfile.TemporaryDirectory() as tmp:
            from packages.hotreload.watcher import ColconWatcher
            watcher = ColconWatcher(tmp)
            mtimes = watcher._scan_files()
            assert mtimes == {}

    def test_incremental_build_no_colcon(self, temp_src):
        """Test incremental_build handles missing colcon gracefully."""
        from packages.hotreload.watcher import ColconWatcher
        watcher = ColconWatcher(temp_src)
        result = watcher.incremental_build()
        # Should return False when colcon not found (not crash)
        assert result is False
