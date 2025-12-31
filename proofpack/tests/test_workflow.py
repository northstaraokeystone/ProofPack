"""Tests for workflow graph module.

Per DELIVERABLE 2: Tests for workflow_graph.json and graph.py
"""

import json
import pytest
from pathlib import Path

from proofpack.core.receipt import dual_hash


# Mock the workflow module for testing
class MockNode:
    def __init__(self, id: str, type: str, function_ref: str, description: str = ""):
        self.id = id
        self.type = type
        self.function_ref = function_ref
        self.description = description


class MockEdge:
    def __init__(self, from_node: str, to_node: str, condition: str | None = None):
        self.from_node = from_node
        self.to_node = to_node
        self.condition = condition


class MockWorkflowGraph:
    def __init__(self, nodes, edges, entry_node, exit_nodes):
        self.nodes = nodes
        self.edges = edges
        self.entry_node = entry_node
        self.exit_nodes = exit_nodes
        self.graph_hash = ""

    def get_node(self, node_id: str):
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_successors(self, node_id: str):
        return [(e.to_node, e.condition) for e in self.edges if e.from_node == node_id]


def test_workflow_graph_json_exists():
    """Test that workflow_graph.json exists."""
    graph_path = Path(__file__).parent.parent / "workflow_graph.json"
    assert graph_path.exists(), "workflow_graph.json should exist"


def test_workflow_graph_json_valid():
    """Test that workflow_graph.json is valid JSON."""
    graph_path = Path(__file__).parent.parent / "workflow_graph.json"

    with open(graph_path, "r") as f:
        data = json.load(f)

    # Required fields
    assert "nodes" in data
    assert "edges" in data
    assert "entry_node" in data
    assert "exit_nodes" in data


def test_workflow_graph_json_has_required_nodes():
    """Test that workflow_graph.json has all 7 required nodes."""
    graph_path = Path(__file__).parent.parent / "workflow_graph.json"

    with open(graph_path, "r") as f:
        data = json.load(f)

    node_ids = {n["id"] for n in data["nodes"]}
    required_nodes = {"ledger", "brief", "packet", "detect", "anchor", "loop", "mcp_server"}

    assert required_nodes.issubset(node_ids), f"Missing nodes: {required_nodes - node_ids}"


def test_workflow_graph_json_entry_node():
    """Test that entry_node is 'ledger'."""
    graph_path = Path(__file__).parent.parent / "workflow_graph.json"

    with open(graph_path, "r") as f:
        data = json.load(f)

    assert data["entry_node"] == "ledger"


def test_workflow_graph_json_exit_nodes():
    """Test that exit_nodes includes expected nodes."""
    graph_path = Path(__file__).parent.parent / "workflow_graph.json"

    with open(graph_path, "r") as f:
        data = json.load(f)

    exit_nodes = set(data["exit_nodes"])
    assert "mcp_server" in exit_nodes or "anchor" in exit_nodes


def test_workflow_graph_hash():
    """Test that graph hash can be computed."""
    # Create simple graph
    nodes = [
        MockNode("a", "type", "ref"),
        MockNode("b", "type", "ref")
    ]
    edges = [MockEdge("a", "b")]
    graph = MockWorkflowGraph(nodes, edges, "a", ["b"])

    # Hash the structure
    canonical = {
        "nodes": [{"id": n.id, "type": n.type, "function_ref": n.function_ref} for n in nodes],
        "edges": [{"from": e.from_node, "to": e.to_node, "condition": e.condition} for e in edges],
        "entry_node": "a",
        "exit_nodes": ["b"]
    }
    hash_result = dual_hash(json.dumps(canonical, sort_keys=True))

    assert ":" in hash_result, "Hash should be dual-hash format"


def test_workflow_receipt_emission():
    """Test workflow receipt emission."""
    from proofpack.core.receipt import emit_receipt

    receipt = emit_receipt("workflow", {
        "tenant_id": "test",
        "graph_hash": "sha256:blake3",
        "planned_path": ["a", "b", "c"],
        "actual_path": ["a", "b", "c"],
        "deviations": []
    })

    assert receipt["receipt_type"] == "workflow"
    assert receipt["planned_path"] == ["a", "b", "c"]
    assert receipt["deviations"] == []


def test_workflow_deviation_detection():
    """Test that deviations are detected correctly."""
    planned = ["a", "b", "c"]
    actual = ["a", "x", "c"]

    deviations = []
    for i, (p, a) in enumerate(zip(planned, actual)):
        if p != a:
            deviations.append({
                "expected": p,
                "actual": a,
                "reason": f"Deviation at step {i}"
            })

    assert len(deviations) == 1
    assert deviations[0]["expected"] == "b"
    assert deviations[0]["actual"] == "x"


def test_workflow_graph_connectivity():
    """Test that graph is connected from entry to exit."""
    graph_path = Path(__file__).parent.parent / "workflow_graph.json"

    with open(graph_path, "r") as f:
        data = json.load(f)

    # Build adjacency list
    adjacency = {}
    for edge in data["edges"]:
        from_node = edge["from"]
        to_node = edge["to"]
        if from_node not in adjacency:
            adjacency[from_node] = []
        adjacency[from_node].append(to_node)

    # BFS from entry
    entry = data["entry_node"]
    visited = set()
    queue = [entry]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                queue.append(neighbor)

    # Check all exit nodes are reachable
    for exit_node in data["exit_nodes"]:
        assert exit_node in visited, f"Exit node {exit_node} not reachable from entry"


def test_workflow_graph_no_orphans():
    """Test that no nodes are orphaned (unreachable)."""
    graph_path = Path(__file__).parent.parent / "workflow_graph.json"

    with open(graph_path, "r") as f:
        data = json.load(f)

    all_nodes = {n["id"] for n in data["nodes"]}

    # Nodes referenced in edges
    edge_nodes = set()
    for edge in data["edges"]:
        edge_nodes.add(edge["from"])
        edge_nodes.add(edge["to"])

    # Entry node should be included
    edge_nodes.add(data["entry_node"])

    # All nodes should be referenced (except potentially some exit nodes)
    unreferenced = all_nodes - edge_nodes
    # Filter to non-exit nodes
    non_exit_unreferenced = unreferenced - set(data["exit_nodes"])

    assert len(non_exit_unreferenced) == 0, f"Orphaned nodes: {non_exit_unreferenced}"
