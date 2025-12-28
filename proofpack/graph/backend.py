"""Graph backend abstraction.

Provides an abstract interface for graph operations with a default
NetworkX implementation. Future versions can swap to Neo4j or ArangoDB.

Backend selection:
    1. NetworkX (in-memory) + pickle persistence - simplest, good for <100k nodes
    2. SQLite with recursive CTEs - medium complexity, good for <1M nodes
    3. Neo4j/ArangoDB - external dependency, only if scale demands
"""
import json
import pickle
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from proofpack.core.receipt import emit_receipt

# Try to import NetworkX
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


@dataclass
class GraphNode:
    """A node in the knowledge graph."""
    node_id: str
    receipt_type: str
    event_time: str  # When it happened (ts from receipt)
    ingestion_time: float  # When it was added to graph
    properties: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the knowledge graph."""
    source_id: str
    target_id: str
    edge_type: str  # CAUSED_BY, PRECEDED, SPAWNED, GRADUATED_TO
    properties: dict = field(default_factory=dict)


class GraphBackend(ABC):
    """Abstract base class for graph backends."""

    @abstractmethod
    def add_node(self, node: GraphNode) -> bool:
        """Add a node to the graph."""
        pass

    @abstractmethod
    def add_edge(self, edge: GraphEdge) -> bool:
        """Add an edge to the graph."""
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        pass

    @abstractmethod
    def get_edges(self, node_id: str, direction: str = "out") -> list[GraphEdge]:
        """Get edges from/to a node."""
        pass

    @abstractmethod
    def query_nodes(self, predicate: Callable[[GraphNode], bool]) -> Iterator[GraphNode]:
        """Query nodes matching predicate."""
        pass

    @abstractmethod
    def get_ancestors(self, node_id: str, depth: int = 10) -> list[str]:
        """Get ancestor node IDs up to depth."""
        pass

    @abstractmethod
    def get_descendants(self, node_id: str, depth: int = 10) -> list[str]:
        """Get descendant node IDs up to depth."""
        pass

    @abstractmethod
    def node_count(self) -> int:
        """Get total node count."""
        pass

    @abstractmethod
    def edge_count(self) -> int:
        """Get total edge count."""
        pass

    @abstractmethod
    def save(self, path: str) -> bool:
        """Persist graph to storage."""
        pass

    @abstractmethod
    def load(self, path: str) -> bool:
        """Load graph from storage."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all nodes and edges."""
        pass


