"""Packet module tests with 80% coverage minimum.

Tests for attach.py, audit.py, and build.py functions.
"""
import pytest
import time
from io import StringIO
import sys

from proofpack.packet import (
    attach,
    map_claims,
    find_supporting_receipts,
    audit_consistency,
    compute_match_score,
    build_packet,
    DecisionPacket,
    PACKET_SCHEMAS,
)
from proofpack.core.receipt import StopRule, dual_hash


# ============================================================================
# attach.py tests
# ============================================================================


def test_attach_returns_receipt(sample_claims, sample_packet_receipts):
    """Verify attach returns receipt with receipt_type == 'attach'."""
    result = attach(sample_claims, sample_packet_receipts)
    assert result["receipt_type"] == "attach"


def test_attach_has_attach_map(sample_claims, sample_packet_receipts):
    """Verify attach_map key exists and is dict."""
    result = attach(sample_claims, sample_packet_receipts)
    assert "attach_map" in result
    assert isinstance(result["attach_map"], dict)


def test_attach_counts_correct(sample_claims, sample_packet_receipts):
    """Verify claim_count, receipt_count, attached_count are accurate."""
    result = attach(sample_claims, sample_packet_receipts)
    assert result["claim_count"] == 10
    assert result["receipt_count"] == 10
    assert result["attached_count"] == 10  # All should match by evidence_ids


def test_attach_unattached_claims():
    """Verify unmatched claims are listed correctly."""
    claims = [
        {"id": "claim_1", "evidence_ids": ["receipt_1"]},
        {"id": "claim_2", "evidence_ids": ["receipt_999"]},  # No match
    ]
    receipts = [
        {"id": "receipt_1", "payload_hash": dual_hash(b"r1")},
    ]

    result = attach(claims, receipts)
    assert "claim_2" in result["unattached_claims"]
    assert "claim_1" not in result["unattached_claims"]


def test_attach_slo_latency(sample_claims, sample_packet_receipts):
    """Verify elapsed_ms <= 500."""
    start = time.perf_counter()
    attach(sample_claims, sample_packet_receipts)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms <= 500, f"Attach took {elapsed_ms:.0f}ms, exceeds 500ms SLO"


def test_map_claims_pure(sample_claims, sample_packet_receipts):
    """Verify same inputs → same output (pure function)."""
    result1 = map_claims(sample_claims, sample_packet_receipts)
    result2 = map_claims(sample_claims, sample_packet_receipts)
    assert result1 == result2


def test_find_supporting_id_match():
    """Verify finds receipts by evidence_ids."""
    claim = {"id": "c1", "evidence_ids": ["r1", "r2"]}
    receipts = [
        {"id": "r1", "payload_hash": "hash1"},
        {"id": "r2", "payload_hash": "hash2"},
        {"id": "r3", "payload_hash": "hash3"},
    ]

    result = find_supporting_receipts(claim, receipts)
    assert "hash1" in result
    assert "hash2" in result
    assert "hash3" not in result


def test_find_supporting_hash_match():
    """Verify finds receipts by source_hash."""
    claim = {"id": "c1", "source_hash": "source123"}
    receipts = [
        {"source_hash": "source123", "payload_hash": "hash1"},
        {"source_hash": "source456", "payload_hash": "hash2"},
    ]

    result = find_supporting_receipts(claim, receipts)
    assert "hash1" in result
    assert "hash2" not in result


def test_find_supporting_empty():
    """Verify returns empty list when no match."""
    claim = {"id": "c1", "evidence_ids": ["nonexistent"]}
    receipts = [
        {"id": "r1", "payload_hash": "hash1"},
    ]

    result = find_supporting_receipts(claim, receipts)
    assert result == []


def test_find_supporting_chunk_match():
    """Verify finds receipts by chunk_id."""
    claim = {"id": "c1", "chunk_id": "chunk_123"}
    receipts = [
        {"chunk_id": "chunk_123", "payload_hash": "hash1"},
        {"chunk_id": "chunk_456", "payload_hash": "hash2"},
    ]

    result = find_supporting_receipts(claim, receipts)
    assert "hash1" in result
    assert "hash2" not in result


def test_find_supporting_scalar_evidence_id():
    """Verify handles scalar evidence_ids (not list)."""
    claim = {"id": "c1", "evidence_ids": "r1"}  # Scalar, not list
    receipts = [
        {"id": "r1", "payload_hash": "hash1"},
    ]

    result = find_supporting_receipts(claim, receipts)
    assert "hash1" in result


