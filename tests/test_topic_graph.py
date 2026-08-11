"""Tests for the ROS2 topic graph model and mock graph builder."""

from lappa.topic_graph import TopicGraph, TopicNode, TopicEdge, build_mock_graph


def test_mock_graph_has_nodes():
    """A mock graph should contain at least one node."""
    graph = build_mock_graph()
    assert len(graph.nodes) > 0, "Mock graph should have >0 nodes"


def test_mock_graph_has_edges():
    """A mock graph should contain at least one edge."""
    graph = build_mock_graph()
    assert len(graph.edges) > 0, "Mock graph should have >0 edges"


def test_mock_graph_has_both_kinds():
    """Mock graph should contain both 'node' and 'topic' kind nodes."""
    graph = build_mock_graph()
    kinds = {n.kind for n in graph.nodes}
    assert "node" in kinds, "Mock graph should have node-kind nodes"
    assert "topic" in kinds, "Mock graph should have topic-kind nodes"


def test_node_ids_unique():
    """Every node in the mock graph should have a unique ID."""
    graph = build_mock_graph()
    ids = [n.id for n in graph.nodes]
    assert len(ids) == len(set(ids)), "Node IDs must be unique"


def test_edge_src_dst_exist():
    """Every edge source and destination must reference an existing node."""
    graph = build_mock_graph()
    node_ids = {n.id for n in graph.nodes}
    for e in graph.edges:
        assert e.src in node_ids, (
            f"Edge src '{e.src}' not found in nodes"
        )
        assert e.dst in node_ids, (
            f"Edge dst '{e.dst}' not found in nodes"
        )


def test_to_dict():
    """to_dict() should produce a JSON-serialisable structure."""
    graph = build_mock_graph()
    d = graph.to_dict()
    assert "nodes" in d
    assert "edges" in d
    assert len(d["nodes"]) == len(graph.nodes)
    assert len(d["edges"]) == len(graph.edges)


def test_to_dict_node_keys():
    """Each node dict should have the expected keys."""
    graph = build_mock_graph()
    d = graph.to_dict()
    for node in d["nodes"]:
        assert "id" in node
        assert "label" in node
        assert "kind" in node
        assert "x" in node
        assert "y" in node


def test_empty_graph():
    """An empty graph should be valid."""
    g = TopicGraph()
    assert g.nodes == []
    assert g.edges == []
    d = g.to_dict()
    assert d["nodes"] == []
    assert d["edges"] == []


def test_graph_node_lookup():
    """TopicGraph.node() should return the correct node by ID."""
    g = TopicGraph()
    g.nodes.append(TopicNode(id="test_node", label="Test Node"))
    n = g.node("test_node")
    assert n is not None
    assert n.label == "Test Node"
    assert g.node("nonexistent") is None


def test_mock_graph_representative():
    """Mock graph should contain a representative set of ROS2 nodes."""
    graph = build_mock_graph()
    node_labels = {n.label for n in graph.nodes if n.kind == "node"}
    # At least a few common robot navigation nodes
    expected = {"driver_node", "cmd_vel_mux", "slam_toolbox"}
    assert expected.issubset(node_labels), (
        f"Missing expected nodes. Got: {node_labels}"
    )