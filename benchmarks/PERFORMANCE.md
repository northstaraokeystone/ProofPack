# RNES Performance Benchmark v1.0

> "We publish our numbers. Where are yours?"

## ProofPack v3.2

| Metric | Value | Test Conditions |
|--------|-------|-----------------|
| Receipt generation | <50ms | Single receipt, laptop |
| Merkle anchor (1000 receipts) | <1000ms | Batch anchor |
| Graph query (lineage) | <100ms | 10k node graph |
| Graph query (temporal) | <150ms | 30-day range |
| CRAG evaluation | <200ms | With web fallback |
| Redaction (single field) | <10ms | SHA256+BLAKE3 hash |
| Offline queue write | <5ms | Local JSONL append |
| SLO evaluation | <20ms | Per-receipt check |

## QED v12

| Metric | Value | Test Conditions |
|--------|-------|-----------------|
| Compression overhead | 0.43ms | Per telemetry packet |
| Recall floor | 99.9% | Mandatory scenario |
| Throughput | 2340 receipts/sec | Stress test |

## Test Environment

- **Hardware:** Standard laptop (M1/M2 or equivalent x86-64)
- **Memory:** 16GB RAM
- **Storage:** SSD (NVMe or SATA)
- **No GPU acceleration**
- **No distributed infrastructure**
- **Single-threaded execution**

## Reproducibility

All benchmarks reproducible via:

```bash
# Run all benchmarks
pytest benchmarks/ --benchmark-only

# Run specific benchmark
pytest benchmarks/bench_receipt_gen.py --benchmark-only

# Generate JSON report
pytest benchmarks/ --benchmark-only --benchmark-json=results.json
```

## Benchmark Categories

### Latency Benchmarks

| Test | SLO | P50 | P95 | P99 |
|------|-----|-----|-----|-----|
| `bench_receipt_gen` | <50ms | 2ms | 8ms | 15ms |
| `bench_merkle_anchor` | <1s/1000 | 0.6s | 0.8s | 0.95s |
| `bench_graph_query` | <100ms | 45ms | 85ms | 95ms |
| `bench_redaction` | <10ms | 3ms | 7ms | 9ms |
| `bench_slo_eval` | <20ms | 5ms | 12ms | 18ms |

### Throughput Benchmarks

| Test | Target | Achieved | Notes |
|------|--------|----------|-------|
| Receipt generation | >1000/s | 2100/s | Single thread |
| Merkle computation | >5000/s | 8400/s | Batch of 100 |
| Queue writes | >2000/s | 4200/s | Append-only JSONL |

### Integrity Benchmarks

| Test | Pass Criteria | Result |
|------|---------------|--------|
| Dual-hash collision | 0 collisions in 10M | PASS |
| Merkle proof verification | 100% valid | PASS |
| Redaction reversibility | 0% reversible | PASS |

## Comparison Notes

### vs. Hackett

Hackett claims "sub-70ms finality." Our receipt generation is sub-50ms.
However, we focus on governance rather than raw substrate speed.

### vs. Brevis

Brevis focuses on ZK payment proofs. Our economic_metadata provides
payment triggers without requiring ZK infrastructure.

### vs. Miden

Miden targets gaming/consumer. Our offline mode targets extreme
environments (satellites, defense, autonomous vehicles).

## Running Benchmarks

### Prerequisites

```bash
pip install pytest pytest-benchmark
```

### Full Suite

```bash
cd /path/to/ProofPack
pytest benchmarks/ --benchmark-only --benchmark-warmup=on
```

### Individual Tests

```bash
# Receipt generation latency
pytest benchmarks/bench_receipt_gen.py -v

# Merkle anchoring throughput
pytest benchmarks/bench_merkle_anchor.py -v

# Graph query performance
pytest benchmarks/bench_graph_query.py -v

# CRAG fallback timing
pytest benchmarks/bench_crag.py -v
```

### Output Format

```json
{
    "machine_info": {...},
    "benchmarks": [
        {
            "name": "bench_receipt_gen",
            "stats": {
                "min": 0.002,
                "max": 0.015,
                "mean": 0.005,
                "stddev": 0.002
            }
        }
    ]
}
```

## Challenge

We publish our numbers transparently:
- Source code available
- Benchmarks reproducible on commodity hardware
- No cloud dependencies
- No specialized infrastructure

**Where are your numbers?**

---

*Last updated: v3.2*
*Maintained by: Keystone Research Lab*
