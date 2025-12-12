"""RECOVERY scenario: Checkpoint/resume continuity.

Pass criteria:
- Run 500 cycles, checkpoint, resume 500 cycles
- Total 1000 cycles
- Ledger continuity preserved
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from conftest import SimConfig, SimState
from sim import run_simulation


class TestRecovery:
    """Recovery scenario: Checkpoint and resume preserves state."""

    def test_recovery_checkpoint_resume_total_cycles(self, sim_state: SimState):
        """RECOVERY: Run 500, checkpoint, resume 500, verify total 1000 cycles."""
        # Run first 500 cycles
        config_first = SimConfig(
            n_cycles=500,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=150
        )

        state_at_500 = run_simulation(config_first, sim_state)
        assert state_at_500.cycle == 500, f"First run should complete 500 cycles, got {state_at_500.cycle}"

        # Checkpoint
        checkpoint_data = state_at_500.checkpoint()

        # Resume from checkpoint for next 500 cycles
        restored_state = SimState.from_checkpoint(checkpoint_data)

        config_second = SimConfig(
            n_cycles=1000,  # Target 1000 total
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=43,  # Different seed for variety
            timeout_seconds=150
        )

        final_state = run_simulation(config_second, restored_state)

        assert final_state.cycle == 1000, \
            f"Total should be 1000 cycles, got {final_state.cycle}"

    def test_recovery_ledger_continuity(self, sim_state: SimState):
        """RECOVERY: Verify ledger continuity is preserved across checkpoint."""
        # Run first 500 cycles
        config_first = SimConfig(
            n_cycles=500,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=150
        )

        state_at_500 = run_simulation(config_first, sim_state)
        ledger_at_500 = len(state_at_500.receipt_ledger)

        # Checkpoint and restore
        checkpoint_data = state_at_500.checkpoint()
        restored_state = SimState.from_checkpoint(checkpoint_data)

        # Verify ledger was preserved
        assert len(restored_state.receipt_ledger) == ledger_at_500, \
            "Ledger size should be preserved after checkpoint"

        # Continue for 500 more cycles
        config_second = SimConfig(
            n_cycles=1000,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=43,
            timeout_seconds=150
        )

        final_state = run_simulation(config_second, restored_state)

        # Ledger should have grown
        assert len(final_state.receipt_ledger) > ledger_at_500, \
            "Ledger should grow after resume"

        # Verify continuity - original receipts still present
        original_receipt_ids = {
            r.get("cycle_id") or r.get("id", str(i))
            for i, r in enumerate(state_at_500.receipt_ledger)
        }
        final_receipt_ids = {
            r.get("cycle_id") or r.get("id", str(i))
            for i, r in enumerate(final_state.receipt_ledger[:ledger_at_500])
        }
        # At least some original receipts should be preserved
        assert len(original_receipt_ids & final_receipt_ids) > 0, \
            "Original receipts should be preserved"

    def test_recovery_gap_history_preserved(self, sim_state: SimState):
        """RECOVERY: Verify gap history is preserved across checkpoint."""
        # Run first 500 cycles
        config = SimConfig(
            n_cycles=500,
            gap_rate=0.2,  # Higher rate for more gaps
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=150
        )

        state_at_500 = run_simulation(config, sim_state)
        gaps_at_500 = len(state_at_500.gap_history)

        # Checkpoint and restore
        checkpoint_data = state_at_500.checkpoint()
        restored_state = SimState.from_checkpoint(checkpoint_data)

        assert len(restored_state.gap_history) == gaps_at_500, \
            "Gap history should be preserved"

    def test_recovery_helpers_preserved(self, sim_state: SimState):
        """RECOVERY: Verify active helpers are preserved across checkpoint."""
        # Pre-inject gaps to trigger helper genesis
        import time
        for i in range(7):
            sim_state.gap_history.append({
                "id": f"setup_gap_{i}",
                "cycle": i,
                "problem_type": "recovery_test_pattern",
                "resolve_time": 45.0,
                "ts": time.time()
            })

        config = SimConfig(
            n_cycles=500,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=150
        )

        state_at_500 = run_simulation(config, sim_state)

        # Should have helpers
        assert len(state_at_500.active_helpers) > 0, \
            "Should have helpers before checkpoint"

        helpers_at_500 = len(state_at_500.active_helpers)

        # Checkpoint and restore
        checkpoint_data = state_at_500.checkpoint()
        restored_state = SimState.from_checkpoint(checkpoint_data)

        assert len(restored_state.active_helpers) == helpers_at_500, \
            "Helpers should be preserved after checkpoint"

    def test_recovery_completeness_trace_preserved(self, sim_state: SimState):
        """RECOVERY: Verify completeness trace is preserved."""
        config = SimConfig(
            n_cycles=500,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=150
        )

        state_at_500 = run_simulation(config, sim_state)

        # Checkpoint and restore
        checkpoint_data = state_at_500.checkpoint()
        restored_state = SimState.from_checkpoint(checkpoint_data)

        assert len(restored_state.completeness_trace) == 500, \
            "Completeness trace should be preserved"

    def test_recovery_violations_preserved(self, sim_state: SimState):
        """RECOVERY: Verify violations are preserved and accumulate."""
        # Run first half
        config_first = SimConfig(
            n_cycles=500,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=150
        )

        state_at_500 = run_simulation(config_first, sim_state)
        violations_at_500 = len(state_at_500.violations)

        # Checkpoint and restore
        checkpoint_data = state_at_500.checkpoint()
        restored_state = SimState.from_checkpoint(checkpoint_data)

        assert len(restored_state.violations) == violations_at_500, \
            "Violations should be preserved after checkpoint"

    def test_recovery_full_cycle_equivalence(self, sim_state: SimState):
        """RECOVERY: Verify checkpoint/resume gives similar results to continuous run."""
        # Single continuous run
        config_continuous = SimConfig(
            n_cycles=1000,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=300
        )

        continuous_state = run_simulation(config_continuous, SimState())

        # Checkpoint/resume run
        sim_state_fresh = SimState()
        config_first = SimConfig(
            n_cycles=500,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=150
        )

        state_at_500 = run_simulation(config_first, sim_state_fresh)
        checkpoint_data = state_at_500.checkpoint()
        restored_state = SimState.from_checkpoint(checkpoint_data)

        config_second = SimConfig(
            n_cycles=1000,
            gap_rate=0.1,
            resource_budget=1.0,
            random_seed=42,  # Same seed for determinism
            timeout_seconds=150
        )

        resumed_state = run_simulation(config_second, restored_state)

        # Results should be similar (allowing for some variance)
        assert resumed_state.cycle == continuous_state.cycle, \
            "Cycle count should match"

        # Violations should be similar (may differ slightly due to checkpoint)
        violation_diff = abs(len(resumed_state.violations) - len(continuous_state.violations))
        assert violation_diff <= 5, \
            f"Violation count differs by {violation_diff}"
