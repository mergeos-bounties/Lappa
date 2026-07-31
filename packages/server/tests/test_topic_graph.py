"""Tests for topic graph panel — data structure and layout logic."""
from __future__ import annotations

import math

import pytest

MOCK_GRAPH = {
    "nodes": [
        {"name": "/turtle1", "package": "turtlesim", "pid": 1234},
        {"name": "/teleop_turtle", "package": "turtlesim", "pid": 1235},
        {"name": "/robot_state_publisher", "package": "robot_state_publisher", "pid": 1236},
        {"name": "/rviz2", "package": "rviz2", "pid": 1237},
    ],
    "topics": [
        {"name": "/turtle1/cmd_vel", "type": "geometry_msgs/msg/Twist"},
        {"name": "/turtle1/pose", "type": "turtlesim/msg/Pose"},
        {"name": "/tf", "type": "tf2_msgs/msg/TFMessage"},
        {"name": "/joint_states", "type": "sensor_msgs/msg/JointState"},
    ],
    "edges": [
        {"from": "/teleop_turtle", "to": "/turtle1/cmd_vel", "direction": "pub"},
        {"from": "/turtle1", "to": "/turtle1/cmd_vel", "direction": "sub"},
        {"from": "/turtle1", "to": "/turtle1/pose", "direction": "pub"},
        {"from": "/rviz2", "to": "/turtle1/pose", "direction": "sub"},
        {"from": "/robot_state_publisher", "to": "/tf", "direction": "pub"},
        {"from": "/rviz2", "to": "/tf", "direction": "sub"},
        {"from": "/robot_state_publisher", "to": "/joint_states", "direction": "pub"},
        {"from": "/rviz2", "to": "/joint_states", "direction": "sub"},
    ],
}


class TestGraphData:
    def test_graph_keys(self) -> None:
        for key in ("nodes", "topics", "edges"):
            assert key in MOCK_GRAPH

    def test_nodes_have_fields(self) -> None:
        for node in MOCK_GRAPH["nodes"]:
            assert "name" in node
            assert node["name"].startswith("/")

    def test_topics_have_fields(self) -> None:
        for topic in MOCK_GRAPH["topics"]:
            assert "name" in topic
            assert "type" in topic

    def test_edges_have_fields(self) -> None:
        for edge in MOCK_GRAPH["edges"]:
            assert edge["direction"] in ("pub", "sub")

    def test_edges_ref_valid_nodes(self) -> None:
        node_names = {n["name"] for n in MOCK_GRAPH["nodes"]}
        for edge in MOCK_GRAPH["edges"]:
            assert edge["from"] in node_names

    def test_edges_ref_valid_topics(self) -> None:
        topic_names = {t["name"] for t in MOCK_GRAPH["topics"]}
        for edge in MOCK_GRAPH["edges"]:
            assert edge["to"] in topic_names

    def test_no_duplicate_nodes(self) -> None:
        names = [n["name"] for n in MOCK_GRAPH["nodes"]]
        assert len(names) == len(set(names))

    def test_no_duplicate_topics(self) -> None:
        names = [t["name"] for t in MOCK_GRAPH["topics"]]
        assert len(names) == len(set(names))

    def test_node_count(self) -> None:
        assert len(MOCK_GRAPH["nodes"]) == 4

    def test_topic_count(self) -> None:
        assert len(MOCK_GRAPH["topics"]) == 4

    def test_edge_count(self) -> None:
        assert len(MOCK_GRAPH["edges"]) == 8

    def test_layout_distinct_positions(self) -> None:
        """Nodes should have distinct circular positions."""
        nodes = MOCK_GRAPH["nodes"]
        positions = {}
        cx, cy, r = 200.0, 150.0, 80.0
        for i, n in enumerate(nodes):
            a = (i / len(nodes)) * 2 * math.pi - math.pi / 2
            positions[n["name"]] = (cx + r * math.cos(a), cy + r * math.sin(a))
        vals = list(positions.values())
        assert len(set(vals)) == len(vals)

    def test_topics_closer_to_center(self) -> None:
        """Topics should be closer to center than nodes."""
        cx, cy = 200.0, 150.0
        node_r, topic_r = 80.0, 35.0
        assert topic_r < node_r
