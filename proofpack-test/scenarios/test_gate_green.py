"""Test gate GREEN decision path.

Pass criteria:
- Confidence >0.9 results in GREEN decision
- Execution proceeds without blocking
- gate_decision receipt emitted
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time

from gate.confidence import ActionPlan, ContextState, ReasoningHistory, calculate_confidence
from gate.decision import gate_decision, GateDecision
from constants import GATE_GREEN_THRESHOLD


class TestGateGreen:
    """Test gate GREEN decision path."""

    def test_high_confidence_executes(self):
        """GREEN: High confidence action executes immediately."""
        # Create high-confidence scenario
        action = ActionPlan(
            action_id="test_action_001",
            action_type="safe_operation",
            target="test_target",
            parameters={},
            reasoning_chain=["analyze", "verify", "execute"]
        )

        context = ContextState(
            initial_hash="abc123",
            current_hash="abc123",  # No drift
            entropy=0.05,  # Low entropy
            timestamp=time.time()
        )

        history = ReasoningHistory(
            steps=[{"step": "analyze"}, {"step": "verify"}],
            confidence_trajectory=[0.95, 0.96, 0.97],  # High, stable
            question_hashes=[]  # No repeated questions
        )

        # Calculate confidence
        confidence, receipt = calculate_confidence(action, context, history)

        assert confidence > GATE_GREEN_THRESHOLD, \
            f"Expected confidence > {GATE_GREEN_THRESHOLD}, got {confidence}"
        assert receipt["receipt_type"] == "confidence_calculation"

    def test_green_decision_no_blocking(self):
        """GREEN: Gate decision does not block."""
        confidence = 0.95  # Above GREEN threshold

        result, receipt = gate_decision(
            confidence,
            action_id="test_action_002",
            context_drift=0.05,
            reasoning_entropy=0.1
        )

        assert result.decision == GateDecision.GREEN, \
            f"Expected GREEN, got {result.decision}"
        assert result.requires_approval is False, \
            "GREEN decision should not require approval"
        assert result.blocked_at is None, \
            "GREEN decision should not have blocked_at"

    def test_green_emits_gate_decision_receipt(self):
        """GREEN: Receipt emitted with correct fields."""
        confidence = 0.92

        result, receipt = gate_decision(
            confidence,
            action_id="test_action_003",
            context_drift=0.02,
            reasoning_entropy=0.08
        )

        assert receipt["receipt_type"] == "gate_decision"
        assert receipt["decision"] == "GREEN"
        assert receipt["confidence_score"] == confidence
        assert "payload_hash" in receipt

    def test_green_boundary_condition(self):
        """GREEN: Exactly at threshold still counts as GREEN."""
        confidence = GATE_GREEN_THRESHOLD  # Exactly 0.9

        result, _ = gate_decision(confidence, action_id="test_boundary")

        assert result.decision == GateDecision.GREEN, \
            f"Expected GREEN at boundary, got {result.decision}"

    def test_green_latency_under_budget(self):
        """GREEN: Decision made within latency budget."""
        t0 = time.perf_counter()

        result, receipt = gate_decision(
            0.95,
            action_id="test_latency"
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert elapsed_ms < 50, f"Decision took {elapsed_ms}ms, budget is 50ms"
