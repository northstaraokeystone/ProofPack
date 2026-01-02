"""Tests for temporal knowledge graph module.

Validates graph ingestion, queries, and performance SLOs.
"""
import time
from io import StringIO
from unittest.mock import patch

import pytest


class TestGraphBackend:
    """Tests for graph backend."""

    def test_networkx_backend_creation(self):
        """Test NetworkX backend can be created."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import NetworkXBackend

        backend = NetworkXBackend()

        assert backend.node_count() == 0
        assert backend.edge_count() == 0

    def test_add_node(self):
        """Test adding nodes to graph."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import GraphNode, NetworkXBackend

        backend = NetworkXBackend()
        node = GraphNode(
            node_id="test123",
            receipt_type="test",
            event_time="2024-01-01T00:00:00Z",
            ingestion_time=time.time(),
            properties={"key": "value"}
        )

        result = backend.add_node(node)

        assert result is True
        assert backend.node_count() == 1

    def test_add_duplicate_node_fails(self):
        """Test adding duplicate node returns False."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import GraphNode, NetworkXBackend

        backend = NetworkXBackend()
        node = GraphNode(
            node_id="test123",
            receipt_type="test",
            event_time="2024-01-01T00:00:00Z",
            ingestion_time=time.time(),
        )

        backend.add_node(node)
        result = backend.add_node(node)

        assert result is False
        assert backend.node_count() == 1

    def test_add_edge(self):
        """Test adding edges between nodes."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import GraphEdge, GraphNode, NetworkXBackend

        backend = NetworkXBackend()

        node1 = GraphNode("n1", "test", "2024-01-01T00:00:00Z", time.time())
        node2 = GraphNode("n2", "test", "2024-01-01T00:01:00Z", time.time())

        backend.add_node(node1)
        backend.add_node(node2)

        edge = GraphEdge(
            source_id="n1",
            target_id="n2",
            edge_type="CAUSED_BY"
        )

        result = backend.add_edge(edge)

        assert result is True
        assert backend.edge_count() == 1

    def test_get_ancestors(self):
        """Test ancestor traversal."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import GraphEdge, GraphNode, NetworkXBackend

        backend = NetworkXBackend()

        # Create chain: n1 <- n2 <- n3
        for i in range(3):
            node = GraphNode(f"n{i}", "test", f"2024-01-01T00:0{i}:00Z", time.time())
            backend.add_node(node)

        backend.add_edge(GraphEdge("n1", "n0", "CAUSED_BY"))
        backend.add_edge(GraphEdge("n2", "n1", "CAUSED_BY"))

        ancestors = backend.get_ancestors("n2", depth=10)

        assert "n1" in ancestors
        assert "n0" in ancestors


class TestGraphIngest:
    """Tests for receipt ingestion."""

    def test_add_receipt_to_graph(self):
        """Test adding receipt as node."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import reset_backend
        from proofpack.graph.ingest import add_node

        reset_backend()

        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "payload_hash": "abc123def456:ghi789jkl012" + "0" * 96,
            "key": "value"
        }

        with patch('sys.stdout', new=StringIO()):
            node_id = add_node(receipt)

        assert node_id is not None
        assert len(node_id) == 16  # Short form

    def test_bulk_ingest(self):
        """Test bulk ingestion of receipts."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import reset_backend
        from proofpack.graph.ingest import bulk_ingest

        reset_backend()

        receipts = [
            {"receipt_type": "test", "ts": f"2024-01-01T00:0{i}:00Z",
             "payload_hash": f"abc{i:03d}def456:ghi789jkl012" + "0" * 96}
            for i in range(10)
        ]

        with patch('sys.stdout', new=StringIO()):
            result = bulk_ingest(receipts, emit_progress=False)

        assert result["added"] == 10
        assert result["errors"] == 0


class TestGraphQuery:
    """Tests for graph queries."""

    @pytest.fixture(autouse=True)
    def setup_graph(self):
        """Set up test graph with sample data."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import GraphEdge, GraphNode, get_backend, reset_backend

        reset_backend()
        backend = get_backend()

        # Create test nodes
        for i in range(5):
            node = GraphNode(
                f"node{i:04d}0000",
                "test",
                f"2024-01-01T00:0{i}:00Z",
                time.time(),
                {"index": i}
            )
            backend.add_node(node)

        # Create edges
        backend.add_edge(GraphEdge("node00010000", "node00000000", "CAUSED_BY"))
        backend.add_edge(GraphEdge("node00020000", "node00010000", "CAUSED_BY"))

        yield

        reset_backend()

    def test_lineage_query(self):
        """Test lineage query."""
        from proofpack.graph.query import lineage

        with patch('sys.stdout', new=StringIO()):
            result = lineage("node00020000", depth=5)

        assert len(result.nodes) > 0
        assert result.query_type == "lineage"

    def test_temporal_query(self):
        """Test temporal range query."""
        from proofpack.graph.query import temporal

        with patch('sys.stdout', new=StringIO()):
            result = temporal(
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:05:00Z"
            )

        assert len(result.nodes) > 0
        assert result.query_type == "temporal"

    def test_match_query(self):
        """Test pattern matching query."""
        from proofpack.graph.query import match

        with patch('sys.stdout', new=StringIO()):
            result = match({"receipt_type": "test"})

        assert len(result.nodes) > 0
        assert result.query_type == "match"


class TestGraphPerformance:
    """Performance tests for graph queries."""

    def test_lineage_slo(self):
        """Test lineage query meets <100ms SLO."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import GraphNode, get_backend, reset_backend
        from proofpack.graph.query import lineage

        reset_backend()
        backend = get_backend()

        # Create larger graph
        for i in range(100):
            node = GraphNode(
                f"n{i:08d}",
                "test",
                f"2024-01-01T00:00:{i:02d}Z",
                time.time()
            )
            backend.add_node(node)

        with patch('sys.stdout', new=StringIO()):
            result = lineage("n00000050", depth=10)

        # Should complete within SLO
        assert result.elapsed_ms < 100

    def test_temporal_slo(self):
        """Test temporal query meets <150ms SLO."""
        pytest.importorskip("networkx")
        from proofpack.graph.backend import GraphNode, get_backend, reset_backend
        from proofpack.graph.query import temporal

        reset_backend()
        backend = get_backend()

        for i in range(100):
            node = GraphNode(
                f"n{i:08d}",
                "test",
                f"2024-01-01T00:00:{i % 60:02d}Z",
                time.time()
            )
            backend.add_node(node)

        with patch('sys.stdout', new=StringIO()):
            result = temporal("2024-01-01T00:00:00Z", "2024-01-01T00:01:00Z")

        assert result.elapsed_ms < 150
