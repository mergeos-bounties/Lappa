"""ROS2 topic graph model: mock graph from a package, live topics when Docker runs.

The GUI panel (:mod:`lappa.gui.topic_graph_widget`) renders the graph returned by
this module. Keeping graph construction / layout here makes it unit-testable
without needing a Qt display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TopicNode:
    """A ROS2 node instance or topic endpoint."""

    id: str
    label: str
    kind: str = "node"  # "node" | "topic"
    x: float = 0.0
    y: float = 0.0


@dataclass
class TopicEdge:
    """A directed relationship between two endpoints."""

    src: str
    dst: str
    label: str = ""


@dataclass
class TopicGraph:
    nodes: list[TopicNode] = field(default_factory=list)
    edges: list[TopicEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "kind": n.kind,
                    "x": n.x,
                    "y": n.y,
                }
                for n in self.nodes
            ],
            "edges": [
                {"src": e.src, "dst": e.dst, "label": e.label} for e in self.edges
            ],
        }

    def node(self, node_id: str) -> TopicNode | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None


# Canonical robot-navigation topics used by the bundled demo packages. The mock
# graph below mirrors the real ROS2 graph that ``ros2 launch`` produces for a
# differential-drive / mecanum robot (see demos/*/README.md).
_TOPIC_MSGS = {
    "/cmd_vel": "geometry_msgs/Twist",
    "/odom": "nav_msgs/Odometry",
    "/scan": "sensor_msgs/LaserScan",
    "/map": "nav_msgs/OccupancyGrid",
    "/tf": "tf2_msgs/TFMessage",
    "/tf_static": "tf2_msgs/TFMessage",
    "/diagnostics": "diagnostic_msgs/DiagnosticArray",
}

# (node_id, display label)
_NODES = [
    ("driver", "driver_node"),
    ("mux", "cmd_vel_mux"),
    ("odom", "odom_publisher"),
    ("scan", "scan_publisher"),
    ("slam", "slam_toolbox"),
    ("base", "robot_state_publisher"),
]

# (src_node, dst_node, topic_name) — who publishes a topic to whom
_EDGES = [
    ("mux", "driver", "/cmd_vel"),
    ("driver", "odom", "/odom"),
    ("scan", "slam", "/scan"),
    ("odom", "slam", "/odom"),
    ("slam", "base", "/map"),
    ("base", "driver", "/tf"),
    ("base", "base", "/tf_static"),
    ("driver", "mux", "/diagnostics"),
]


def _topic_endpoint_id(topic: str, role: str) -> str:
    return f"{topic.strip('/')}:{role}"


def build_mock_graph() -> TopicGraph:
    """Return a self-contained mock topic graph for a navigation package.

    Produces a bipartite layout: node endpoints on the left, topic endpoints on
    the right. Edges run node -> topic (publish) and topic -> node (subscribe).
    No IO is performed, so it renders even without Docker / ROS2.
    """
    graph = TopicGraph()

    # Left column: node endpoints.
    for index, (nid, label) in enumerate(_NODES):
        graph.nodes.append(
            TopicNode(id=nid, label=label, kind="node", x=0.0, y=float(index))
        )

    # Right column: one topic endpoint per message type.
    topic_index = len(_NODES)
    for rel_index, (topic, msg) in enumerate(_TOPIC_MSGS.items()):
        epid = _topic_endpoint_id(topic, "pub")
        graph.nodes.append(
            TopicNode(
                id=epid,
                label=f"/{topic.strip('/')}\n{msg}",
                kind="topic",
                x=1.0,
                y=float(topic_index + rel_index),
            )
        )

    # Edges: node -> topic endpoint (publish side).
    for _src, _dst, topic in _EDGES:
        tick = _topic_endpoint_id(topic, "pub")
        graph.edges.append(TopicEdge(src=_src, dst=tick, label=f"pub {topic}"))

    return graph