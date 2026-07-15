import os

def test_figure_eight():
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'figure_eight.txt')
    assert os.path.exists(fixture_path), "Fixture not found"
    
    with open(fixture_path, 'r') as f:
        points = [line.strip() for line in f if line.strip()]
        
    assert len(points) == 9, "Expected 9 points to complete a figure 8"
    assert points[0] == "0.0, 0.0", "Start point must be origin"
    assert points[-1] == "0.0, 0.0", "End point must return to origin"
