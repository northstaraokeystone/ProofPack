"""SLO verification tests for qed_bridge module.

Tests cover:
- Hook validation and tenant mapping
- Single window ingestion
- Batch window ingestion with anchoring
- Manifest parsing and linkage
- Integrity validation
- SLO timing requirements
"""
import json
import time

import pytest

from proofpack.core.receipt import StopRule, dual_hash
from proofpack.qed_bridge import (
    HOOK_TENANT_MAP,
    VALID_HOOKS,
    batch_windows,
    extract_window_metrics,
    ingest_qed_output,
    link_to_receipts,
    parse_manifest,
    validate_hook,
    validate_manifest_integrity,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_qed_window():
    """Return valid QED window dict with data, score, safety_events."""
    return {
        "data": [1, 2, 3, 4, 5],
        "score": 0.999,
        "safety_events": 2,
        "compression_ratio": 10.5,
        "classification": "normal",
    }


@pytest.fixture
def mock_qed_window_unsafe():
    """Return QED window with low recall score and safety events."""
    return {
        "data": [1, 2, 3],
        "score": 0.95,  # Below 0.999 threshold
        "safety_events": 5,  # Has safety events
        "compression_ratio": 8.0,
    }


@pytest.fixture
def mock_qed_manifest(tmp_path):
    """Return valid manifest dict and write to temp file."""
    manifest = {
        "window_counts": 100,
        "avg_compression": 10.0,
        "estimated_savings": 5000.0,
        "dataset_checksum": "abc123",
        "hook": "tesla",
        "run_id": "run_001",
        "ts": "2024-01-15T10:00:00Z",
    }
    manifest_path = tmp_path / "qed_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    return manifest, str(manifest_path)


@pytest.fixture
def mock_ledger_query():
    """Return callable that simulates ledger.query_receipts()."""
    def query_fn(receipt_type: str, tenant_id: str | None = None) -> list[dict]:
        # Return 100 mock receipts
        receipts = []
        for i in range(100):
            receipts.append({
                "receipt_type": receipt_type,
                "tenant_id": tenant_id or "tesla-automotive",
                "payload_hash": dual_hash(f"payload_{i}"),
                "window_hash": dual_hash(f"window_{i}"),
                "compression_ratio": 10.0 + (i % 5) * 0.1,
            })
        return receipts
    return query_fn


@pytest.fixture
def mock_ledger_query_partial():
    """Return callable that returns fewer receipts than expected."""
    def query_fn(receipt_type: str, tenant_id: str | None = None) -> list[dict]:
        # Return only 95 receipts (5% missing)
        receipts = []
        for i in range(95):
            receipts.append({
                "receipt_type": receipt_type,
                "tenant_id": tenant_id or "tesla-automotive",
                "payload_hash": dual_hash(f"payload_{i}"),
                "compression_ratio": 10.0,
            })
        return receipts
    return query_fn


# ============================================================================
# Hook Validation Tests
# ============================================================================


def test_validate_hook_valid():
    """Test that valid hooks pass validation."""
    for hook in VALID_HOOKS:
        result = validate_hook(hook)
        assert result == hook


def test_validate_hook_invalid_raises_stoprule():
    """Test that invalid hook triggers stoprule."""
    with pytest.raises(StopRule) as exc_info:
        validate_hook("invalid_hook")
    assert "Invalid hook" in str(exc_info.value)
    assert "invalid_hook" in str(exc_info.value)


def test_hook_tenant_mapping():
    """Test that HOOK_TENANT_MAP has expected mappings."""
    expected = {
        "tesla": "tesla-automotive",
        "spacex": "spacex-aerospace",
        "starlink": "starlink-constellation",
        "boring": "boring-infrastructure",
        "neuralink": "neuralink-medical",
        "xai": "xai-research",
    }
    assert HOOK_TENANT_MAP == expected


# ============================================================================
# Single Window Ingestion Tests
# ============================================================================


def test_ingest_single_window(mock_qed_window):
    """Test ingest_qed_output produces valid qed_window_receipt."""
    receipt = ingest_qed_output(mock_qed_window, "tesla")

    assert receipt["receipt_type"] == "qed_window"
    assert receipt["tenant_id"] == "tesla-automotive"
    assert ":" in receipt["window_hash"]  # dual_hash format
    assert receipt["hook"] == "tesla"
    assert receipt["compression_ratio"] == 10.5
    assert receipt["recall_score"] == 0.999
    assert receipt["safety_events"] == 2


def test_ingest_maps_hook_to_tenant(mock_qed_window):
    """Test that each hook maps correctly to tenant_id."""
    for hook, expected_tenant in HOOK_TENANT_MAP.items():
        receipt = ingest_qed_output(mock_qed_window, hook)
        assert receipt["tenant_id"] == expected_tenant


def test_ingest_invalid_hook_raises_stoprule(mock_qed_window):
    """Test that invalid hook raises StopRule."""
    with pytest.raises(StopRule):
        ingest_qed_output(mock_qed_window, "invalid")


def test_recall_violation_stoprule(mock_qed_window_unsafe):
    """Test that recall_score < 0.999 triggers stoprule for safety window."""
    # Window has safety_events > 0 and score < 0.999
    with pytest.raises(StopRule) as exc_info:
        ingest_qed_output(mock_qed_window_unsafe, "tesla")
    assert "Recall score" in str(exc_info.value)
    assert "0.95" in str(exc_info.value)


def test_dual_hash_format(mock_qed_window):
    """Test that all hashes use dual_hash format (contains ':')."""
    receipt = ingest_qed_output(mock_qed_window, "tesla")
    assert ":" in receipt["window_hash"]
    assert ":" in receipt["payload_hash"]


def test_extract_window_metrics_defaults():
    """Test extract_window_metrics provides defaults for missing fields."""
    window = {"data": [1, 2, 3]}  # Minimal window
    metrics = extract_window_metrics(window)

    assert metrics["compression_ratio"] == 1.0
    assert metrics["recall_score"] == 0.999
    assert metrics["safety_events"] == 0
    assert metrics["classification"] == "normal"


# ============================================================================
# Batch Window Tests
# ============================================================================


def test_batch_windows_anchors(mock_qed_window):
    """Test batch_windows computes merkle root."""
    windows = [mock_qed_window.copy() for _ in range(5)]

    receipt = batch_windows(windows, "spacex")

    assert receipt["receipt_type"] == "qed_batch"
    assert ":" in receipt["merkle_root"]  # dual_hash format
    assert receipt["batch_size"] == 5
    assert len(receipt["window_hashes"]) == 5
    assert receipt["tenant_id"] == "spacex-aerospace"


def test_batch_windows_slo():
    """Test batch of 100 windows completes in <= 1s."""
    windows = [
        {"data": [i], "score": 0.999, "safety_events": 0}
        for i in range(100)
    ]

    t0 = time.time()
    batch_windows(windows, "starlink")
    elapsed = time.time() - t0

    assert elapsed <= 1.0, f"Batch took {elapsed}s, SLO is 1s"


def test_batch_windows_aggregates_metrics(mock_qed_window):
    """Test batch receipt aggregates safety events and compression."""
    windows = []
    for i in range(10):
        w = mock_qed_window.copy()
        w["safety_events"] = i
        w["compression_ratio"] = 5.0 + i
        windows.append(w)

    receipt = batch_windows(windows, "boring")

    assert receipt["total_safety_events"] == sum(range(10))
    expected_avg = sum(5.0 + i for i in range(10)) / 10
    assert abs(receipt["avg_compression_ratio"] - expected_avg) < 0.01


# ============================================================================
# Manifest Parsing Tests
# ============================================================================


def test_parse_manifest_valid(mock_qed_manifest):
    """Test valid manifest parses and emits receipt."""
    manifest, path = mock_qed_manifest

    result = parse_manifest(path)

    assert "manifest_hash" in result
    assert ":" in result["manifest_hash"]  # dual_hash format
    assert result["window_counts"] == 100
    assert result["hook"] == "tesla"
    assert result["run_id"] == "run_001"


def test_parse_manifest_missing_field(tmp_path):
    """Test missing required field raises stoprule."""
    # Create manifest missing run_id
    incomplete = {
        "window_counts": 100,
        "avg_compression": 10.0,
        "estimated_savings": 5000.0,
        "dataset_checksum": "abc123",
        "hook": "tesla",
        "ts": "2024-01-15T10:00:00Z",
        # Missing run_id
    }
    path = tmp_path / "incomplete_manifest.json"
    path.write_text(json.dumps(incomplete))

    with pytest.raises(StopRule) as exc_info:
        parse_manifest(str(path))
    assert "Missing required fields" in str(exc_info.value)


def test_parse_manifest_invalid_hook(tmp_path):
    """Test invalid hook in manifest raises stoprule."""
    manifest = {
        "window_counts": 100,
        "avg_compression": 10.0,
        "estimated_savings": 5000.0,
        "dataset_checksum": "abc123",
        "hook": "invalid_hook",
        "run_id": "run_001",
        "ts": "2024-01-15T10:00:00Z",
    }
    path = tmp_path / "bad_hook_manifest.json"
    path.write_text(json.dumps(manifest))

    with pytest.raises(StopRule):
        parse_manifest(str(path))


# ============================================================================
# Linkage Tests
# ============================================================================


def test_link_to_receipts_coverage(mock_qed_manifest, mock_ledger_query):
    """Test linkage computes coverage ratio."""
    manifest, path = mock_qed_manifest
    parsed = parse_manifest(path)

    linkages = link_to_receipts(parsed, mock_ledger_query)

    assert len(linkages) == 100  # mock returns 100 receipts
    # Manifest expects 100, query returns 100
    # Coverage should be 100/100 = 1.0


def test_link_to_receipts_gaps(mock_qed_manifest, mock_ledger_query_partial):
    """Test linkage identifies gaps when receipts missing."""
    manifest, path = mock_qed_manifest
    parsed = parse_manifest(path)

    linkages = link_to_receipts(parsed, mock_ledger_query_partial)

    # Manifest expects 100, query returns 95
    assert len(linkages) == 95


# ============================================================================
# Integrity Check Tests
# ============================================================================


def test_integrity_check_pass(mock_qed_manifest):
    """Test matching manifest and receipts pass."""
    manifest, path = mock_qed_manifest
    parsed = parse_manifest(path)

    # Create receipts that match manifest exactly
    receipts = []
    for i in range(100):
        receipts.append({
            "compression_ratio": 10.0,  # Matches avg_compression
        })

    result = validate_manifest_integrity(parsed, receipts)

    assert result["status"] == "pass"
    assert result["discrepancies"] == []


def test_integrity_check_fail_count_mismatch(mock_qed_manifest):
    """Test mismatched counts trigger stoprule when > 1%."""
    manifest, path = mock_qed_manifest
    parsed = parse_manifest(path)

    # Create only 90 receipts (10% mismatch, > 1% threshold)
    receipts = [{"compression_ratio": 10.0} for _ in range(90)]

    with pytest.raises(StopRule) as exc_info:
        validate_manifest_integrity(parsed, receipts)
    assert "integrity violation" in str(exc_info.value).lower()


def test_integrity_check_minor_count_mismatch_no_stoprule(mock_qed_manifest):
    """Test small count mismatch (< 1%) does not raise stoprule."""
    manifest, path = mock_qed_manifest
    parsed = parse_manifest(path)

    # Create 99 receipts (1% mismatch, at threshold)
    receipts = [{"compression_ratio": 10.0} for _ in range(99)]

    # Should not raise, just report fail status
    result = validate_manifest_integrity(parsed, receipts)
    assert result["status"] == "fail"
    assert len(result["discrepancies"]) > 0


# ============================================================================
# Dual Hash Format Tests
# ============================================================================


def test_all_hashes_dual_format(mock_qed_window, mock_qed_manifest):
    """Test all hash fields use dual_hash format."""
    # Window receipt
    window_receipt = ingest_qed_output(mock_qed_window, "tesla")
    assert ":" in window_receipt["window_hash"]
    assert ":" in window_receipt["payload_hash"]

    # Manifest receipt
    manifest, path = mock_qed_manifest
    parsed = parse_manifest(path)
    assert ":" in parsed["manifest_hash"]


# ============================================================================
# Edge Cases
# ============================================================================


def test_empty_batch():
    """Test batch_windows handles empty list."""
    receipt = batch_windows([], "tesla")

    assert receipt["batch_size"] == 0
    assert receipt["window_hashes"] == []
    assert receipt["avg_compression_ratio"] == 1.0  # Default


def test_window_without_safety_events_high_score_ok():
    """Test window without safety events doesn't trigger recall stoprule."""
    window = {
        "data": [1, 2, 3],
        "score": 0.5,  # Low score
        "safety_events": 0,  # But no safety events
    }

    # Should not raise despite low score (no safety events)
    receipt = ingest_qed_output(window, "xai")
    assert receipt["recall_score"] == 0.5
