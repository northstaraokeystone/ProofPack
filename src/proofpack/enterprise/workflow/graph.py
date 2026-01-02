"""Workflow Graph Module - Load, validate, and traverse workflow DAGs.

Per CLAUDEME §12: Every receipts-native system must have explicit workflow DAG.
Graph is loaded once at startup, hashed, and every traversal emits workflow_receipt.

Stoprule: Deviation from planned_path without human approval → HALT
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from proofpack.core.receipt import StopRule, dual_hash, emit_receipt


@dataclass
class Node:
    """Workflow graph node."""
    id: str
    type: str
    function_ref: str
    description: str = ""


@dataclass
class Edge:
    """Workflow graph edge."""
    from_node: str
    to_node: str
    condition: str | None = None
    type: str = "sequential"


@dataclass
class WorkflowGraph:
    """Complete workflow graph structure."""
    version: str
    description: str
    nodes: list[Node]
    edges: list[Edge]
    entry_node: str
    exit_nodes: list[str]
    graph_hash: str = ""

    def get_node(self, node_id: str) -> Node | None:
        """Get node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_successors(self, node_id: str) -> list[tuple[str, str | None]]:
        """Get successor nodes and their conditions."""
        successors = []
        for edge in self.edges:
            if edge.from_node == node_id:
                successors.append((edge.to_node, edge.condition))
        return successors

    def get_predecessors(self, node_id: str) -> list[str]:
        """Get predecessor node IDs."""
        return [edge.from_node for edge in self.edges if edge.to_node == node_id]


@dataclass
class ValidationResult:
    """Result of graph validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class TraversalResult:
    """Result of graph traversal."""
    success: bool
    planned_path: list[str]
    actual_path: list[str]
    deviations: list[dict]
    outputs: dict[str, Any] = field(default_factory=dict)
    receipt: dict | None = None


def load_graph(path: str) -> WorkflowGraph:
    """Load workflow graph from JSON file.

    Args:
        path: Path to workflow_graph.json

    Returns:
        WorkflowGraph object with computed hash

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON is invalid
    """
    graph_path = Path(path)
    if not graph_path.exists():
        raise FileNotFoundError(f"Workflow graph not found: {path}")

    with open(graph_path) as f:
        data = json.load(f)

    # Parse nodes
    nodes = [
        Node(
            id=n["id"],
            type=n["type"],
            function_ref=n["function_ref"],
            description=n.get("description", "")
        )
        for n in data.get("nodes", [])
    ]

    # Parse edges
    edges = [
        Edge(
            from_node=e["from"],
            to_node=e["to"],
            condition=e.get("condition"),
            type=e.get("type", "sequential")
        )
        for e in data.get("edges", [])
    ]

    graph = WorkflowGraph(
        version=data.get("version", "1.0"),
        description=data.get("description", ""),
        nodes=nodes,
        edges=edges,
        entry_node=data.get("entry_node", ""),
        exit_nodes=data.get("exit_nodes", [])
    )

    # Compute and store hash
    graph.graph_hash = hash_graph(graph)

    return graph


def validate_graph(graph: WorkflowGraph) -> ValidationResult:
    """Validate workflow graph structure.

    Checks:
        - Entry node exists
        - All exit nodes exist
        - All edge endpoints reference valid nodes
        - Graph is connected from entry
        - No orphan nodes

    Args:
        graph: WorkflowGraph to validate

    Returns:
        ValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    node_ids = {n.id for n in graph.nodes}

    # Check entry node
    if not graph.entry_node:
        errors.append("Missing entry_node")
    elif graph.entry_node not in node_ids:
        errors.append(f"Entry node '{graph.entry_node}' not found in nodes")

    # Check exit nodes
    if not graph.exit_nodes:
        errors.append("Missing exit_nodes")
    else:
        for exit_node in graph.exit_nodes:
            if exit_node not in node_ids:
                errors.append(f"Exit node '{exit_node}' not found in nodes")

    # Check edges reference valid nodes
    for edge in graph.edges:
        if edge.from_node not in node_ids:
            errors.append(f"Edge from unknown node: {edge.from_node}")
        if edge.to_node not in node_ids:
            errors.append(f"Edge to unknown node: {edge.to_node}")

    # Check connectivity from entry node
    if graph.entry_node in node_ids:
        reachable = _find_reachable(graph, graph.entry_node)
        unreachable = node_ids - reachable
        if unreachable:
            warnings.append(f"Unreachable nodes from entry: {unreachable}")

    # Check all exit nodes are reachable
    if graph.entry_node in node_ids:
        reachable = _find_reachable(graph, graph.entry_node)
        for exit_node in graph.exit_nodes:
            if exit_node not in reachable:
                errors.append(f"Exit node '{exit_node}' not reachable from entry")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def _find_reachable(graph: WorkflowGraph, start: str) -> set[str]:
    """Find all nodes reachable from start node (BFS)."""
    reachable = set()
    queue = [start]

    while queue:
        current = queue.pop(0)
        if current in reachable:
            continue
        reachable.add(current)

        for successor, _ in graph.get_successors(current):
            if successor not in reachable:
                queue.append(successor)

    return reachable