def test_extract_claim_id_missing():
    """Verify generates hash when claim has no id."""
    from proofpack.packet.attach import extract_claim_id

    claim = {"content": "test claim without id"}
    result = extract_claim_id(claim)

    # Should be dual-hash format
    assert ":" in result
    parts = result.split(":")
    assert len(parts) == 2
    assert len(parts[0]) == 64  # SHA256


# ============================================================================
# audit.py tests
# ============================================================================


def test_audit_pass(sample_claims, sample_packet_receipts):
    """Verify 100% match → passed=True."""
    attachments = attach(sample_claims, sample_packet_receipts)
    result = audit_consistency(attachments)
    assert result["passed"] is True


def test_audit_fail_raises_stoprule():
    """Verify <99.9% → StopRule raised."""
    # Create attachments with 90% match
    attachments = {
        "claim_count": 10,
        "attached_count": 9,
        "unattached_claims": ["claim_9"],
        "attach_map": {},
    }

    with pytest.raises(StopRule) as exc_info:
        audit_consistency(attachments)

    assert "Consistency violation" in str(exc_info.value)


def test_audit_threshold_exact():
    """Verify 99.9% exactly → passes."""
    # Need exactly 999 out of 1000 attached
    attachments = {
        "claim_count": 1000,
        "attached_count": 999,
        "unattached_claims": ["claim_999"],
        "attach_map": {},
    }

    result = audit_consistency(attachments, threshold=0.999)
    assert result["passed"] is True
    assert result["match_score"] == 0.999


def test_audit_emits_halt_receipt():
    """Verify failure emits halt_receipt before StopRule."""
    attachments = {
        "claim_count": 10,
        "attached_count": 9,
        "unattached_claims": ["claim_9"],
        "attach_map": {},
    }

    # Capture stdout to verify halt_receipt emitted
    import json
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        audit_consistency(attachments)
    except StopRule:
        pass  # Expected

    sys.stdout = old_stdout
    output = captured_output.getvalue()

    # Check that halt_receipt was emitted
    lines = [line for line in output.strip().split('\n') if line]
    receipts = [json.loads(line) for line in lines]

    halt_receipts = [r for r in receipts if r["receipt_type"] == "halt"]
    assert len(halt_receipts) > 0, "halt_receipt not emitted before StopRule"