class NetworkXBackend(GraphBackend):
    """NetworkX-based graph backend.

    Good for graphs up to ~100k nodes. Stores everything in memory
    with optional pickle persistence.
    """

    def __init__(self):
        if not HAS_NETWORKX:
            raise ImportError("NetworkX not installed. Run: pip install networkx")

        self._graph = nx.DiGraph()
        self._node_index: dict[str, GraphNode] = {}

    def add_node(self, node: GraphNode) -> bool:
        """Add a node to the graph."""
        if node.node_id in self._node_index:
            return False

        self._graph.add_node(
            node.node_id,
            receipt_type=node.receipt_type,
            event_time=node.event_time,
            ingestion_time=node.ingestion_time,
            **node.properties
        )
        self._node_index[node.node_id] = node
        return True

    def add_edge(self, edge: GraphEdge) -> bool:
        """Add an edge to the graph."""
        # Ensure both nodes exist
        if edge.source_id not in self._node_index:
            return False
        if edge.target_id not in self._node_index:
            return False

        self._graph.add_edge(
            edge.source_id,
            edge.target_id,
            edge_type=edge.edge_type,
            **edge.properties
        )
        return True

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self._node_index.get(node_id)

    def get_edges(self, node_id: str, direction: str = "out") -> list[GraphEdge]:
        """Get edges from/to a node."""
        edges = []

        if direction in ("out", "both"):
            for _, target, data in self._graph.out_edges(node_id, data=True):
                edges.append(GraphEdge(
                    source_id=node_id,
                    target_id=target,
                    edge_type=data.get("edge_type", "UNKNOWN"),
                    properties={k: v for k, v in data.items() if k != "edge_type"}
                ))

        if direction in ("in", "both"):
            for source, _, data in self._graph.in_edges(node_id, data=True):
                edges.append(GraphEdge(
                    source_id=source,
                    target_id=node_id,
                    edge_type=data.get("edge_type", "UNKNOWN"),
                    properties={k: v for k, v in data.items() if k != "edge_type"}
                ))

        return edges

    def query_nodes(self, predicate: Callable[[GraphNode], bool]) -> Iterator[GraphNode]:
        """Query nodes matching predicate."""
        for node in self._node_index.values():
            if predicate(node):
                yield node

    def get_ancestors(self, node_id: str, depth: int = 10) -> list[str]:
        """Get ancestor node IDs using BFS."""
        if node_id not in self._node_index:
            return []

        ancestors = []
        visited = {node_id}
        queue = [(node_id, 0)]

        while queue:
            current, current_depth = queue.pop(0)

            if current_depth >= depth:
                continue

            # Get predecessors (nodes pointing to current)
            for pred in self._graph.predecessors(current):
                if pred not in visited:
                    visited.add(pred)
                    ancestors.append(pred)
                    queue.append((pred, current_depth + 1))

        return ancestors

    def get_descendants(self, node_id: str, depth: int = 10) -> list[str]:
        """Get descendant node IDs using BFS."""
        if node_id not in self._node_index:
            return []

        descendants = []
        visited = {node_id}
        queue = [(node_id, 0)]

        while queue:
            current, current_depth = queue.pop(0)

            if current_depth >= depth:
                continue

            # Get successors (nodes current points to)
            for succ in self._graph.successors(current):
                if succ not in visited:
                    visited.add(succ)
                    descendants.append(succ)
                    queue.append((succ, current_depth + 1))

        return descendants

    def node_count(self) -> int:
        """Get total node count."""
        return len(self._node_index)

    def edge_count(self) -> int:
        """Get total edge count."""
        return self._graph.number_of_edges()

    def save(self, path: str) -> bool:
        """Persist graph to pickle file."""
        try:
            data = {
                "graph": self._graph,
                "node_index": self._node_index,
            }
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump(data, f)
            return True
        except Exception:
            return False

    def load(self, path: str) -> bool:
        """Load graph from pickle file."""
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self._graph = data["graph"]
            self._node_index = data["node_index"]
            return True
        except Exception:
            return False

    def clear(self) -> None:
        """Clear all nodes and edges."""
        self._graph.clear()
        self._node_index.clear()

    def get_subgraph(self, node_ids: list[str]) -> "NetworkXBackend":
        """Extract a subgraph containing the specified nodes."""
        subgraph = NetworkXBackend()
        subgraph._graph = self._graph.subgraph(node_ids).copy()
        subgraph._node_index = {
            nid: self._node_index[nid]
            for nid in node_ids
            if nid in self._node_index
        }
        return subgraph

    def to_dict(self) -> dict:
        """Export graph to dictionary format."""
        return {
            "nodes": [
                {
                    "id": node.node_id,
                    "type": node.receipt_type,
                    "event_time": node.event_time,
                    "properties": node.properties,
                }
                for node in self._node_index.values()
            ],
            "edges": [
                {
                    "source": u,
                    "target": v,
                    "type": data.get("edge_type", "UNKNOWN"),
                    "properties": {k: v for k, v in data.items() if k != "edge_type"},
                }
                for u, v, data in self._graph.edges(data=True)
            ],
        }


# Global backend instance
_backend: Optional[GraphBackend] = None


def get_backend() -> GraphBackend:
    """Get the global graph backend instance."""
    global _backend

    if _backend is None:
        _backend = NetworkXBackend()

    return _backend


def set_backend(backend: GraphBackend) -> None:
    """Set the global graph backend instance."""
    global _backend
    _backend = backend


def reset_backend() -> None:
    """Reset the global backend (for testing)."""
    global _backend
    if _backend:
        _backend.clear()
    _backend = None
