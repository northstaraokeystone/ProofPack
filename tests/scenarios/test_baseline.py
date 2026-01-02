"""BASELINE scenario: 1000 cycles, zero violations.

Pass criteria:
- Zero violations
- Receipts populated in ledger
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conftest import SimConfig, SimState
from sim import run_simulation


class TestBaseline:
    """Baseline scenario: 1000 cycles under normal conditions."""

    def test_baseline_zero_violations(self, sim_config: SimConfig, sim_state: SimState):
        """BASELINE: Run 1000 cycles with default config, expect zero violations."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=300
        )

        final_state = run_simulation(config, sim_state)

        assert final_state.cycle == 1000, f"Expected 1000 cycles, got {final_state.cycle}"
        assert len(final_state.violations) == 0, f"Expected zero violations, got: {final_state.violations}"

    def test_baseline_receipts_populated(self, sim_config: SimConfig, sim_state: SimState):
        """BASELINE: Verify receipts are populated in ledger."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=300
        )

        final_state = run_simulation(config, sim_state)

        assert len(final_state.receipt_ledger) > 0, "Receipt ledger should not be empty"
        assert any(r.get("receipt_type") == "cycle" for r in final_state.receipt_ledger), \
            "Ledger should contain cycle receipts"
        assert any(r.get("receipt_type") == "observation" for r in final_state.receipt_ledger), \
            "Ledger should contain observation receipts"

    def test_baseline_completeness_tracked(self, sim_config: SimConfig, sim_state: SimState):
        """BASELINE: Verify completeness trace is populated."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=300
        )

        final_state = run_simulation(config, sim_state)

        assert len(final_state.completeness_trace) == 1000, \
            f"Expected 1000 completeness snapshots, got {len(final_state.completeness_trace)}"

        # Verify final completeness has all levels
        final_completeness = final_state.completeness_trace[-1]
        assert "L0" in final_completeness, "Completeness should track L0"
        assert "L1" in final_completeness, "Completeness should track L1"
        assert "L2" in final_completeness, "Completeness should track L2"
        assert "L3" in final_completeness, "Completeness should track L3"
        assert "L4" in final_completeness, "Completeness should track L4"

    def test_baseline_gap_handling(self, sim_config: SimConfig, sim_state: SimState):
        """BASELINE: Verify gaps are detected and recorded."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.1,  # 10% gap rate
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=300
        )

        final_state = run_simulation(config, sim_state)

        # With 10% gap rate over 1000 cycles, expect ~100 gaps (±50)
        gap_count = len(final_state.gap_history)
        assert 50 < gap_count < 150, f"Expected ~100 gaps, got {gap_count}"

        # Each gap should have required fields
        for gap in final_state.gap_history:
            assert "id" in gap, "Gap missing id"
            assert "problem_type" in gap, "Gap missing problem_type"
            assert "cycle" in gap, "Gap missing cycle"
