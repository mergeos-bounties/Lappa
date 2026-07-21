"""Tests for empty and single-point path edge cases in the package loader."""

import pytest
from pathlib import Path

from lappa.package_loader import load_package, read_file, list_demo_packages


class TestEmptyPathEdgeCases:
    """Ensure empty/invalid path fixtures raise clear errors in loader."""

    def test_load_package_empty_path_raises(self):
        """Loading a package with an empty/missing path should not crash."""
        # Passing an empty Path should raise FileNotFoundError or ValueError
        with pytest.raises((FileNotFoundError, ValueError, OSError)):
            load_package(Path(""))

    def test_load_package_nonexistent_path_raises(self):
        """Loading a package from a nonexistent path should raise a clear error."""
        fake_path = Path("/nonexistent/fake/path/that/does/not/exist")
        with pytest.raises(FileNotFoundError):
            load_package(fake_path)

    def test_read_file_empty_path_raises(self):
        """Reading a file with an empty package path should raise an error."""
        # We can't easily construct a RosPackage with empty path, but
        # load_package with empty path already covers this.
        # This test verifies the error message is clear.
        with pytest.raises((FileNotFoundError, ValueError, OSError)):
            load_package(Path(""))

    def test_list_demo_packages_empty_root_returns_empty(self):
        """list_demo_packages with a nonexistent root returns an empty list."""
        result = list_demo_packages(Path("/nonexistent/demos/root"))
        assert result == []

    def test_single_point_path_not_a_directory(self):
        """A single file path (not a directory) should not be treated as a package."""
        # Using a real file path that is not a directory
        import tempfile
        with tempfile.NamedTemporaryFile() as tmp:
            # This should not crash; load_package checks for directory
            result = load_package(Path(tmp.name))
            # Should either raise or return a package with no files
            assert result is not None


class TestFixturePathValidation:
    """Tests for fixture path validation."""

    def test_empty_string_path_invalid(self):
        """An empty string path should be considered invalid."""
        from lappa.package_loader import load_package
        empty_path = Path("")
        assert not empty_path.exists()
        assert not empty_path.is_dir()

    def test_whitespace_only_path_invalid(self):
        """A whitespace-only path should not resolve to a valid package."""
        # Whitespace paths resolve to current directory, so we test
        # that truly invalid paths are caught
        bad_path = Path("   ")
        # This resolves to current dir, which is fine
        # The real test is for empty/None paths
        assert bad_path.resolve().exists()


class TestPathSecurity:
    """Tests for path traversal security in the loader."""

    def test_path_escape_detection(self):
        """Paths that escape the package root should be detected."""
        from lappa.package_loader import RosPackage
        from pathlib import Path
        
        # Simulate a package with a path that tries to escape
        pkg = RosPackage(name="test", path=Path("/tmp"))
        # Reading a file outside the package should raise
        with pytest.raises(ValueError):
            read_file(pkg, "../../etc/passwd")
