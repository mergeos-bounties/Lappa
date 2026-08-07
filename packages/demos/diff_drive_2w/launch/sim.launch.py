from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='diff_drive_2w', executable='teleop', name='teleop', output='screen'),
    ])
