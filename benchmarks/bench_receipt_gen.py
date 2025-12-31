"""Benchmark: Receipt generation latency.

Target SLO: <50ms per receipt generation.
"""
import time

from proofpack.core.receipt import dual_hash, emit_receipt


class TestReceiptGenerationLatency:
    """Benchmark receipt generation performance."""

    def test_single_receipt_latency(self, benchmark):
        """Single receipt should generate in <50ms."""
        def generate_receipt():
            return emit_receipt("benchmark", {
                "tenant_id": "bench",
                "operation": "test",
                "value": 42,
            })

        result = benchmark(generate_receipt)
        assert result is not None
        assert "payload_hash" in result

    def test_dual_hash_latency(self, benchmark):
        """Dual hash should complete in <5ms."""
        data = b"benchmark data for hashing" * 100

        def compute_hash():
            return dual_hash(data)

        result = benchmark(compute_hash)
        assert ":" in result  # SHA256:BLAKE3 format

    def test_receipt_with_payload_latency(self, benchmark):
        """Receipt with 1KB payload should still be <50ms."""
        payload = {"data": "x" * 1024}

        def generate_with_payload():
            return emit_receipt("benchmark_payload", {
                "tenant_id": "bench",
                "payload": payload,
            })

        result = benchmark(generate_with_payload)
        assert result is not None

    def test_throughput_100_receipts(self, benchmark):
        """Generate 100 receipts, measure throughput."""
        def generate_batch():
            receipts = []
            for i in range(100):
                r = emit_receipt("benchmark_batch", {
                    "tenant_id": "bench",
                    "sequence": i,
                })
                receipts.append(r)
            return receipts

        result = benchmark(generate_batch)
        assert len(result) == 100


# Manual timing for non-pytest runs
def manual_benchmark():
    """Run manual timing for quick verification."""
    iterations = 1000

    # Warmup
    for _ in range(100):
        emit_receipt("warmup", {"tenant_id": "bench"})

    # Timed run
    start = time.perf_counter()
    for i in range(iterations):
        emit_receipt("manual_bench", {"tenant_id": "bench", "seq": i})
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / iterations) * 1000
    throughput = iterations / elapsed

    print("\nReceipt Generation Benchmark")
    print(f"  Iterations: {iterations}")
    print(f"  Total time: {elapsed:.3f}s")
    print(f"  Avg per receipt: {avg_ms:.2f}ms")
    print(f"  Throughput: {throughput:.0f} receipts/sec")
    print(f"  SLO (<50ms): {'PASS' if avg_ms < 50 else 'FAIL'}")

    return avg_ms < 50


if __name__ == "__main__":
    manual_benchmark()
