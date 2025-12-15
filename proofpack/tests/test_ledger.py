"""Tests for proofpack.ledger module."""
import time

import pytest

from proofpack.ledger import (
    ingest,
    batch_ingest,
    query_receipts,
    trace_lineage,
    compact,
    anchor_batch,
    generate_proof,
    verify_proof,
)
from proofpack.ledger.ingest import set_store as set_ingest_store
from proofpack.ledger.query import set_store as set_query_store
from proofpack.ledger.compact import set_store as set_compact_store
from proofpack.core.receipt import StopRule


class TestIngest:
    """Tests for ingest function."""

    def test_ingest_returns_receipt(self, temp_ledger, capsys):
        """ingest() returns dict with receipt_type='ingest'."""
        result = ingest(b"test_payload", "tenant1", store=temp_ledger)
        assert isinstance(result, dict)
        assert result["receipt_type"] == "ingest"

    def test_ingest_has_tenant_id(self, temp_ledger, capsys):
        """receipt['tenant_id'] == provided tenant_id."""
        result = ingest(b"test_payload", "tenant_a", store=temp_ledger)
        assert result["tenant_id"] == "tenant_a"

    def test_ingest_has_payload_hash(self, temp_ledger, capsys):
        """':' in receipt['payload_hash'] (dual-hash format)."""
        result = ingest(b"test_payload", "tenant1", store=temp_ledger)
        assert ":" in result["payload_hash"]
        parts = result["payload_hash"].split(":")
        assert len(parts[0]) == 64  # SHA256 hex

    def test_ingest_stores_receipt(self, temp_ledger, capsys):
        """After ingest, query_receipts() finds it."""
        ingest(b"test_payload", "tenant1", store=temp_ledger)
        set_query_store(temp_ledger)
        receipts = query_receipts(store=temp_ledger, tenant_id="tenant1")
        assert len(receipts) == 1
        assert receipts[0]["receipt_type"] == "ingest"

    def test_ingest_slo_latency(self, temp_ledger, capsys):
        """ingest() completes in <= 50ms (p95 target)."""
        start = time.perf_counter()
        ingest(b"test_payload", "tenant1", store=temp_ledger)
        elapsed_ms = (time.perf_counter() - start) * 1000
        # SLO target is 50ms, hard limit is 100ms
        assert elapsed_ms <= 50, f"Latency {elapsed_ms:.2f}ms exceeds 50ms SLO"

    def test_ingest_tenant_isolation(self, temp_ledger, capsys):
        """Ingests are isolated by tenant_id."""
        ingest(b"payload1", "tenant1", store=temp_ledger)
        ingest(b"payload2", "tenant2", store=temp_ledger)

        tenant1_receipts = query_receipts(store=temp_ledger, tenant_id="tenant1")
        tenant2_receipts = query_receipts(store=temp_ledger, tenant_id="tenant2")

        assert len(tenant1_receipts) == 1
        assert len(tenant2_receipts) == 1
        assert tenant1_receipts[0]["tenant_id"] == "tenant1"
        assert tenant2_receipts[0]["tenant_id"] == "tenant2"


class TestBatchIngest:
    """Tests for batch_ingest function."""

    def test_batch_ingest_count(self, temp_ledger, capsys):
        """batch_ingest(10 items) returns 10 receipts."""
        payloads = [f"payload_{i}".encode() for i in range(10)]
        results = batch_ingest(payloads, "tenant1", store=temp_ledger)
        assert len(results) == 10

    def test_batch_ingest_all_stored(self, temp_ledger, capsys):
        """All batch items are stored."""
        payloads = [f"payload_{i}".encode() for i in range(5)]
        batch_ingest(payloads, "tenant1", store=temp_ledger)
        receipts = query_receipts(store=temp_ledger, tenant_id="tenant1")
        assert len(receipts) == 5


