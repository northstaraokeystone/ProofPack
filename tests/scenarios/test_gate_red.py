"""Test gate RED decision path.

Pass criteria:
- Confidence <0.7 results in RED decision
- Execution blocked
- block_receipt emitted
- Human approval required
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from proofpack.core.constants import GATE_YELLOW_THRESHOLD
from proofpack.gate.decision import GateDecision, gate_decision


class TestGateRed:
    """Test gate RED decision path."""

    def test_low_confidence_blocked(self):
        """RED: Low confidence action is blocked."""
        confidence = 0.55  # Below YELLOW threshold

        result, receipt = gate_decision(
            confidence,
            action_id="test_action_red_001",
            context_drift=0.4,
            reasoning_entropy=0.5
        )

        assert result.decision == GateDecision.RED, \
            f"Expected RED, got {result.decision}"
        assert result.requires_approval is True, \
            "RED should require approval"
        assert result.blocked_at is not None, \
            "RED should have blocked_at timestamp"

    def test_red_emits_block_receipt(self):
        """RED: block_receipt emitted with correct fields."""
        confidence = 0.45

        result, receipt = gate_decision(
            confidence,
            action_id="test_action_red_002"
        )

        assert receipt["receipt_type"] == "block"
        assert receipt["requires_approval"] is True
        assert "blocked_at" in receipt
        assert "reason" in receipt
        assert "action_id" in receipt

    def test_red_boundary_condition(self):
        """RED: Just below YELLOW threshold is RED."""
        confidence = GATE_YELLOW_THRESHOLD - 0.001  # 0.699

        result, _ = gate_decision(confidence, action_id="test_boundary_red")

        assert result.decision == GateDecision.RED, \
            f"Expected RED at boundary, got {result.decision}"

    def test_red_very_low_confidence(self):
        """RED: Very low confidence (0.1) is definitely blocked."""
        confidence = 0.1

        result, receipt = gate_decision(
            confidence,
            action_id="test_very_low"
        )

        assert result.decision == GateDecision.RED
        assert "confidence_score 0.1" in receipt.get("reason", "")

    def test_red_zero_confidence(self):
        """RED: Zero confidence is blocked."""
        confidence = 0.0

        result, _ = gate_decision(confidence, action_id="test_zero")

        assert result.decision == GateDecision.RED
        assert result.requires_approval is True

    def test_red_includes_drift_in_decision(self):
        """RED: High drift contributes to blocking decision."""
        # Even with moderate base confidence, high drift should affect
        confidence = 0.5
        high_drift = 0.8

        result, receipt = gate_decision(
            confidence,
            action_id="test_high_drift",
            context_drift=high_drift
        )

        assert result.decision == GateDecision.RED
        assert result.context_drift == high_drift

    def test_red_requires_approval_flag(self):
        """RED: requires_approval is True for all RED decisions."""
        for conf in [0.1, 0.3, 0.5, 0.69]:
            result, _ = gate_decision(conf, action_id=f"test_approval_{conf}")
            assert result.requires_approval is True, \
                f"requires_approval should be True for confidence {conf}"