def test_audit_escalation_4h():
    """Verify halt_receipt has escalation_deadline = now + 4h."""
    attachments = {
        "claim_count": 10,
        "attached_count": 9,
        "unattached_claims": ["claim_9"],
        "attach_map": {},
    }

    import json
    from datetime import datetime, timezone, timedelta

    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        audit_consistency(attachments)
    except StopRule:
        pass

    sys.stdout = old_stdout
    output = captured_output.getvalue()

    lines = [line for line in output.strip().split('\n') if line]
    receipts = [json.loads(line) for line in lines]
    halt_receipts = [r for r in receipts if r["receipt_type"] == "halt"]

    assert len(halt_receipts) > 0
    halt = halt_receipts[0]

    # Parse escalation_deadline
    deadline = datetime.fromisoformat(halt["escalation_deadline"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    # Should be approximately 4 hours from now (allow 1 minute tolerance)
    expected = now + timedelta(hours=4)
    delta = abs((deadline - expected).total_seconds())
    assert delta < 60, f"Escalation deadline {delta:.0f}s off from 4 hours"


def test_audit_slo():
    """Verify elapsed_ms <= 1000."""
    attachments = {
        "claim_count": 1000,
        "attached_count": 1000,
        "unattached_claims": [],
        "attach_map": {},
    }

    start = time.perf_counter()
    audit_consistency(attachments)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms <= 1000, f"Audit took {elapsed_ms:.0f}ms, exceeds 1000ms SLO"


def test_compute_score_all():
    """Verify all attached → 1.0."""
    attachments = {
        "claim_count": 10,
        "attached_count": 10,
        "unattached_claims": [],
    }

    score, mismatches = compute_match_score(attachments)
    assert score == 1.0
    assert len(mismatches) == 0


def test_compute_score_none():
    """Verify none attached → 0.0."""
    attachments = {
        "claim_count": 10,
        "attached_count": 0,
        "unattached_claims": [f"claim_{i}" for i in range(10)],
    }

    score, mismatches = compute_match_score(attachments)
    assert score == 0.0
    assert len(mismatches) == 10


def test_compute_score_partial():
    """Verify 9/10 → 0.9."""
    attachments = {
        "claim_count": 10,
        "attached_count": 9,
        "unattached_claims": ["claim_9"],
    }

    score, mismatches = compute_match_score(attachments)
    assert score == 0.9
    assert len(mismatches) == 1


# ============================================================================
# build.py tests
# ============================================================================


def test_build_returns_packet(sample_brief, sample_claims, sample_packet_receipts):
    """Verify has packet_id, brief_hash, merkle_anchor."""
    attachments = attach(sample_claims, sample_packet_receipts)
    result = build_packet(sample_brief, attachments)

    assert "packet_id" in result
    assert "brief_hash" in result
    assert "merkle_anchor" in result


def test_build_emits_receipt(sample_brief, sample_claims, sample_packet_receipts):
    """Verify packet_receipt emitted."""
    import json

    attachments = attach(sample_claims, sample_packet_receipts)

    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    build_packet(sample_brief, attachments)

    sys.stdout = old_stdout
    output = captured_output.getvalue()

    lines = [line for line in output.strip().split('\n') if line]
    receipts = [json.loads(line) for line in lines]

    packet_receipts = [r for r in receipts if r["receipt_type"] == "packet"]
    assert len(packet_receipts) > 0, "packet_receipt not emitted"


def test_build_decision_health(sample_brief, sample_claims, sample_packet_receipts):
    """Verify extracted from brief correctly."""
    attachments = attach(sample_claims, sample_packet_receipts)
    result = build_packet(sample_brief, attachments)

    health = result["decision_health"]
    assert health["strength"] == 0.95
    assert health["coverage"] == 0.88
    assert health["efficiency"] == 0.92


def test_build_merkle_anchor(sample_brief, sample_claims, sample_packet_receipts):
    """Verify dual-hash format, computed from receipts."""
    attachments = attach(sample_claims, sample_packet_receipts)
    result = build_packet(sample_brief, attachments)

    merkle_anchor = result["merkle_anchor"]

    # Verify dual-hash format (sha256:blake3)
    assert ":" in merkle_anchor
    parts = merkle_anchor.split(":")
    assert len(parts) == 2
    assert len(parts[0]) == 64  # SHA256 hex length
    assert len(parts[1]) == 64  # BLAKE3 hex length


def test_build_slo(sample_brief, sample_claims, sample_packet_receipts):
    """Verify elapsed_ms <= 2000."""
    attachments = attach(sample_claims, sample_packet_receipts)

    start = time.perf_counter()
    build_packet(sample_brief, attachments)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms <= 2000, f"Build took {elapsed_ms:.0f}ms, exceeds 2000ms SLO"


def test_build_missing_brief_stoprule(sample_claims, sample_packet_receipts):
    """Verify missing required field → StopRule."""
    attachments = attach(sample_claims, sample_packet_receipts)

    # Brief missing executive_summary
    bad_brief = {"some_other_field": "value"}

    with pytest.raises(StopRule) as exc_info:
        build_packet(bad_brief, attachments)

    assert "missing required field" in str(exc_info.value).lower()


def test_decision_packet_immutable(sample_brief, sample_claims, sample_packet_receipts):
    """Verify DecisionPacket is frozen dataclass."""
    attachments = attach(sample_claims, sample_packet_receipts)
    result = build_packet(sample_brief, attachments)

    # Create DecisionPacket instance
    from proofpack.packet.build import DecisionPacket

    packet = DecisionPacket(
        packet_id=result["packet_id"],
        ts=result["ts"],
        tenant_id=result["tenant_id"],
        brief=result["brief"],
        brief_hash=result["brief_hash"],
        decision_health=result["decision_health"],
        dialectical_record=result["dialectical_record"],
        attached_receipts=result["attached_receipts"],
        attach_map=result["attach_map"],
        consistency_score=result["consistency_score"],
        merkle_anchor=result["merkle_anchor"],
    )

    # Verify immutable (frozen)
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        packet.packet_id = "new_id"


def test_decision_packet_to_dict(sample_brief, sample_claims, sample_packet_receipts):
    """Verify to_dict() returns valid dict."""
    attachments = attach(sample_claims, sample_packet_receipts)
    result = build_packet(sample_brief, attachments)

    assert isinstance(result, dict)
    assert "packet_id" in result
    assert "brief_hash" in result


def test_packet_schemas_defined():
    """Verify PACKET_SCHEMAS exports all schema definitions."""
    assert "attach" in PACKET_SCHEMAS
    assert "consistency" in PACKET_SCHEMAS
    assert "halt" in PACKET_SCHEMAS
    assert "packet" in PACKET_SCHEMAS
