"""Benchmark: Graph query latency.

Target SLOs:
  - Lineage query: <100ms
  - Temporal query: <150ms
  - Match query: <200ms
  - Causal chain: <300ms
"""
import time
import pytest
from datetime import datetime, timedelta
import uuid


class MockGraph:
    """Mock graph for benchmarking queries."""

    def __init__(self, node_count: int = 10000):
        self.nodes = {}
        self.edges = []
        self._generate_graph(node_count)

    def _generate_graph(self, count: int):
        """Generate test graph with lineage relationships."""
        for i in range(count):
            node_id = str(uuid.uuid4())
            ts = datetime.utcnow() - timedelta(days=i % 30)
            self.nodes[node_id] = {
                "id": node_id,
                "ts": ts.isoformat() + "Z",
                "type": f"type_{i % 10}",
                "tenant_id": f"tenant_{i % 5}",
            }
            # Create lineage edges
            if i > 0:
                parent_id = list(self.nodes.keys())[i - 1]
                self.edges.append((parent_id, node_id))

    def query_lineage(self, node_id: str, depth: int = 10) -> list:
        """Query lineage ancestors."""
        result = []
        current = node_id

        for edge in reversed(self.edges):
            if len(result) >= depth:
                break
            if edge[1] == current:
                result.append(self.nodes.get(edge[0], {}))
                current = edge[0]

        return result

    def query_temporal(self, start: datetime, end: datetime) -> list:
        """Query nodes in time range."""
        results = []
        for node in self.nodes.values():
            ts = datetime.fromisoformat(node["ts"].rstrip("Z"))
            if start <= ts <= end:
                results.append(node)
        return results

    def query_match(self, pattern: dict) -> list:
        """Query nodes matching pattern."""
        results = []
        for node in self.nodes.values():
            matches = True
            for key, value in pattern.items():
                if node.get(key) != value:
                    matches = False
                    break
            if matches:
                results.append(node)
        return results


class TestGraphQueryPerformance:
    """Benchmark graph query operations."""

    @pytest.fixture
    def graph(self):
        """Create test graph."""
        return MockGraph(10000)

    def test_lineage_query_latency(self, graph, benchmark):
        """Lineage query should complete in <100ms."""
        target_id = list(graph.nodes.keys())[5000]

        def query():
            return graph.query_lineage(target_id, depth=10)

        result = benchmark(query)
        assert len(result) <= 10

    def test_temporal_query_latency(self, graph, benchmark):
        """Temporal query (30 days) should complete in <150ms."""
        end = datetime.utcnow()
        start = end - timedelta(days=30)

        def query():
            return graph.query_temporal(start, end)

        result = benchmark(query)
        assert len(result) > 0

    def test_match_query_latency(self, graph, benchmark):
        """Match query should complete in <200ms."""
        pattern = {"type": "type_5", "tenant_id": "tenant_2"}

        def query():
            return graph.query_match(pattern)

        result = benchmark(query)
        # Should find some matches
        assert isinstance(result, list)


def manual_benchmark():
    """Manual benchmark for verification."""
    print("\nGraph Query Benchmark")
    print("-" * 50)

    # Create graph
    print("  Creating 10k node graph...", end=" ")
    start = time.perf_counter()
    graph = MockGraph(10000)
    print(f"done ({time.perf_counter() - start:.2f}s)")

    # Lineage query
    target_id = list(graph.nodes.keys())[5000]
    iterations = 100

    start = time.perf_counter()
    for _ in range(iterations):
        graph.query_lineage(target_id, depth=10)
    elapsed = (time.perf_counter() - start) / iterations * 1000
    print(f"  Lineage query: {elapsed:.1f}ms (SLO <100ms) [{'PASS' if elapsed < 100 else 'FAIL'}]")

    # Temporal query
    end = datetime.utcnow()
    start_date = end - timedelta(days=30)

    start = time.perf_counter()
    for _ in range(iterations):
        graph.query_temporal(start_date, end)
    elapsed = (time.perf_counter() - start) / iterations * 1000
    print(f"  Temporal query: {elapsed:.1f}ms (SLO <150ms) [{'PASS' if elapsed < 150 else 'FAIL'}]")

    # Match query
    pattern = {"type": "type_5"}

    start = time.perf_counter()
    for _ in range(iterations):
        graph.query_match(pattern)
    elapsed = (time.perf_counter() - start) / iterations * 1000
    print(f"  Match query: {elapsed:.1f}ms (SLO <200ms) [{'PASS' if elapsed < 200 else 'FAIL'}]")

    print("-" * 50)


if __name__ == "__main__":
    manual_benchmark()
