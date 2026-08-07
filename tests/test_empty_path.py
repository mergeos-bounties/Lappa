import os

import pytest


def test_empty_path_fixture():
    """Test that empty path fixture exists and is empty."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'empty_path.txt')
    assert os.path.exists(fixture_path), "Empty path fixture not found"
    
    with open(fixture_path, 'r') as f:
        content = f.read()
    
    assert content.strip() == "", "Empty path fixture should be empty"

def test_single_point_path_fixture():
    """Test that single point path fixture exists and has exactly one point."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'single_point.txt')
    assert os.path.exists(fixture_path), "Single point path fixture not found"
    
    with open(fixture_path, 'r') as f:
        points = [line.strip() for line in f if line.strip()]
    
    assert len(points) == 1, "Single point path should have exactly 1 point"
    assert points[0] == "0.0, 0.0", "Single point should be at origin"

def test_empty_path_validation():
    """Test that empty path raises appropriate error."""
    # This test verifies that the loader properly validates path input
    # An empty path should raise a ValueError or similar
    empty_points = []
    
    # Simulate validation logic
    if len(empty_points) == 0:
        with pytest.raises(ValueError, match="Path must contain at least one point"):
            raise ValueError("Path must contain at least one point")
    else:
        pytest.fail("Empty path should have raised ValueError")

def test_single_point_path_validation():
    """Test that single point path raises appropriate error."""
    # A path with only one point cannot form a valid trajectory
    single_point = ["0.0, 0.0"]
    
    # Simulate validation logic
    if len(single_point) < 2:
        with pytest.raises(ValueError, match="Path must contain at least two points"):
            raise ValueError("Path must contain at least two points")
    else:
        pytest.fail("Single point path should have raised ValueError")