def hash_graph(graph: WorkflowGraph) -> str:
    """Compute dual-hash of workflow graph structure.

    Hash includes: nodes, edges, entry_node, exit_nodes
    Does NOT include: version, description, computed hash

    Args:
        graph: WorkflowGraph to hash

    Returns:
        Dual-hash string (SHA256:BLAKE3)
    """
    # Create canonical representation for hashing
    canonical = {
        "nodes": [
            {"id": n.id, "type": n.type, "function_ref": n.function_ref}
            for n in sorted(graph.nodes, key=lambda x: x.id)
        ],
        "edges": [
            {"from": e.from_node, "to": e.to_node, "condition": e.condition}
            for e in sorted(graph.edges, key=lambda x: (x.from_node, x.to_node))
        ],
        "entry_node": graph.entry_node,
        "exit_nodes": sorted(graph.exit_nodes)
    }

    canonical_json = json.dumps(canonical, sort_keys=True)
    return dual_hash(canonical_json)


def plan_path(graph: WorkflowGraph, context: dict) -> list[str]:
    """Plan execution path through graph based on context.

    Uses BFS to find path from entry to first reachable exit node.
    Conditions in edges are evaluated against context.

    Args:
        graph: WorkflowGraph to traverse
        context: Execution context for condition evaluation

    Returns:
        List of node IDs representing planned path
    """
    if not graph.entry_node:
        return []

    # BFS to find path to exit
    queue = [(graph.entry_node, [graph.entry_node])]
    visited = set()

    while queue:
        current, path = queue.pop(0)

        if current in visited:
            continue
        visited.add(current)

        # Check if we've reached an exit
        if current in graph.exit_nodes:
            return path

        # Explore successors
        for successor, condition in graph.get_successors(current):
            if successor not in visited:
                # Evaluate condition if present
                if condition and not _evaluate_condition(condition, context):
                    continue
                queue.append((successor, path + [successor]))

    # No exit found, return path to last reachable node
    return [graph.entry_node] if visited else []


def _evaluate_condition(condition: str, context: dict) -> bool:
    """Evaluate edge condition against context.

    Supports simple comparisons like 'anomaly_score > threshold'.
    Returns True if condition is met or cannot be evaluated.
    """
    if not condition:
        return True

    try:
        # Simple parser for conditions like "field > value" or "field > field"
        parts = condition.split()
        if len(parts) >= 3:
            left = parts[0]
            op = parts[1]
            right = parts[2]

            # Get values from context
            left_val = context.get(left, 0)
            right_val = context.get(right, right)

            # Try to convert right to number if it's not a context key
            if isinstance(right_val, str) and right_val == right:
                try:
                    right_val = float(right)
                except ValueError:
                    pass

            # Evaluate
            if op == ">":
                return left_val > right_val
            elif op == "<":
                return left_val < right_val
            elif op == ">=":
                return left_val >= right_val
            elif op == "<=":
                return left_val <= right_val
            elif op == "==":
                return left_val == right_val
    except Exception:
        pass

    # Default to True if we can't evaluate
    return True


