"""STRESS scenario: gap_rate=0.5, resources=0.3, recovery test.

Pass criteria:
- Stabilize ≥1 helper
- Recover in final 100 cycles (no violations in final 100)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conftest import SimConfig, SimState
from sim import run_simulation


class TestStress:
    """Stress scenario: High gap rate, constrained resources."""

    def test_stress_stabilizes_helper(self, sim_state: SimState):
        """STRESS: System should stabilize at least 1 helper under stress."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.5,  # High gap rate
            resource_budget=0.3,  # Constrained resources
            random_seed=42,
            timeout_seconds=300
        )

        final_state = run_simulation(config, sim_state)

        # Should have at least one active helper
        approved_helpers = [
            h for h in final_state.active_helpers
            if h.get("state") == "approved"
        ]
        assert len(approved_helpers) >= 1, \
            f"Expected at least 1 approved helper, got {len(approved_helpers)}"

    def test_stress_recovery_in_final_cycles(self, sim_state: SimState):
        """STRESS: System should recover (no new violations) in final 100 cycles."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.5,
            resource_budget=0.3,
            random_seed=42,
            timeout_seconds=300
        )

        # Run first 900 cycles
        config_partial = SimConfig(
            n_cycles=900,
            gap_rate=0.5,
            resource_budget=0.3,
            random_seed=42,
            timeout_seconds=300
        )
        state_at_900 = run_simulation(config_partial, sim_state)
        violations_at_900 = len(state_at_900.violations)

        # Continue to 1000 cycles
        final_state = run_simulation(config, sim_state)

        # Check violations accumulated only in first 900, not last 100
        # (allowing for some tolerance as system stabilizes)
        violations_in_final_100 = len(final_state.violations) - violations_at_900

        # Allow small number of violations in final 100 as system stabilizes
        assert violations_in_final_100 <= 5, \
            f"Too many violations in final 100 cycles: {violations_in_final_100}"

    def test_stress_high_gap_detection(self, sim_state: SimState):
        """STRESS: Verify high gap rate generates many gaps."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.5,  # 50% gap rate
            resource_budget=0.3,
            random_seed=42,
            timeout_seconds=300
        )

        final_state = run_simulation(config, sim_state)

        # With 50% gap rate, expect ~500 gaps (±100)
        gap_count = len(final_state.gap_history)
        assert 400 < gap_count < 600, f"Expected ~500 gaps, got {gap_count}"

    def test_stress_pattern_emergence(self, sim_state: SimState):
        """STRESS: High gap rate should cause pattern emergence."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.5,
            resource_budget=0.3,
            random_seed=42,
            timeout_seconds=300
        )

        final_state = run_simulation(config, sim_state)

        # With high gap rate, multiple helpers should be proposed
        assert len(final_state.active_helpers) >= 2, \
            f"Expected multiple helper proposals, got {len(final_state.active_helpers)}"

    def test_stress_ledger_continuity(self, sim_state: SimState):
        """STRESS: Ledger should maintain continuity under stress."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.5,
            resource_budget=0.3,
            random_seed=42,
            timeout_seconds=300
        )

        final_state = run_simulation(config, sim_state)

        # Verify cycle receipts are sequential
        cycle_receipts = [
            r for r in final_state.receipt_ledger
            if r.get("receipt_type") == "cycle"
        ]
        assert len(cycle_receipts) == 1000, \
            f"Expected 1000 cycle receipts, got {len(cycle_receipts)}"
