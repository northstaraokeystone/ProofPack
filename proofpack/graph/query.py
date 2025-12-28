"""Temporal query interface for the knowledge graph.

Query patterns:
    - Lineage trace: "What receipts led to X?" (<100ms)
    - Temporal range: "What happened between T1 and T2?" (<150ms)
    - Pattern match: "Find receipts matching criteria" (<200ms)
    - Causal chain: "What was the root cause of X?" (<300ms)
    - Episode extraction: "Get complete episode containing X" (<250ms)
"""
import time
from dataclasses import dataclass
from typing import Callable, Optional

from proofpack.core.receipt import emit_receipt, StopRule

from .backend import GraphNode, get_backend


@dataclass
class QueryResult:
    """Result from a graph query."""
    nodes: list[dict]
    edges: list[dict]
    elapsed_ms: float
    query_type: str


def lineage(
    receipt_id: str,
    depth: int = 10,
    tenant_id: str = "default",
) -> QueryResult:
    """Trace receipt ancestry.

    SLO: <100ms

    Args:
        receipt_id: Starting receipt ID
        depth: Maximum depth to trace
        tenant_id: Tenant identifier

    Returns:
        QueryResult with lineage nodes and edges
    """
    start = time.perf_counter()
    backend = get_backend()

    # Use short form
    short_id = receipt_id[:16]

    # Get ancestors
    ancestor_ids = backend.get_ancestors(short_id, depth)

    # Build result
    nodes = []
    edges = []

    # Add starting node
    start_node = backend.get_node(short_id)
    if start_node:
        nodes.append({
            "id": start_node.node_id,
            "type": start_node.receipt_type,
            "event_time": start_node.event_time,
            "depth": 0,
        })

    # Add ancestors
    for i, ancestor_id in enumerate(ancestor_ids):
        node = backend.get_node(ancestor_id)
        if node:
            nodes.append({
                "id": node.node_id,
                "type": node.receipt_type,
                "event_time": node.event_time,
                "depth": i + 1,
            })

    # Get edges between all nodes
    all_ids = {short_id} | set(ancestor_ids)
    for node_id in all_ids:
        for edge in backend.get_edges(node_id, direction="out"):
            if edge.target_id in all_ids:
                edges.append({
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type,
                })

    elapsed_ms = (time.perf_counter() - start) * 1000

    # SLO check
    if elapsed_ms > 100:
        emit_receipt("graph_slo_violation", {
            "query_type": "lineage",
            "elapsed_ms": elapsed_ms,
            "slo_ms": 100,
            "tenant_id": tenant_id,
        })

    emit_receipt("graph_query", {
        "query_type": "lineage",
        "receipt_id": short_id,
        "depth": depth,
        "nodes_found": len(nodes),
        "elapsed_ms": elapsed_ms,
        "tenant_id": tenant_id,
    })

    return QueryResult(
        nodes=nodes,
        edges=edges,
        elapsed_ms=elapsed_ms,
        query_type="lineage",
    )


def temporal(
    start_time: str,
    end_time: str,
    receipt_type: str = None,
    limit: int = 1000,
    tenant_id: str = "default",
) -> QueryResult:
    """Query receipts in a time range.

    SLO: <150ms

    Args:
        start_time: ISO8601 start timestamp
        end_time: ISO8601 end timestamp
        receipt_type: Optional filter by type
        limit: Maximum results
        tenant_id: Tenant identifier

    Returns:
        QueryResult with matching nodes
    """
    start = time.perf_counter()
    backend = get_backend()

    def predicate(node: GraphNode) -> bool:
        if node.event_time < start_time:
            return False
        if node.event_time > end_time:
            return False
        if receipt_type and node.receipt_type != receipt_type:
            return False
        return True

    nodes = []
    for node in backend.query_nodes(predicate):
        nodes.append({
            "id": node.node_id,
            "type": node.receipt_type,
            "event_time": node.event_time,
        })
        if len(nodes) >= limit:
            break

    # Sort by event time
    nodes.sort(key=lambda n: n["event_time"])

    elapsed_ms = (time.perf_counter() - start) * 1000

    # SLO check
    if elapsed_ms > 150:
        emit_receipt("graph_slo_violation", {
            "query_type": "temporal",
            "elapsed_ms": elapsed_ms,
            "slo_ms": 150,
            "tenant_id": tenant_id,
        })

    emit_receipt("graph_query", {
        "query_type": "temporal",
        "start_time": start_time,
        "end_time": end_time,
        "receipt_type": receipt_type,
        "nodes_found": len(nodes),
        "elapsed_ms": elapsed_ms,
        "tenant_id": tenant_id,
    })

    return QueryResult(
        nodes=nodes,
        edges=[],
        elapsed_ms=elapsed_ms,
        query_type="temporal",
    )


def match(
    criteria: dict,
    limit: int = 100,
    tenant_id: str = "default",
) -> QueryResult:
    """Find receipts matching criteria.

    SLO: <200ms

    Args:
        criteria: Dictionary of field: value matches
        limit: Maximum results
        tenant_id: Tenant identifier

    Returns:
        QueryResult with matching nodes
    """
    start = time.perf_counter()
    backend = get_backend()

    def predicate(node: GraphNode) -> bool:
        for key, value in criteria.items():
            if key == "receipt_type":
                if node.receipt_type != value:
                    return False
            elif key == "event_time":
                if node.event_time != value:
                    return False
            else:
                if node.properties.get(key) != value:
                    return False
        return True

    nodes = []
    for node in backend.query_nodes(predicate):
        nodes.append({
            "id": node.node_id,
            "type": node.receipt_type,
            "event_time": node.event_time,
            "properties": node.properties,
        })
        if len(nodes) >= limit:
            break

    elapsed_ms = (time.perf_counter() - start) * 1000

    # SLO check
    if elapsed_ms > 200:
        emit_receipt("graph_slo_violation", {
            "query_type": "match",
            "elapsed_ms": elapsed_ms,
            "slo_ms": 200,
            "tenant_id": tenant_id,
        })

    emit_receipt("graph_query", {
        "query_type": "match",
        "criteria": criteria,
        "nodes_found": len(nodes),
        "elapsed_ms": elapsed_ms,
        "tenant_id": tenant_id,
    })

    return QueryResult(
        nodes=nodes,
        edges=[],
        elapsed_ms=elapsed_ms,
        query_type="match",
    )