def traverse(
    graph: WorkflowGraph,
    entry: str,
    context: dict,
    node_executor: Callable[[str, dict], tuple[bool, Any]] | None = None,
    require_approval_on_deviation: bool = True,
    tenant_id: str = "default"
) -> TraversalResult:
    """Traverse workflow graph and execute nodes.

    Executes nodes in order, tracking planned vs actual path.
    Emits workflow_receipt at completion.

    Args:
        graph: WorkflowGraph to traverse
        entry: Entry node ID (must match graph.entry_node)
        context: Execution context
        node_executor: Optional function(node_id, context) -> (success, output)
        require_approval_on_deviation: If True, HALT on deviation
        tenant_id: Tenant identifier

    Returns:
        TraversalResult with paths, deviations, and receipt

    Raises:
        StopRule: If deviation occurs and require_approval_on_deviation is True
    """
    if entry != graph.entry_node:
        raise ValueError(f"Entry must be {graph.entry_node}, got {entry}")

    # Plan the path
    planned_path = plan_path(graph, context)
    actual_path = []
    deviations = []
    outputs = {}

    # Execute nodes
    current = entry
    visited = set()

    while current and current not in visited:
        visited.add(current)
        actual_path.append(current)

        # Execute node if executor provided
        if node_executor:
            try:
                success, output = node_executor(current, context)
                outputs[current] = output

                if not success:
                    # Node failed - record deviation
                    expected_idx = len(actual_path) - 1
                    expected = planned_path[expected_idx] if expected_idx < len(planned_path) else "none"
                    deviations.append({
                        "expected": expected,
                        "actual": f"{current}:failed",
                        "reason": "Node execution failed"
                    })
                    break
            except Exception as e:
                outputs[current] = {"error": str(e)}
                deviations.append({
                    "expected": current,
                    "actual": f"{current}:error",
                    "reason": str(e)
                })
                break

        # Check if we've reached an exit
        if current in graph.exit_nodes:
            break

        # Find next node
        successors = graph.get_successors(current)
        next_node = None

        for successor, condition in successors:
            if _evaluate_condition(condition, context):
                next_node = successor
                break

        current = next_node

    # Check for path deviations
    for i, (planned, actual) in enumerate(zip(planned_path, actual_path)):
        if planned != actual:
            deviations.append({
                "expected": planned,
                "actual": actual,
                "reason": "Path diverged from plan"
            })

    # Length mismatch is also a deviation
    if len(actual_path) != len(planned_path):
        deviations.append({
            "expected": f"length:{len(planned_path)}",
            "actual": f"length:{len(actual_path)}",
            "reason": "Path length mismatch"
        })

    # Handle deviations
    if deviations and require_approval_on_deviation:
        stoprule_workflow_deviation(
            planned_path,
            actual_path,
            deviations[0]["reason"]
        )

    # Emit workflow receipt
    receipt = emit_workflow_receipt(
        graph.graph_hash,
        planned_path,
        actual_path,
        deviations,
        tenant_id
    )

    success = len(deviations) == 0 and (
        actual_path[-1] in graph.exit_nodes if actual_path else False
    )

    return TraversalResult(
        success=success,
        planned_path=planned_path,
        actual_path=actual_path,
        deviations=deviations,
        outputs=outputs,
        receipt=receipt
    )


def emit_workflow_receipt(
    graph_hash: str,
    planned_path: list[str],
    actual_path: list[str],
    deviations: list[dict],
    tenant_id: str = "default"
) -> dict:
    """Emit workflow execution receipt.

    Per CLAUDEME §12: Every traversal must emit workflow_receipt.

    Args:
        graph_hash: Dual-hash of workflow graph
        planned_path: Planned node execution order
        actual_path: Actual node execution order
        deviations: List of path deviations
        tenant_id: Tenant identifier

    Returns:
        Workflow receipt dict
    """
    return emit_receipt("workflow", {
        "tenant_id": tenant_id,
        "graph_hash": graph_hash,
        "planned_path": planned_path,
        "actual_path": actual_path,
        "deviations": deviations
    })


def stoprule_workflow_deviation(
    planned_path: list[str],
    actual_path: list[str],
    reason: str
):
    """HALT on workflow path deviation without human approval.

    Per CLAUDEME §12: Deviation without approval triggers HALT.
    """
    emit_receipt("anomaly", {
        "metric": "workflow_deviation",
        "baseline": len(planned_path),
        "delta": len(actual_path) - len(planned_path),
        "classification": "violation",
        "action": "halt"
    })
    raise StopRule(
        f"Workflow deviation: planned {planned_path}, got {actual_path}. "
        f"Reason: {reason}. Human approval required to proceed."
    )
