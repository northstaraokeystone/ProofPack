"""Graph indexing for fast retrieval.

Maintains secondary indexes for common query patterns:
    - By receipt type
    - By time range (bucketed)
    - By parent relationship
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Set

from proofpack.core.receipt import emit_receipt

from .backend import GraphNode, get_backend


@dataclass
class GraphIndex:
    """Secondary indexes for the graph."""

    # Type index: receipt_type -> set of node_ids
    by_type: dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    # Time bucket index: YYYY-MM-DD-HH -> set of node_ids
    by_time_bucket: dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    # Parent index: parent_id -> set of child_ids
    by_parent: dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    # Reverse parent index: child_id -> parent_id
    parent_of: dict[str, str] = field(default_factory=dict)


# Global index instance
_index: Optional[GraphIndex] = None


def get_index() -> GraphIndex:
    """Get the global graph index."""
    global _index
    if _index is None:
        _index = GraphIndex()
    return _index


def reset_index() -> None:
    """Reset the global index (for testing)."""
    global _index
    _index = None


def index_node(node: GraphNode, parent_id: str = None) -> None:
    """Add a node to all indexes.

    Args:
        node: The node to index
        parent_id: Optional parent node ID
    """
    idx = get_index()

    # Type index
    idx.by_type[node.receipt_type].add(node.node_id)

    # Time bucket index (hourly buckets)
    if node.event_time:
        # Extract YYYY-MM-DD-HH from ISO timestamp
        bucket = node.event_time[:13].replace("T", "-") if len(node.event_time) >= 13 else ""
        if bucket:
            idx.by_time_bucket[bucket].add(node.node_id)

    # Parent index
    if parent_id:
        idx.by_parent[parent_id].add(node.node_id)
        idx.parent_of[node.node_id] = parent_id


def remove_from_index(node_id: str) -> None:
    """Remove a node from all indexes.

    Args:
        node_id: The node ID to remove
    """
    idx = get_index()

    # Remove from type index
    for type_set in idx.by_type.values():
        type_set.discard(node_id)

    # Remove from time bucket index
    for bucket_set in idx.by_time_bucket.values():
        bucket_set.discard(node_id)

    # Remove from parent index
    for children in idx.by_parent.values():
        children.discard(node_id)

    # Remove this node's children tracking
    if node_id in idx.by_parent:
        del idx.by_parent[node_id]

    # Remove from reverse parent index
    if node_id in idx.parent_of:
        del idx.parent_of[node_id]


def get_by_type(receipt_type: str) -> Set[str]:
    """Get all node IDs of a specific type.

    Args:
        receipt_type: The receipt type to query

    Returns:
        Set of matching node IDs
    """
    return get_index().by_type.get(receipt_type, set())


def get_by_time_range(start_time: str, end_time: str) -> Set[str]:
    """Get all node IDs within a time range.

    Uses hourly buckets for efficient filtering.

    Args:
        start_time: ISO8601 start timestamp
        end_time: ISO8601 end timestamp

    Returns:
        Set of node IDs that may be in range (may need further filtering)
    """
    idx = get_index()

    # Extract bucket range
    start_bucket = start_time[:13].replace("T", "-") if len(start_time) >= 13 else ""
    end_bucket = end_time[:13].replace("T", "-") if len(end_time) >= 13 else ""

    result = set()
    for bucket, node_ids in idx.by_time_bucket.items():
        if bucket >= start_bucket and bucket <= end_bucket:
            result.update(node_ids)

    return result


def get_children(parent_id: str) -> Set[str]:
    """Get all child node IDs of a parent.

    Args:
        parent_id: The parent node ID

    Returns:
        Set of child node IDs
    """
    return get_index().by_parent.get(parent_id, set())


def get_parent(child_id: str) -> Optional[str]:
    """Get the parent node ID of a child.

    Args:
        child_id: The child node ID

    Returns:
        Parent node ID or None
    """
    return get_index().parent_of.get(child_id)


def rebuild_index(tenant_id: str = "default") -> dict:
    """Rebuild all indexes from the graph.

    Args:
        tenant_id: Tenant identifier

    Returns:
        Statistics about rebuilt index
    """
    start_time = time.perf_counter()

    # Reset index
    reset_index()
    idx = get_index()

    backend = get_backend()
    node_count = 0

    # Index all nodes
    for node in backend.query_nodes(lambda n: True):
        node_count += 1

        # Type index
        idx.by_type[node.receipt_type].add(node.node_id)

        # Time bucket index
        if node.event_time:
            bucket = node.event_time[:13].replace("T", "-") if len(node.event_time) >= 13 else ""
            if bucket:
                idx.by_time_bucket[bucket].add(node.node_id)

        # Parent relationships from edges
        edges = backend.get_edges(node.node_id, direction="out")
        for edge in edges:
            if edge.edge_type in ("CAUSED_BY", "SPAWNED"):
                idx.parent_of[node.node_id] = edge.target_id
                idx.by_parent[edge.target_id].add(node.node_id)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    stats = {
        "nodes_indexed": node_count,
        "type_buckets": len(idx.by_type),
        "time_buckets": len(idx.by_time_bucket),
        "parent_relationships": len(idx.parent_of),
        "elapsed_ms": elapsed_ms,
    }

    emit_receipt("graph_index_rebuild", {
        **stats,
        "tenant_id": tenant_id,
    })

    return stats


def get_index_stats() -> dict:
    """Get statistics about the current index.

    Returns:
        Dictionary with index statistics
    """
    idx = get_index()

    return {
        "type_count": len(idx.by_type),
        "time_bucket_count": len(idx.by_time_bucket),
        "parent_count": len(idx.by_parent),
        "child_count": len(idx.parent_of),
        "largest_type": max(
            ((t, len(s)) for t, s in idx.by_type.items()),
            key=lambda x: x[1],
            default=("", 0)
        ),
        "largest_time_bucket": max(
            ((b, len(s)) for b, s in idx.by_time_bucket.items()),
            key=lambda x: x[1],
            default=("", 0)
        ),
    }