class TestQueryReceipts:
    """Tests for query_receipts function."""

    def test_query_by_tenant(self, temp_ledger, capsys):
        """query_receipts(tenant_id=X) returns only X's receipts."""
        ingest(b"payload1", "tenant_a", store=temp_ledger)
        ingest(b"payload2", "tenant_b", store=temp_ledger)
        ingest(b"payload3", "tenant_a", store=temp_ledger)

        results = query_receipts(store=temp_ledger, tenant_id="tenant_a")
        assert len(results) == 2
        assert all(r["tenant_id"] == "tenant_a" for r in results)

    def test_query_by_type(self, temp_ledger, capsys):
        """query_receipts(receipt_type='ingest') filters correctly."""
        ingest(b"payload1", "tenant1", store=temp_ledger)
        results = query_receipts(store=temp_ledger, receipt_type="ingest")
        assert len(results) >= 1
        assert all(r["receipt_type"] == "ingest" for r in results)

    def test_query_by_since(self, temp_ledger, capsys):
        """Only receipts after timestamp returned."""
        # Create receipts with different timestamps
        ingest(b"payload1", "tenant1", store=temp_ledger)
        time.sleep(0.01)
        cutoff_time = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"
        time.sleep(0.01)
        ingest(b"payload2", "tenant1", store=temp_ledger)
        ingest(b"payload3", "tenant1", store=temp_ledger)

        results = query_receipts(store=temp_ledger, since=cutoff_time, tenant_id="tenant1")
        # Should only get receipts after cutoff
        for r in results:
            assert r["ts"] >= cutoff_time

    def test_query_sorted_desc(self, temp_ledger, capsys):
        """First receipt has latest ts."""
        # Ingest with small delay to ensure different timestamps
        for i in range(3):
            ingest(f"payload_{i}".encode(), "tenant1", store=temp_ledger)
            time.sleep(0.01)

        results = query_receipts(store=temp_ledger, tenant_id="tenant1")
        timestamps = [r["ts"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)


class TestAnchorBatch:
    """Tests for anchor_batch function."""

    def test_anchor_batch_returns_receipt(self, capsys):
        """receipt['receipt_type'] == 'anchor'."""
        receipts = [{"data": i} for i in range(10)]
        result = anchor_batch(receipts, "tenant1")
        assert result["receipt_type"] == "anchor"

    def test_anchor_batch_has_merkle_root(self, capsys):
        """':' in receipt['merkle_root']."""
        receipts = [{"data": i} for i in range(10)]
        result = anchor_batch(receipts, "tenant1")
        assert ":" in result["merkle_root"]

    def test_anchor_batch_has_hash_algos(self, capsys):
        """receipt['hash_algos'] == ['SHA256', 'BLAKE3']."""
        receipts = [{"data": i} for i in range(10)]
        result = anchor_batch(receipts, "tenant1")
        assert result["hash_algos"] == ["SHA256", "BLAKE3"]

    def test_anchor_batch_batch_size(self, capsys):
        """receipt['batch_size'] == len(receipts)."""
        receipts = [{"data": i} for i in range(10)]
        result = anchor_batch(receipts, "tenant1")
        assert result["batch_size"] == 10

    def test_anchor_batch_slo(self, capsys):
        """elapsed_ms <= 1000 for 1000 receipts."""
        receipts = [{"data": i} for i in range(1000)]
        start = time.perf_counter()
        anchor_batch(receipts, "tenant1")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms <= 1000, f"Anchor batch took {elapsed_ms:.2f}ms, exceeds 1000ms SLO"


class TestVerifyProof:
    """Tests for generate_proof and verify_proof functions."""

    def test_verify_proof_valid(self, capsys):
        """verify_proof(item, proof, root) == True for valid proof."""
        items = [{"data": i} for i in range(10)]
        item = items[3]

        proof = generate_proof(item, items)
        root = proof["root"]

        assert verify_proof(item, proof, root) is True

    def test_verify_proof_invalid(self, capsys):
        """verify_proof(modified_item, proof, root) == False."""
        items = [{"data": i} for i in range(10)]
        item = items[3]

        proof = generate_proof(item, items)
        root = proof["root"]

        # Modify the item
        modified_item = {"data": 999}

        assert verify_proof(modified_item, proof, root) is False


class TestTraceLineage:
    """Tests for trace_lineage function."""

    def test_trace_lineage_returns_list(self, temp_ledger, capsys):
        """isinstance(result, list)."""
        ingest(b"test_payload", "tenant1", store=temp_ledger)
        receipts = query_receipts(store=temp_ledger, tenant_id="tenant1")
        receipt_id = receipts[0]["payload_hash"]

        result = trace_lineage(temp_ledger, receipt_id)
        assert isinstance(result, list)

    def test_trace_lineage_finds_receipt(self, temp_ledger, capsys):
        """trace_lineage returns receipt for existing payload_hash."""
        receipt = ingest(b"test_payload", "tenant1", store=temp_ledger)
        receipt_id = receipt["payload_hash"]

        result = trace_lineage(temp_ledger, receipt_id)
        assert len(result) >= 1
        assert result[0]["payload_hash"] == receipt_id

    def test_trace_lineage_not_found(self, temp_ledger, capsys):
        """trace_lineage returns empty list for nonexistent hash."""
        result = trace_lineage(temp_ledger, "nonexistent:hash")
        assert result == []


class TestCompact:
    """Tests for compact function."""

    def test_compact_hash_continuity(self, temp_ledger, capsys):
        """compact() emits receipt with hash_continuity=True."""
        # Ingest some data
        for i in range(5):
            ingest(f"payload_{i}".encode(), "tenant1", store=temp_ledger)

        # Compact all data (use future timestamp)
        result = compact("9999-12-31T23:59:59Z", "tenant1", store=temp_ledger)
        assert result["hash_continuity"] is True

    def test_compact_counts(self, temp_ledger, capsys):
        """compact() tracks counts before and after."""
        for i in range(3):
            ingest(f"payload_{i}".encode(), "tenant1", store=temp_ledger)

        result = compact("9999-12-31T23:59:59Z", "tenant1", store=temp_ledger)
        assert result["counts"]["before"] == 3
        # After compaction, should have fewer receipts (rolled up)
        assert result["counts"]["after"] <= result["counts"]["before"]

    def test_compact_empty_tenant(self, temp_ledger, capsys):
        """compact() handles tenant with no receipts."""
        result = compact("9999-12-31T23:59:59Z", "empty_tenant", store=temp_ledger)
        assert result["counts"]["before"] == 0
        assert result["counts"]["after"] == 0
        assert result["hash_continuity"] is True

    def test_compact_stoprule_on_violation(self, temp_ledger, capsys):
        """pytest.raises(StopRule) when invariant violated."""
        from proofpack.ledger.compact import verify_invariants

        fake_receipt = {
            "counts": {"before": 5, "after": 10},  # Invalid: after > before
            "hash_continuity": True,
        }
        with pytest.raises(StopRule):
            verify_invariants(fake_receipt)

        fake_receipt2 = {
            "counts": {"before": 5, "after": 3},
            "hash_continuity": False,  # Invalid
        }
        with pytest.raises(StopRule):
            verify_invariants(fake_receipt2)
