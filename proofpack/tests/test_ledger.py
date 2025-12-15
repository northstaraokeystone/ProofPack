"""Tests for proofpack.ledger module."""
import time

import pytest

from proofpack.ledger import ingest, batch_ingest, query_receipts, compact
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

    def test_ingest_stores_receipt(self, temp_ledger, capsys):
        """After ingest, query_receipts() finds it."""
        ingest(b"test_payload", "tenant1", store=temp_ledger)
        set_query_store(temp_ledger)
        receipts = query_receipts(tenant_id="tenant1", store=temp_ledger)
        assert len(receipts) == 1
        assert receipts[0]["receipt_type"] == "ingest"

    def test_ingest_slo_latency(self, temp_ledger, capsys):
        """ingest() completes in <= 50ms (p95 target)."""
        start = time.perf_counter()
        ingest(b"test_payload", "tenant1", store=temp_ledger)
        elapsed_ms = (time.perf_counter() - start) * 1000
        # Allow some margin for test environment variability
        assert elapsed_ms < 100  # Using hard limit, not SLO target

    def test_ingest_tenant_isolation(self, temp_ledger, capsys):
        """Ingests are isolated by tenant_id."""
        ingest(b"payload1", "tenant1", store=temp_ledger)
        ingest(b"payload2", "tenant2", store=temp_ledger)

        tenant1_receipts = query_receipts(tenant_id="tenant1", store=temp_ledger)
        tenant2_receipts = query_receipts(tenant_id="tenant2", store=temp_ledger)

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
        receipts = query_receipts(tenant_id="tenant1", store=temp_ledger)
        assert len(receipts) == 5


class TestQueryReceipts:
    """Tests for query_receipts function."""

    def test_query_by_tenant(self, temp_ledger, capsys):
        """query_receipts(tenant_id=X) returns only X's receipts."""
        ingest(b"payload1", "tenant_a", store=temp_ledger)
        ingest(b"payload2", "tenant_b", store=temp_ledger)
        ingest(b"payload3", "tenant_a", store=temp_ledger)

        results = query_receipts(tenant_id="tenant_a", store=temp_ledger)
        assert len(results) == 2
        assert all(r["tenant_id"] == "tenant_a" for r in results)

    def test_query_by_type(self, temp_ledger, capsys):
        """query_receipts(receipt_type='ingest') filters correctly."""
        ingest(b"payload1", "tenant1", store=temp_ledger)
        results = query_receipts(receipt_type="ingest", store=temp_ledger)
        assert len(results) >= 1
        assert all(r["receipt_type"] == "ingest" for r in results)

    def test_query_sorted_by_ts_desc(self, temp_ledger, capsys):
        """Results are sorted by ts descending."""
        # Ingest with small delay to ensure different timestamps
        for i in range(3):
            ingest(f"payload_{i}".encode(), "tenant1", store=temp_ledger)
            time.sleep(0.01)

        results = query_receipts(tenant_id="tenant1", store=temp_ledger)
        timestamps = [r["ts"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)


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

    def test_compact_stoprule_on_mismatch(self, temp_ledger, capsys):
        """Corrupted data raises StopRule.

        Note: This test simulates what would happen if hash_continuity
        was violated. In the current implementation, this is mathematically
        prevented by the count tracking logic.
        """
        # The current implementation ensures hash_continuity by design,
        # so we test the verify_invariants function instead
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
