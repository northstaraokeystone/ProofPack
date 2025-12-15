"""Pytest fixtures for ProofPack tests."""
import pytest
from datetime import datetime, timezone

from proofpack.ledger.store import LedgerStore
from proofpack.core.receipt import dual_hash


@pytest.fixture
def temp_ledger(tmp_path):
    """Provide temporary LedgerStore with tmp_path."""
    ledger_path = tmp_path / "test_receipts.jsonl"
    return LedgerStore(str(ledger_path))


@pytest.fixture
def sample_receipt():
    """Provide a valid ingest_receipt dict."""
    return {
        "receipt_type": "ingest",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant_id": "test_tenant",
        "payload_hash": dual_hash(b"test_payload"),
        "redactions": [],
        "source_type": "test",
    }


@pytest.fixture
def sample_receipts():
    """Provide list of 10 valid receipts."""
    receipts = []
    for i in range(10):
        receipts.append({
            "receipt_type": "ingest",
            "ts": f"2024-01-{i+1:02d}T00:00:00Z",
            "tenant_id": "test_tenant",
            "payload_hash": dual_hash(f"payload_{i}".encode()),
            "redactions": [],
            "source_type": "test",
        })
    return receipts


@pytest.fixture
def sample_tenants():
    """Provide list of tenant IDs for multi-tenant testing."""
    return ["tenant_a", "tenant_b", "tenant_c"]


@pytest.fixture
def tmp_ledger(tmp_path):
    """Alias for temp_ledger - temporary LedgerStore with tmp_path."""
    ledger_path = tmp_path / "test_receipts.jsonl"
    return LedgerStore(str(ledger_path))
