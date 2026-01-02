"""Episode extraction and subgraph construction.

An episode is a coherent subset of the knowledge graph that represents
a complete interaction or workflow. Episodes are useful for:
    - Debugging specific issues
    - Understanding decision chains
    - Replaying past scenarios
"""
import time
from dataclasses import dataclass, field

from proofpack.core.receipt import emit_receipt

from .backend import get_backend


@dataclass
class Episode:
    """A coherent subgraph representing a complete interaction."""

    episode_id: str
    center_node_id: str
    nodes: list[dict]
    edges: list[dict]
    start_time: str
    end_time: str
    receipt_types: list[str]
    metadata: dict = field(default_factory=dict)


def extract_episode(
    receipt_id: str,
    include_ancestors: bool = True,
    include_descendants: bool = True,
    include_siblings: bool = True,
    max_nodes: int = 100,
    tenant_id: str = "default",
) -> Episode | None:
    """Extract a complete episode centered on a receipt.

    Args:
        receipt_id: The center receipt ID
        include_ancestors: Include parent receipts
        include_descendants: Include child receipts
        include_siblings: Include sibling receipts (same parent)
        max_nodes: Maximum nodes to include
        tenant_id: Tenant identifier

    Returns:
        Episode object or None if center not found
    """
    start_time = time.perf_counter()
    backend = get_backend()

    short_id = receipt_id[:16]
    center = backend.get_node(short_id)

    if not center:
        return None

    # Collect node IDs
    node_ids = {short_id}

    # Add ancestors
    if include_ancestors:
        ancestors = backend.get_ancestors(short_id, depth=10)
        node_ids.update(ancestors[:max_nodes // 3])

    # Add descendants
    if include_descendants:
        descendants = backend.get_descendants(short_id, depth=10)
        node_ids.update(descendants[:max_nodes // 3])

    # Add siblings (nodes with same parent)
    if include_siblings:
        edges = backend.get_edges(short_id, direction="out")
        for edge in edges:
            if edge.edge_type in ("CAUSED_BY", "SPAWNED"):
                parent_id = edge.target_id
                # Get all children of this parent
                for sibling in backend.get_edges(parent_id, direction="in"):
                    if len(node_ids) < max_nodes:
                        node_ids.add(sibling.source_id)

    # Build node list
    nodes = []
    receipt_types = set()
    min_time = ""
    max_time = ""

    for node_id in node_ids:
        node = backend.get_node(node_id)
        if node:
            nodes.append({
                "id": node.node_id,
                "type": node.receipt_type,
                "event_time": node.event_time,
                "is_center": node.node_id == short_id,
                "properties": node.properties,
            })
            receipt_types.add(node.receipt_type)

            if not min_time or node.event_time < min_time:
                min_time = node.event_time
            if not max_time or node.event_time > max_time:
                max_time = node.event_time

    # Sort nodes by event time
    nodes.sort(key=lambda n: n["event_time"])

    # Build edge list
    edges = []
    for node_id in node_ids:
        for edge in backend.get_edges(node_id, direction="out"):
            if edge.target_id in node_ids:
                edges.append({
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type,
                    "properties": edge.properties,
                })

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    episode = Episode(
        episode_id=f"episode_{short_id}_{int(time.time())}",
        center_node_id=short_id,
        nodes=nodes,
        edges=edges,
        start_time=min_time,
        end_time=max_time,
        receipt_types=list(receipt_types),
        metadata={
            "extracted_at": time.time(),
            "extraction_ms": elapsed_ms,
            "include_ancestors": include_ancestors,
            "include_descendants": include_descendants,
            "include_siblings": include_siblings,
        },
    )

    emit_receipt("episode_extracted", {
        "episode_id": episode.episode_id,
        "center_node_id": short_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "receipt_types": list(receipt_types),
        "elapsed_ms": elapsed_ms,
        "tenant_id": tenant_id,
    })

    return episode


def episode_to_dict(episode: Episode) -> dict:
    """Convert episode to dictionary format for serialization.

    Args:
        episode: Episode object

    Returns:
        Dictionary representation
    """
    return {
        "episode_id": episode.episode_id,
        "center_node_id": episode.center_node_id,
        "nodes": episode.nodes,
        "edges": episode.edges,
        "start_time": episode.start_time,
        "end_time": episode.end_time,
        "receipt_types": episode.receipt_types,
        "metadata": episode.metadata,
    }


def episode_to_dot(episode: Episode) -> str:
    """Convert episode to DOT format for visualization.

    Args:
        episode: Episode object

    Returns:
        DOT graph format string
    """
    lines = ["digraph episode {"]
    lines.append('  rankdir="LR";')
    lines.append('  node [shape=box];')

    # Add nodes
    for node in episode.nodes:
        style = 'style=filled,fillcolor=yellow' if node.get("is_center") else ""
        label = f"{node['type']}\\n{node['id'][:8]}"
        lines.append(f'  "{node["id"]}" [label="{label}",{style}];')

    # Add edges
    for edge in episode.edges:
        lines.append(f'  "{edge["source"]}" -> "{edge["target"]}" [label="{edge["type"]}"];')

    lines.append("}")

    return "\n".join(lines)


def find_connected_episodes(
    receipt_ids: list[str],
    tenant_id: str = "default",
) -> list[set[str]]:
    """Find connected components among a set of receipts.

    Useful for identifying which receipts belong to the same episode.

    Args:
        receipt_ids: List of receipt IDs to analyze
        tenant_id: Tenant identifier

    Returns:
        List of sets, each set contains connected receipt IDs
    """
    backend = get_backend()

    # Build connectivity graph
    short_ids = [rid[:16] for rid in receipt_ids]
    short_set = set(short_ids)

    # Union-find for connected components
    parent = {sid: sid for sid in short_ids}

    def find(x: str) -> str:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: str, y: str) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Connect nodes that share edges
    for sid in short_ids:
        for edge in backend.get_edges(sid, direction="both"):
            other = edge.target_id if edge.source_id == sid else edge.source_id
            if other in short_set:
                union(sid, other)

    # Group by component
    components: dict[str, set[str]] = {}
    for sid in short_ids:
        root = find(sid)
        if root not in components:
            components[root] = set()
        components[root].add(sid)

    return list(components.values())


def merge_episodes(episodes: list[Episode]) -> Episode:
    """Merge multiple episodes into one.

    Args:
        episodes: List of episodes to merge

    Returns:
        Merged episode
    """
    if not episodes:
        raise ValueError("No episodes to merge")

    if len(episodes) == 1:
        return episodes[0]

    # Combine all nodes and edges
    all_nodes = {}
    all_edges = []
    all_types = set()
    min_time = ""
    max_time = ""

    for ep in episodes:
        for node in ep.nodes:
            if node["id"] not in all_nodes:
                all_nodes[node["id"]] = node
                all_types.add(node["type"])

                if not min_time or node["event_time"] < min_time:
                    min_time = node["event_time"]
                if not max_time or node["event_time"] > max_time:
                    max_time = node["event_time"]

        for edge in ep.edges:
            edge_key = (edge["source"], edge["target"], edge["type"])
            if edge_key not in {(e["source"], e["target"], e["type"]) for e in all_edges}:
                all_edges.append(edge)

    # Determine center (use first episode's center)
    center_id = episodes[0].center_node_id

    nodes = sorted(all_nodes.values(), key=lambda n: n["event_time"])

    return Episode(
        episode_id=f"merged_{int(time.time())}",
        center_node_id=center_id,
        nodes=nodes,
        edges=all_edges,
        start_time=min_time,
        end_time=max_time,
        receipt_types=list(all_types),
        metadata={
            "merged_from": [ep.episode_id for ep in episodes],
            "merged_at": time.time(),
        },
    )