def causal_chain(
    receipt_id: str,
    max_depth: int = 20,
    tenant_id: str = "default",
) -> QueryResult:
    """Find the root cause of a receipt.

    Traces back through CAUSED_BY edges to find the originating event.

    SLO: <300ms

    Args:
        receipt_id: Starting receipt ID
        max_depth: Maximum depth to trace
        tenant_id: Tenant identifier

    Returns:
        QueryResult with causal chain from root to receipt
    """
    start = time.perf_counter()
    backend = get_backend()

    short_id = receipt_id[:16]

    # Trace back through CAUSED_BY edges
    chain = []
    current = short_id
    visited = set()

    while len(chain) < max_depth:
        if current in visited:
            break  # Cycle detected
        visited.add(current)

        node = backend.get_node(current)
        if not node:
            break

        chain.append({
            "id": node.node_id,
            "type": node.receipt_type,
            "event_time": node.event_time,
            "depth": len(chain),
        })

        # Find CAUSED_BY edge
        edges = backend.get_edges(current, direction="out")
        caused_by = [e for e in edges if e.edge_type == "CAUSED_BY"]

        if not caused_by:
            break

        current = caused_by[0].target_id

    # Reverse to show root → target
    chain.reverse()
    for i, node in enumerate(chain):
        node["depth"] = i

    # Build edges
    edges = []
    for i in range(len(chain) - 1):
        edges.append({
            "source": chain[i]["id"],
            "target": chain[i + 1]["id"],
            "type": "CAUSED_BY",
        })

    elapsed_ms = (time.perf_counter() - start) * 1000

    # SLO check
    if elapsed_ms > 300:
        emit_receipt("graph_slo_violation", {
            "query_type": "causal_chain",
            "elapsed_ms": elapsed_ms,
            "slo_ms": 300,
            "tenant_id": tenant_id,
        })

    emit_receipt("graph_query", {
        "query_type": "causal_chain",
        "receipt_id": short_id,
        "chain_length": len(chain),
        "root_id": chain[0]["id"] if chain else None,
        "elapsed_ms": elapsed_ms,
        "tenant_id": tenant_id,
    })

    return QueryResult(
        nodes=chain,
        edges=edges,
        elapsed_ms=elapsed_ms,
        query_type="causal_chain",
    )


def episode(
    receipt_id: str,
    context_window: int = 10,
    tenant_id: str = "default",
) -> QueryResult:
    """Extract complete episode containing a receipt.

    An episode includes:
    - The receipt itself
    - Its ancestors (causes)
    - Its descendants (effects)
    - Temporally adjacent receipts

    SLO: <250ms

    Args:
        receipt_id: Central receipt ID
        context_window: Number of temporal neighbors to include
        tenant_id: Tenant identifier

    Returns:
        QueryResult with complete episode
    """
    start = time.perf_counter()
    backend = get_backend()

    short_id = receipt_id[:16]

    # Get the central node
    center = backend.get_node(short_id)
    if not center:
        return QueryResult(nodes=[], edges=[], elapsed_ms=0, query_type="episode")

    # Collect all related node IDs
    related_ids = {short_id}

    # Add ancestors
    ancestors = backend.get_ancestors(short_id, depth=5)
    related_ids.update(ancestors)

    # Add descendants
    descendants = backend.get_descendants(short_id, depth=5)
    related_ids.update(descendants)

    # Add temporal neighbors
    center_time = center.event_time

    # Query nodes close in time
    for node in backend.query_nodes(lambda n: True):
        if len(related_ids) >= context_window * 3:
            break

        # Simple time proximity check (within same hour)
        if node.event_time[:13] == center_time[:13]:
            related_ids.add(node.node_id)

    # Build nodes list
    nodes = []
    for node_id in related_ids:
        node = backend.get_node(node_id)
        if node:
            nodes.append({
                "id": node.node_id,
                "type": node.receipt_type,
                "event_time": node.event_time,
                "is_center": node.node_id == short_id,
            })

    # Sort by event time
    nodes.sort(key=lambda n: n["event_time"])

    # Build edges
    edges = []
    for node_id in related_ids:
        for edge in backend.get_edges(node_id, direction="out"):
            if edge.target_id in related_ids:
                edges.append({
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type,
                })

    elapsed_ms = (time.perf_counter() - start) * 1000

    # SLO check
    if elapsed_ms > 250:
        emit_receipt("graph_slo_violation", {
            "query_type": "episode",
            "elapsed_ms": elapsed_ms,
            "slo_ms": 250,
            "tenant_id": tenant_id,
        })

    emit_receipt("graph_query", {
        "query_type": "episode",
        "receipt_id": short_id,
        "nodes_found": len(nodes),
        "edges_found": len(edges),
        "elapsed_ms": elapsed_ms,
        "tenant_id": tenant_id,
    })

    return QueryResult(
        nodes=nodes,
        edges=edges,
        elapsed_ms=elapsed_ms,
        query_type="episode",
    )
