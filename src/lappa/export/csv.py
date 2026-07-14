"""CSV export improvements for Lappa trajectories."""

import csv
from pathlib import Path

def export_trajectory_csv(trajectory, output_path):
    """Export trajectory with richer columns."""
    output = Path(output_path)
    
    with open(output, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'timestamp', 'x', 'y', 'z', 
            'velocity', 'acceleration', 'jerk',
            'rotation_x', 'rotation_y', 'rotation_z'
        ])
        
        # Data
        for point in trajectory:
            writer.writerow([
                point.get('timestamp', 0),
                point.get('x', 0),
                point.get('y', 0),
                point.get('z', 0),
                point.get('velocity', 0),
                point.get('acceleration', 0),
                point.get('jerk', 0),
                point.get('rx', 0),
                point.get('ry', 0),
                point.get('rz', 0)
            ])
    
    return output

def generate_sample_trajectory():
    """Generate sample trajectory for demos."""
    return [
        {'timestamp': 0, 'x': 0, 'y': 0, 'z': 0, 'velocity': 0, 'acceleration': 0, 'jerk': 0},
        {'timestamp': 1, 'x': 1, 'y': 0, 'z': 0, 'velocity': 1, 'acceleration': 1, 'jerk': 1},
        {'timestamp': 2, 'x': 3, 'y': 0, 'z': 0, 'velocity': 2, 'acceleration': 1, 'jerk': 0},
        {'timestamp': 3, 'x': 6, 'y': 0, 'z': 0, 'velocity': 3, 'acceleration': 1, 'jerk': 0},
    ]
