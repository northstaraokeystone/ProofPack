"""LEARNING scenario: Recurring gaps → helper proposal.

Pass criteria:
- Pre-inject 7 recurring gaps
- ≥1 helper_blueprint proposed within 500 cycles
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from conftest import SimConfig, SimState
from sim import run_simulation, simulate_genesis


class TestLearning:
    """Learning scenario: System learns from recurring gaps."""

    def test_learning_helper_proposed_from_recurring_gaps(self, sim_state: SimState):
        """LEARNING: Pre-inject 7 recurring gaps, expect helper proposal within 500 cycles."""
        # Pre-inject 7 recurring gaps of same type with high resolve times
        for i in range(7):
            gap = {
                "id": f"preinjected_gap_{i}",
                "cycle": i,
                "problem_type": "recurring_timeout",  # Same problem type
                "resolve_time": 45.0,  # > 30 minutes median threshold
                "ts": time.time()
            }
            sim_state.gap_history.append(gap)

        config = SimConfig(
            n_cycles=500,
            gap_rate=0.1,  # Normal gap rate
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=300
        )

        final_state = run_simulation(config, sim_state)

        # Should have at least 1 helper blueprint for the recurring pattern
        helper_for_pattern = [
            h for h in final_state.active_helpers
            if h.get("pattern_id") == "recurring_timeout"
        ]
        assert len(helper_for_pattern) >= 1, \
            f"Expected helper for 'recurring_timeout' pattern, got helpers: {final_state.active_helpers}"

    def test_learning_genesis_trigger_threshold(self, sim_state: SimState):
        """LEARNING: Verify genesis triggers at ≥5 occurrences AND median resolve > 30."""
        # Test exactly 5 gaps at threshold
        for i in range(5):
            gap = {
                "id": f"threshold_gap_{i}",
                "cycle": i,
                "problem_type": "threshold_test",
                "resolve_time": 35.0,  # Just above 30 min threshold
                "ts": time.time()
            }
            sim_state.gap_history.append(gap)

        # Run genesis check
        sim_state = simulate_genesis(sim_state)

        # Should have triggered helper proposal
        helper_for_threshold = [
            h for h in sim_state.active_helpers
            if h.get("pattern_id") == "threshold_test"
        ]
        assert len(helper_for_threshold) >= 1, \
            "Genesis should trigger at exactly 5 occurrences with median > 30"

    def test_learning_no_genesis_below_threshold(self, sim_state: SimState):
        """LEARNING: Verify genesis does NOT trigger below thresholds."""
        # Only 4 gaps (below 5 threshold)
        for i in range(4):
            gap = {
                "id": f"below_threshold_gap_{i}",
                "cycle": i,
                "problem_type": "below_threshold_test",
                "resolve_time": 40.0,
                "ts": time.time()
            }
            sim_state.gap_history.append(gap)

        sim_state = simulate_genesis(sim_state)

        helper_for_pattern = [
            h for h in sim_state.active_helpers
            if h.get("pattern_id") == "below_threshold_test"
        ]
        assert len(helper_for_pattern) == 0, \
            "Genesis should NOT trigger with only 4 occurrences"

    def test_learning_no_genesis_fast_resolve(self, sim_state: SimState):
        """LEARNING: Verify genesis does NOT trigger for fast-resolving gaps."""
        # 7 gaps but fast resolve times (below 30 min median)
        for i in range(7):
            gap = {
                "id": f"fast_resolve_gap_{i}",
                "cycle": i,
                "problem_type": "fast_resolve_test",
                "resolve_time": 15.0,  # Below 30 min threshold
                "ts": time.time()
            }
            sim_state.gap_history.append(gap)

        sim_state = simulate_genesis(sim_state)

        helper_for_pattern = [
            h for h in sim_state.active_helpers
            if h.get("pattern_id") == "fast_resolve_test"
        ]
        assert len(helper_for_pattern) == 0, \
            "Genesis should NOT trigger when median resolve < 30 min"

    def test_learning_multiple_patterns(self, sim_state: SimState):
        """LEARNING: System should learn multiple distinct patterns."""
        # Inject two different recurring patterns
        for i in range(6):
            sim_state.gap_history.append({
                "id": f"pattern_a_{i}",
                "cycle": i,
                "problem_type": "pattern_type_a",
                "resolve_time": 45.0,
                "ts": time.time()
            })
            sim_state.gap_history.append({
                "id": f"pattern_b_{i}",
                "cycle": i,
                "problem_type": "pattern_type_b",
                "resolve_time": 60.0,
                "ts": time.time()
            })

        config = SimConfig(
            n_cycles=100,
            gap_rate=0.0,  # No new gaps
            random_seed=42,
            timeout_seconds=60
        )

        final_state = run_simulation(config, sim_state)

        pattern_ids = {h.get("pattern_id") for h in final_state.active_helpers}
        assert "pattern_type_a" in pattern_ids, "Should learn pattern_type_a"
        assert "pattern_type_b" in pattern_ids, "Should learn pattern_type_b"
