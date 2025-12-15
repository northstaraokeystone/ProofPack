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


@pytest.fixture
def sample_claims():
    """Provide 10 claims with ids and evidence_ids fields."""
    claims = []
    for i in range(10):
        claims.append({
            "id": f"claim_{i}",
            "evidence_ids": [f"receipt_{i}"],
            "content": f"This is claim number {i}",
        })
    return claims


@pytest.fixture
def sample_packet_receipts():
    """Provide 10 receipts with payload_hash and id fields matching claims."""
    receipts = []
    for i in range(10):
        receipts.append({
            "id": f"receipt_{i}",
            "receipt_type": "ingest",
            "ts": f"2024-01-{i+1:02d}T00:00:00Z",
            "tenant_id": "test_tenant",
            "payload_hash": dual_hash(f"payload_{i}".encode()),
            "source_type": "test",
        })
    return receipts


@pytest.fixture
def sample_brief():
    """Provide brief with executive_summary, decision_health, dialectical fields."""
    return {
        "executive_summary": "This is a test decision summary.",
        "decision_health": {
            "strength": 0.95,
            "coverage": 0.88,
            "efficiency": 0.92,
        },
        "dialectical_record": {
            "pro": ["Pro argument 1", "Pro argument 2"],
            "con": ["Con argument 1"],
            "gaps": ["Gap 1"],
        },
    }


# Detect module fixtures

@pytest.fixture
def sample_receipts_for_scan():
    """Provide 100 receipts with various field values for scanning."""
    receipts = []
    for i in range(100):
        receipts.append({
            "receipt_type": "ingest",
            "ts": f"2024-01-{(i % 28) + 1:02d}T{i % 24:02d}:00:00Z",
            "tenant_id": "test_tenant",
            "payload_hash": dual_hash(f"scan_payload_{i}".encode()),
            "latency_ms": 50 + (i % 100),  # Values 50-149
            "error_count": i % 5,  # Values 0-4
            "status": "success" if i % 10 != 0 else "failure",
            "source_type": "api" if i % 3 == 0 else "batch",
        })
    return receipts


@pytest.fixture
def sample_patterns():
    """Provide 5 patterns covering each classification type."""
    return [
        {
            "id": "threshold_breach_latency",
            "type": "threshold_breach",
            "conditions": [
                {"field": "latency_ms", "operator": "gt", "value": 100}
            ]
        },
        {
            "id": "trend_change_errors",
            "type": "trend_change",
            "conditions": [
                {"field": "error_count", "operator": "gt", "value": 2}
            ]
        },
        {
            "id": "performance_drop_status",
            "type": "performance_drop",
            "conditions": [
                {"field": "status", "operator": "eq", "value": "failure"}
            ]
        },
        {
            "id": "unexpected_value_source",
            "type": "unexpected_value",
            "conditions": [
                {"field": "source_type", "operator": "eq", "value": "unknown"}
            ]
        },
        {
            "id": "code_smell_empty",
            "type": "code_smell",
            "conditions": [
                {"field": "payload_hash", "operator": "contains", "value": "empty"}
            ]
        },
    ]


@pytest.fixture
def sample_baseline():
    """Provide baseline dict with known metric value."""
    return {
        "metric": "latency_ms",
        "baseline_value": 75.0,
        "sample_size": 100,
        "computed_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def drifting_receipts():
    """Provide receipts with values 20% above baseline."""
    receipts = []
    baseline_value = 75.0
    drifted_value = baseline_value * 1.2  # 20% above
    for i in range(20):
        receipts.append({
            "receipt_type": "ingest",
            "ts": f"2024-01-{i + 1:02d}T00:00:00Z",
            "tenant_id": "test_tenant",
            "payload_hash": dual_hash(f"drift_payload_{i}".encode()),
            "latency_ms": drifted_value + (i % 5 - 2),  # Slight variation around 90
        })
    return receipts
