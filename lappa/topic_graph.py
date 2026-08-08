"""
Topic graph panel for Lappa IDE.
Renders ROS2 topic/node graph as an interactive panel mock.
"""

import json
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class TopicNode:
    """A node in the ROS2 topic graph."""
    name: str
    node_type: str = "unknown"
    status: str = "active"  # active, inactive, error
    
    def __hash__(self):
        return hash(self.name)


@dataclass
class TopicEdge:
    """A connection between two graph entities."""
    source: str
    target: str
    topic: str
    direction: str = "pub"  # pub, sub, srv
    msg_type: str = "unknown"
    frequency_hz: float = 0.0


@dataclass
class TopicGraph:
    """Complete ROS2 topic graph representation."""
    nodes: Dict[str, TopicNode] = field(default_factory=dict)
    edges: List[TopicEdge] = field(default_factory=list)
    
    @classmethod
    def from_discovery(cls, nodes_json: str, topics_json: str) -> "TopicGraph":
        """Build graph from ROS2 discovery output."""
        graph = cls()
        
        # Parse nodes
        nodes_data = json.loads(nodes_json) if isinstance(nodes_json, str) else nodes_json
        for n in nodes_data:
            name = n.get("name", n.get("node", "unknown"))
            graph.nodes[name] = TopicNode(
                name=name,
                node_type=n.get("type", "unknown"),
                status=n.get("status", "active"),
            )
        
        # Parse topics
        topics_data = json.loads(topics_json) if isinstance(topics_json, str) else topics_json
        for t in topics_data:
            topic_name = t.get("name", "")
            for pub in t.get("publishers", []):
                graph.edges.append(TopicEdge(
                    source=pub,
                    target="",  # broadcast
                    topic=topic_name,
                    direction="pub",
                    msg_type=t.get("type", "unknown"),
                ))
            for sub in t.get("subscribers", []):
                graph.edges.append(TopicEdge(
                    source="",
                    target=sub,
                    topic=topic_name,
                    direction="sub",
                    msg_type=t.get("type", "unknown"),
                ))
        
        return graph
    
    def get_node_topics(self, node_name: str) -> List[TopicEdge]:
        """Get all edges involving a specific node."""
        return [e for e in self.edges if e.source == node_name or e.target == node_name]
    
    def get_topics_by_type(self, msg_type: str) -> List[str]:
        """Find all topics of a specific message type."""
        topics = set()
        for e in self.edges:
            if e.msg_type == msg_type:
                topics.add(e.topic)
        return sorted(topics)
    
    def get_publisher_count(self, topic: str) -> int:
        return sum(1 for e in self.edges if e.topic == topic and e.direction == "pub")
    
    def get_subscriber_count(self, topic: str) -> int:
        return sum(1 for e in self.edges if e.topic == topic and e.direction == "sub")
    
    def find_isolated_nodes(self) -> List[str]:
        """Find nodes with no topic connections."""
        connected = set()
        for e in self.edges:
            if e.source:
                connected.add(e.source)
            if e.target:
                connected.add(e.target)
        return sorted(set(self.nodes.keys()) - connected)
    
    def find_cycles(self) -> List[List[str]]:
        """Detect cycles in service/client calls (simplified DFS)."""
        adj = {name: set() for name in self.nodes}
        for e in self.edges:
            if e.source and e.target:
                adj[e.source].add(e.target)
        
        cycles = []
        visited = set()
        stack = []
        
        def dfs(node, path_set):
            if node in path_set:
                cycle_start = stack.index(node)
                cycles.append(stack[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            path_set.add(node)
            stack.append(node)
            for neighbor in adj.get(node, set()):
                dfs(neighbor, path_set)
            stack.pop()
            path_set.discard(node)
        
        for node in self.nodes:
            if node not in visited:
                dfs(node, set())
        
        return cycles
    
    def summary(self) -> dict:
        """Generate a summary of the topic graph."""
        topics = set(e.topic for e in self.edges)
        msg_types = set(e.msg_type for e in self.edges)
        return {
            "total_nodes": len(self.nodes),
            "active_nodes": sum(1 for n in self.nodes.values() if n.status == "active"),
            "total_topics": len(topics),
            "total_edges": len(self.edges),
            "message_types": sorted(msg_types),
            "isolated_nodes": self.find_isolated_nodes(),
            "cycles_detected": len(self.find_cycles()),
        }
    
    def export_mermaid(self) -> str:
        """Export graph as Mermaid flowchart for documentation."""
        lines = ["graph LR"]
        
        # Nodes
        for name, node in self.nodes.items():
            node_id = name.replace("/", "_").replace("-", "_")
            style = {
                "active": "fill:#4CAF50",
                "inactive": "fill:#9E9E9E",
                "error": "fill:#F44336",
            }.get(node.status, "fill:#FFF")
            lines.append(f'    {node_id}["{name}"]')
        
        # Edges
        for e in self.edges:
            src = (e.source or "topic").replace("/", "_").replace("-", "_")
            tgt = (e.target or "topic").replace("/", "_").replace("-", "_")
            label = e.topic.split("/")[-1][:20]
            lines.append(f"    {src} -->|{label}| {tgt}")
        
        return "\n".join(lines)


def build_mock_graph() -> TopicGraph:
    """Build a mock topic graph for testing/demo."""
    nodes = [
        {"name": "/turtle1/pose", "type": "turtlesim/Pose"},
        {"name": "/turtle1/cmd_vel", "type": "geometry_msgs/Twist"},
        {"name": "/turtle1/color_sensor", "type": "turtlesim/Color"},
        {"name": "/teleop_turtle", "type": "teleop"},
        {"name": "/draw_square", "type": "demo"},
    ]
    
    mock_nodes = json.dumps([
        {"name": n["name"].lstrip("/"), "type": n["type"], "status": "active"}
        for n in nodes
    ])
    
    mock_topics = json.dumps([
        {"name": "/turtle1/pose", "type": "turtlesim/Pose",
         "publishers": ["turtlesim"], "subscribers": ["teleop_turtle"]},
        {"name": "/turtle1/cmd_vel", "type": "geometry_msgs/Twist",
         "publishers": ["teleop_turtle"], "subscribers": ["turtlesim"]},
        {"name": "/turtle1/color_sensor", "type": "turtlesim/Color",
         "publishers": ["turtlesim"], "subscribers": ["draw_square"]},
    ])
    
    return TopicGraph.from_discovery(mock_nodes, mock_topics)


if __name__ == "__main__":
    graph = build_mock_graph()
    print("=== Topic Graph Summary ===")
    print(json.dumps(graph.summary(), indent=2))
    print("\n=== Mermaid Export ===")
    print(graph.export_mermaid())
