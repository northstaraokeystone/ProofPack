"""Temporal Knowledge Graph for ProofPack.

Transforms static receipt storage into a queryable temporal knowledge graph.
Enables "what happened before X" queries in <300ms.

Key concepts:
    - Receipts become nodes
    - Lineage becomes edges (CAUSED_BY, PRECEDED, SPAWNED, GRADUATED_TO)
    - Temporal markers track event_time and ingestion_time

Usage:
    from graph import ingest, query

    # Add receipt to graph
    ingest.add_node(receipt)

    # Query lineage
    lineage = query.lineage("receipt-id", depth=5)

    # Temporal range query
    events = query.temporal("2024-01-01", "2024-12-31")

    # Episode extraction
    episode = query.episode("receipt-id")

Performance SLOs:
    - Lineage trace: <100ms
    - Temporal range: <150ms
    - Pattern match: <200ms
    - Causal chain: <300ms
    - Episode extraction: <250ms
"""

from .backend import GraphBackend, get_backend
from .ingest import add_node, add_edge, bulk_ingest
from .query import lineage, temporal, match, causal_chain, episode

__all__ = [
    # Backend
    "GraphBackend",
    "get_backend",
    # Ingest
    "add_node",
    "add_edge",
    "bulk_ingest",
    # Query
    "lineage",
    "temporal",
    "match",
    "causal_chain",
    "episode",
]
