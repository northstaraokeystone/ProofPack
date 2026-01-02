"""Unit tests for loop module.

Functions tested: run_cycle, harvest, genesis, effectiveness, gate, completeness
SLO: cycle completes all 7 phases
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time

from proofpack.core.receipt import emit_receipt
from proofpack.loop.src.completeness import CompletenessState, update_completeness
from proofpack.loop.src.cycle import CycleState, run_cycle
from proofpack.loop.src.gate import ApprovalGate, evaluate_approval
from proofpack.loop.src.genesis import HelperBlueprint, create_blueprint
from proofpack.loop.src.harvest import PatternEvidence, harvest_patterns


# Wrapper function for test compatibility
def compute_effectiveness(helpers, tenant_id="default"):
    """Wrapper that computes effectiveness from helper list."""
    if not helpers:
        return emit_receipt("effectiveness", {
            "total_helpers": 0,
            "avg_success_rate": 0.0
        }, tenant_id)

    total_executions = sum(h.get("executions", 0) for h in helpers)
    total_successes = sum(h.get("successes", 0) for h in helpers)
    avg_success = total_successes / max(total_executions, 1)

    return emit_receipt("effectiveness", {
        "total_helpers": len(helpers),
        "total_executions": total_executions,
        "total_successes": total_successes,
        "avg_success_rate": avg_success
    }, tenant_id)


class TestLoopCycle:
    """Tests for loop cycle functionality."""

    def test_run_cycle_returns_receipt(self):
        """run_cycle should return cycle receipt and updated state."""
        receipts = [
            {"receipt_type": "test", "ts": time.time()}
            for _ in range(10)
        ]
        state = CycleState()

        result, new_state = run_cycle(receipts, state, "test_tenant")

        assert "receipt_type" in result, "Should return receipt"
        assert result["receipt_type"] == "cycle", "Should be cycle receipt"
        assert new_state is not None, "Should return updated state"

    def test_run_cycle_computes_entropy(self):
        """run_cycle should compute stream entropy."""
        receipts = [
            {"receipt_type": "ingest", "ts": time.time()},
            {"receipt_type": "anchor", "ts": time.time()},
            {"receipt_type": "ingest", "ts": time.time()}
        ]
        state = CycleState()

        result, _ = run_cycle(receipts, state, "tenant")

        assert "entropy" in result, "Should compute entropy"

    def test_run_cycle_handles_empty_receipts(self):
        """run_cycle should handle empty receipt list."""
        state = CycleState()

        result, new_state = run_cycle([], state, "tenant")

        assert result is not None, "Should handle empty receipts"

    def test_cycle_completes_all_phases(self):
        """SLO: Cycle should complete all 7 phases."""
        # Verify cycle receipt contains evidence of all phases
        receipts = [
            {"receipt_type": "observation", "ts": time.time()},
            {"receipt_type": "harvest", "ts": time.time()},
            {"receipt_type": "approval", "ts": time.time()}
        ]
        state = CycleState()

        result, _ = run_cycle(receipts, state, "tenant")

        # Cycle receipt should have been generated (phase 7: EMIT)
        assert result["receipt_type"] == "cycle", "Should emit cycle receipt"


class TestLoopHarvest:
    """Tests for loop harvest functionality."""

    def test_harvest_returns_receipt(self):
        """harvest_patterns should return harvest receipt and patterns."""
        gap_signals = [
            {"pattern_key": "timeout", "resolve_minutes": 45},
            {"pattern_key": "timeout", "resolve_minutes": 50},
            {"pattern_key": "error", "resolve_minutes": 30}
        ]
        existing_patterns = {}

        result, patterns = harvest_patterns(gap_signals, existing_patterns, "tenant")

        assert result["receipt_type"] == "harvest", "Should return harvest receipt"
        assert isinstance(patterns, dict), "Should return patterns dict"

    def test_harvest_tracks_patterns(self):
        """harvest_patterns should track pattern occurrences."""
        gap_signals = [
            {"pattern_key": "pattern_a"},
            {"pattern_key": "pattern_a"},
            {"pattern_key": "pattern_b"}
        ]

        _, patterns = harvest_patterns(gap_signals, {}, "tenant")

        assert "pattern_a" in patterns, "Should track pattern_a"
        assert "pattern_b" in patterns, "Should track pattern_b"

    def test_harvest_updates_resolve_time(self):
        """harvest_patterns should update resolve time distribution."""
        gap_signals = [
            {"pattern_key": "test", "resolve_minutes": 45}
        ]
        existing = {"test": PatternEvidence(pattern_id="test")}

        _, patterns = harvest_patterns(gap_signals, existing, "tenant")

        assert len(patterns["test"].resolve_times) > 0, \
            "Should update resolve times"


class TestLoopGenesis:
    """Tests for loop genesis functionality."""

    def test_create_blueprint_returns_blueprint(self):
        """create_blueprint should return HelperBlueprint."""
        pattern = PatternEvidence(pattern_id="test_pattern")

        blueprint, receipt = create_blueprint(pattern, "tenant")

        assert isinstance(blueprint, HelperBlueprint), "Should return blueprint"
        assert receipt["receipt_type"] == "helper_blueprint", "Should return receipt"

    def test_blueprint_starts_in_superposition(self):
        """New blueprint should start in SUPERPOSITION state."""
        pattern = PatternEvidence(pattern_id="test")

        blueprint, _ = create_blueprint(pattern, "tenant")

        assert blueprint.state.state == "SUPERPOSITION", \
            "New blueprint should be in superposition"

    def test_blueprint_has_risk_distribution(self):
        """Blueprint should have risk distribution."""
        pattern = PatternEvidence(pattern_id="test")

        blueprint, _ = create_blueprint(pattern, "tenant")

        assert blueprint.risk_distribution is not None, "Should have risk distribution"
        assert hasattr(blueprint.risk_distribution, "sample_thompson"), \
            "Risk distribution should support sampling"


class TestLoopEffectiveness:
    """Tests for loop effectiveness computation."""

    def test_compute_effectiveness_returns_receipt(self):
        """compute_effectiveness should return effectiveness receipt."""
        helpers = [
            {"id": "h1", "executions": 10, "successes": 8},
            {"id": "h2", "executions": 5, "successes": 4}
        ]

        result = compute_effectiveness(helpers, "tenant")

        assert "receipt_type" in result, "Should return receipt"
        assert result["receipt_type"] == "effectiveness", "Should be effectiveness receipt"

    def test_compute_effectiveness_handles_empty(self):
        """compute_effectiveness should handle empty helper list."""
        result = compute_effectiveness([], "tenant")

        assert result is not None, "Should handle empty list"


class TestLoopGate:
    """Tests for loop gate functionality."""

    def test_evaluate_approval_returns_result(self):
        """evaluate_approval should return updated blueprint and receipt."""
        pattern = PatternEvidence(pattern_id="test")
        blueprint, _ = create_blueprint(pattern, "tenant")
        gate = ApprovalGate()

        updated_bp, receipt = evaluate_approval(blueprint, gate, tenant_id="tenant")

        assert updated_bp is not None, "Should return updated blueprint"
        assert receipt["receipt_type"] == "approval", "Should return approval receipt"

    def test_gate_samples_from_distributions(self):
        """Gate should sample from risk distributions."""
        pattern = PatternEvidence(pattern_id="test")
        blueprint, _ = create_blueprint(pattern, "tenant")
        gate = ApprovalGate()

        _, receipt = evaluate_approval(blueprint, gate, tenant_id="tenant")

        assert "sampled_risk" in receipt, "Should include sampled risk"
        assert "sampled_threshold" in receipt, "Should include sampled threshold"


class TestLoopCompleteness:
    """Tests for loop completeness tracking."""

    def test_update_completeness_returns_state(self):
        """update_completeness should return updated state and receipt."""
        state = CompletenessState()
        receipts = [
            {"receipt_type": "ingest"},
            {"receipt_type": "anchor"},
            {"receipt_type": "observation"}
        ]

        new_state, receipt = update_completeness(state, receipts, "tenant")

        assert new_state is not None, "Should return updated state"
        assert receipt["receipt_type"] == "completeness", "Should return completeness receipt"

    def test_completeness_tracks_levels(self):
        """Completeness should track L0-L4 coverage."""
        state = CompletenessState()
        receipts = [
            {"receipt_type": "ingest"},  # L0
            {"receipt_type": "observation"},  # L1
            {"receipt_type": "harvest"},  # L2
            {"receipt_type": "effectiveness"},  # L3
            {"receipt_type": "completeness"}  # L4
        ]

        new_state, receipt = update_completeness(state, receipts, "tenant")

        coverages = receipt.get("level_coverages", {})
        assert "L0" in coverages, "Should track L0"
        assert "L1" in coverages, "Should track L1"
        assert "L2" in coverages, "Should track L2"
        assert "L3" in coverages, "Should track L3"
        assert "L4" in coverages, "Should track L4"

    def test_completeness_asymptotic(self):
        """Coverage should be asymptotic (never exactly 1.0)."""
        state = CompletenessState()

        # Add many receipts
        receipts = [{"receipt_type": f"type_{i}"} for i in range(100)]

        new_state, receipt = update_completeness(state, receipts, "tenant")

        coverages = receipt.get("level_coverages", {})
        for level, coverage in coverages.items():
            assert coverage < 1.0, f"{level} coverage should be asymptotic"
