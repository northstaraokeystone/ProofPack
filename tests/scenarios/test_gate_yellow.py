"""Test gate YELLOW decision path.

Pass criteria:
- Confidence 0.7-0.9 results in YELLOW decision
- Execution proceeds with watchers spawned
- gate_decision receipt emitted
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from proofpack.core.constants import GATE_GREEN_THRESHOLD, GATE_YELLOW_THRESHOLD
from proofpack.gate.decision import GateDecision, gate_decision


class TestGateYellow:
    """Test gate YELLOW decision path."""

    def test_medium_confidence_yellow(self):
        """YELLOW: Medium confidence results in YELLOW decision."""
        confidence = 0.82  # Between YELLOW (0.7) and GREEN (0.9)

        result, receipt = gate_decision(
            confidence,
            action_id="test_action_yellow_001",
            context_drift=0.15,
            reasoning_entropy=0.2
        )

        assert result.decision == GateDecision.YELLOW, \
            f"Expected YELLOW, got {result.decision}"

    def test_yellow_executes_but_watched(self):
        """YELLOW: Execution proceeds but with monitoring."""
        confidence = 0.75

        result, receipt = gate_decision(
            confidence,
            action_id="test_action_yellow_002"
        )

        assert result.decision == GateDecision.YELLOW
        assert result.requires_approval is False, \
            "YELLOW should not require approval"
        assert result.blocked_at is None, \
            "YELLOW should not be blocked"

    def test_yellow_emits_gate_decision_receipt(self):
        """YELLOW: Receipt emitted with correct fields."""
        confidence = 0.78

        result, receipt = gate_decision(
            confidence,
            action_id="test_action_yellow_003",
            context_drift=0.12,
            reasoning_entropy=0.18
        )

        assert receipt["receipt_type"] == "gate_decision"
        assert receipt["decision"] == "YELLOW"
        assert receipt["confidence_score"] == confidence
        assert "context_drift" in receipt
        assert "reasoning_entropy" in receipt

    def test_yellow_lower_boundary(self):
        """YELLOW: At lower boundary (0.7) is still YELLOW."""
        confidence = GATE_YELLOW_THRESHOLD  # Exactly 0.7

        result, _ = gate_decision(confidence, action_id="test_lower_boundary")

        assert result.decision == GateDecision.YELLOW, \
            f"Expected YELLOW at lower boundary, got {result.decision}"

    def test_yellow_upper_boundary(self):
        """YELLOW: Just below GREEN threshold is YELLOW."""
        confidence = GATE_GREEN_THRESHOLD - 0.001  # 0.899

        result, _ = gate_decision(confidence, action_id="test_upper_boundary")

        assert result.decision == GateDecision.YELLOW, \
            f"Expected YELLOW just below GREEN, got {result.decision}"

    def test_yellow_spawns_watchers_integration(self):
        """YELLOW: Watchers should be spawned (integration check)."""
        # This tests the documented behavior that YELLOW spawns watchers
        confidence = 0.8

        result, receipt = gate_decision(
            confidence,
            action_id="test_watcher_spawn"
        )

        assert result.decision == GateDecision.YELLOW
        # Watcher spawning would be handled by loop/ integration
        # This test verifies the YELLOW decision is made
