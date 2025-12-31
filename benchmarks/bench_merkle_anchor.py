"""Benchmark: Merkle anchoring throughput.

Target SLO: <1000ms for 1000 receipts.
"""
import time

from proofpack.core.receipt import merkle


class TestMerkleAnchorPerformance:
    """Benchmark Merkle tree operations."""

    def test_merkle_1000_receipts(self, benchmark):
        """Anchor 1000 receipts in <1000ms."""
        receipts = [
            {"receipt_type": "bench", "seq": i, "tenant_id": "bench"}
            for i in range(1000)
        ]

        def compute_merkle():
            return merkle(receipts)

        result = benchmark(compute_merkle)
        assert result is not None
        assert ":" in result  # Dual-hash format

    def test_merkle_100_receipts(self, benchmark):
        """Anchor 100 receipts - baseline measure."""
        receipts = [
            {"receipt_type": "bench", "seq": i, "tenant_id": "bench"}
            for i in range(100)
        ]

        def compute_merkle():
            return merkle(receipts)

        result = benchmark(compute_merkle)
        assert result is not None

    def test_merkle_10000_receipts(self, benchmark):
        """Anchor 10000 receipts - stress test."""
        receipts = [
            {"receipt_type": "bench", "seq": i, "tenant_id": "bench"}
            for i in range(10000)
        ]

        def compute_merkle():
            return merkle(receipts)

        result = benchmark(compute_merkle)
        assert result is not None

    def test_merkle_incremental(self, benchmark):
        """Test incremental Merkle updates."""
        base_receipts = [
            {"receipt_type": "bench", "seq": i, "tenant_id": "bench"}
            for i in range(100)
        ]

        def add_and_recompute():
            extended = base_receipts + [{"receipt_type": "new", "seq": 100, "tenant_id": "bench"}]
            return merkle(extended)

        result = benchmark(add_and_recompute)
        assert result is not None


def manual_benchmark():
    """Manual benchmark for verification."""
    sizes = [100, 500, 1000, 5000, 10000]

    print("\nMerkle Anchor Benchmark")
    print("-" * 50)

    for size in sizes:
        receipts = [
            {"receipt_type": "bench", "seq": i, "tenant_id": "bench"}
            for i in range(size)
        ]

        # Warmup
        merkle(receipts[:10])

        # Timed run
        iterations = 10
        start = time.perf_counter()
        for _ in range(iterations):
            merkle(receipts)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        target = size  # 1ms per receipt target
        status = "PASS" if avg_ms < target else "FAIL"

        print(f"  {size:5d} receipts: {avg_ms:7.1f}ms (target <{target}ms) [{status}]")

    print("-" * 50)


if __name__ == "__main__":
    manual_benchmark()
