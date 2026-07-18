"""Smoke test for robot_patrol_loop demo fixture."""

import os
import unittest


class TestPatrolLoop(unittest.TestCase):
    """Verify patrol loop fixture exists and has required structure."""

    def test_readme_exists(self):
        readme = os.path.join(os.path.dirname(__file__), "README.md")
        self.assertTrue(os.path.exists(readme))
        with open(readme) as f:
            content = f.read()
        self.assertIn("Patrol", content)
        self.assertIn("metrics", content.lower())

    def test_fixture_directory_structure(self):
        """Patrol loop fixture should have at minimum a README."""
        base = os.path.dirname(__file__)
        self.assertTrue(os.path.isdir(base))
        files = os.listdir(base)
        self.assertIn("README.md", files)


if __name__ == "__main__":
    unittest.main()
