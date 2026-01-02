"""Tests for unified proof.py module.

Validates that consolidated proof.py matches original module behavior
for BRIEF, PACKET, and DETECT modes.
"""
import pytest
from io import StringIO
from unittest.mock import patch


class TestProofBriefMode:
    """Tests for BRIEF mode operations."""

    def test_compose_evidence(self):
        """Test evidence composition."""
        from proof import proof, ProofMode

        with patch('sys.stdout', new=StringIO()):
            result = proof(ProofMode.BRIEF, {
                "operation": "compose",
                "evidence": ["chunk1", "chunk2", "chunk3"]
            })

        assert result["receipt_type"] == "brief"
        assert "executive_summary" in result
        assert result["evidence_count"] == 3

    def test_compose_empty_evidence_raises(self):
        """Test that empty evidence raises StopRule."""
        from proof import proof, ProofMode
        from core.receipt import StopRule

        with patch('sys.stdout', new=StringIO()):
            with pytest.raises(StopRule):
                proof(ProofMode.BRIEF, {
                    "operation": "compose",
                    "evidence": []
                })

    def test_retrieve_within_budget(self):
        """Test retrieval within budget constraints."""
        from proof import proof, ProofMode

        with patch('sys.stdout', new=StringIO()):
            result = proof(ProofMode.BRIEF, {
                "operation": "retrieve",
                "query": "find relevant evidence",
                "budget": {"tokens": 500, "ms": 1000}
            })

        assert result["receipt_type"] == "retrieval"
        assert result["k"] <= 5  # 500 tokens / 100 = 5 max

    def test_health_scoring(self):
        """Test brief health scoring."""
        from proof import proof, ProofMode

        brief = {
            "supporting_evidence": [
                {"chunk_id": "c1", "confidence": 0.9},
                {"chunk_id": "c2", "confidence": 0.85},
            ],
            "evidence_count": 10,
        }

        with patch('sys.stdout', new=StringIO()):
            result = proof(ProofMode.BRIEF, {
                "operation": "health",
                "brief": brief
            }, {"thresholds": {"min_strength": 0.5, "min_coverage": 0.5, "min_efficiency": 0.5}})

        assert result["receipt_type"] == "health"
        assert "strength" in result
        assert "coverage" in result

    def test_dialectic_analysis(self):
        """Test PRO/CON dialectic analysis."""
        from proof import proof, ProofMode

        with patch('sys.stdout', new=StringIO()):
            result = proof(ProofMode.BRIEF, {
                "operation": "dialectic",
                "evidence": ["e1", "e2", "e3", "e4"]
            })

        assert result["receipt_type"] == "dialectic"
        assert "pro" in result
        assert "con" in result
        assert "resolution_status" in result


class TestProofPacketMode:
    """Tests for PACKET mode operations."""

    def test_build_packet(self):
        """Test decision packet assembly."""
        from proof import proof, ProofMode

        brief = {
            "executive_summary": "Test summary",
            "strength": 0.9,
            "coverage": 0.8,
            "efficiency": 0.7,
        }
        receipts = [
            {"payload_hash": "abc123:def456"},
            {"payload_hash": "ghi789:jkl012"},
        ]

        with patch('sys.stdout', new=StringIO()):
            result = proof(ProofMode.PACKET, {
                "operation": "build",
                "brief": brief,
                "receipts": receipts
            })

        assert result["receipt_type"] == "packet"
        assert "packet_id" in result
        assert "merkle_anchor" in result
        assert result["receipt_count"] == 2

    def test_attach_claims(self):
        """Test claim-to-receipt mapping."""
        from proof import proof, ProofMode

        claims = [
            {"claim_id": "claim1", "text": "First claim"},
            {"claim_id": "claim2", "text": "Second claim"},
        ]
        receipts = [
            {"payload_hash": "abc123:def456"},
        ]

        with patch('sys.stdout', new=StringIO()):
            result = proof(ProofMode.PACKET, {
                "operation": "attach",
                "claims": claims,
                "receipts": receipts
            })

        assert result["receipt_type"] == "attach"
        assert "mappings" in result
        assert result["total_claims"] == 2


class TestProofDetectMode:
    """Tests for DETECT mode operations."""

    def test_scan_patterns(self):
        """Test pattern scanning."""
        from proof import proof, ProofMode

        receipts = [
            {"receipt_type": "test", "value": 100},
            {"receipt_type": "test", "value": 200},
        ]
        patterns = [
            {
                "id": "threshold_breach",
                "type": "threshold",
                "conditions": [
                    {"field": "value", "operator": "gt", "value": 150}
                ]
            }
        ]

        with patch('sys.stdout', new=StringIO()):
            result = proof(ProofMode.DETECT, {
                "operation": "scan",
                "receipts": receipts,
                "patterns": patterns
            })

        assert isinstance(result, list)

    def test_classify_match(self):
        """Test anomaly classification."""
        from proof import proof, ProofMode

        match = {
            "pattern_id": "threshold_breach_001",
            "confidence": 0.85,
            "matched_conditions": [{"field": "value", "operator": "gt", "value": 100}]
        }

        with patch('sys.stdout', new=StringIO()):
            result = proof(ProofMode.DETECT, {
                "operation": "classify",
                "match": match
            })

        assert result["receipt_type"] == "classify"
        assert result["classification"] == "violation"


class TestProofModeString:
    """Test that mode can be passed as string."""

    def test_brief_as_string(self):
        """Test BRIEF mode with string."""
        from proof import proof

        with patch('sys.stdout', new=StringIO()):
            result = proof("BRIEF", {
                "operation": "compose",
                "evidence": ["test"]
            })

        assert result["receipt_type"] == "brief"

    def test_invalid_mode_raises(self):
        """Test that invalid mode raises ValueError."""
        from proof import proof

        with pytest.raises(ValueError):
            proof("INVALID_MODE", {})


class TestBackwardCompatibility:
    """Test backward-compatible wrapper functions."""

    def test_compose_wrapper(self):
        """Test compose() wrapper."""
        from proof import compose

        with patch('sys.stdout', new=StringIO()):
            result = compose(["e1", "e2"])

        assert result["receipt_type"] == "brief"

    def test_build_packet_wrapper(self):
        """Test build_packet() wrapper."""
        from proof import build_packet

        with patch('sys.stdout', new=StringIO()):
            result = build_packet({"executive_summary": "test"}, [])

        assert result["receipt_type"] == "packet"
