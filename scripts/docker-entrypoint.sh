#!/bin/bash
set -e

# Source ROS2
source /opt/ros/humble/setup.bash

# Launch rosbridge websocket server in background
ros2 launch rosbridge_server rosbridge_websocket_launch.xml &
BRIDGE_PID=$!

# Launch Lappa bridge node
python3 /app/ros2_bridge.py &
LAPPA_PID=$!

echo "Lappa ROS2 Bridge ready on ws://localhost:9090"

# Wait for any process to exit
wait -n
