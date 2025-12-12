"""APPROVAL scenario: Gate at all risk levels.

Pass criteria:
- Auto-approve at risk < 0.2
- Single approval at 0.2 ≤ risk < 0.5
- Two approvals at 0.5 ≤ risk < 0.8
- Observation period at risk ≥ 0.8
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from conftest import SimConfig, SimState
from sim import simulate_approval


class TestApproval:
    """Approval scenario: Test gate function at all risk levels."""

    def test_approval_auto_approve_low_risk(self, sim_state: SimState):
        """APPROVAL: Risk < 0.2 should auto-approve."""
        # Test multiple times to verify consistency
        results = [simulate_approval(sim_state, 0.1) for _ in range(10)]

        approved_count = results.count("approved")
        assert approved_count == 10, \
            f"Risk 0.1 should always auto-approve, got {approved_count}/10 approved"

    def test_approval_single_approval_medium_risk(self, sim_state: SimState):
        """APPROVAL: 0.2 ≤ risk < 0.5 should mostly approve with single approval."""
        # Test at risk 0.35 (middle of range)
        results = [simulate_approval(sim_state, 0.35) for _ in range(100)]

        approved_count = results.count("approved")
        # Should approve ~80% of the time
        assert 60 <= approved_count <= 95, \
            f"Risk 0.35 should approve ~80%, got {approved_count}%"

    def test_approval_two_approvals_high_risk(self, sim_state: SimState):
        """APPROVAL: 0.5 ≤ risk < 0.8 should approve less frequently."""
        # Test at risk 0.65 (middle of range)
        results = [simulate_approval(sim_state, 0.65) for _ in range(100)]

        approved_count = results.count("approved")
        # Should approve ~60% of the time
        assert 40 <= approved_count <= 80, \
            f"Risk 0.65 should approve ~60%, got {approved_count}%"

    def test_approval_observation_period_very_high_risk(self, sim_state: SimState):
        """APPROVAL: Risk ≥ 0.8 should require observation period (stay pending)."""
        # Test at risk 0.9
        results = [simulate_approval(sim_state, 0.9) for _ in range(10)]

        pending_count = results.count("pending")
        # Should always stay pending at high risk
        assert pending_count == 10, \
            f"Risk 0.9 should always stay pending, got {pending_count}/10 pending"

    def test_approval_boundary_0_2(self, sim_state: SimState):
        """APPROVAL: Test boundary at 0.2."""
        # Just below boundary
        results_below = [simulate_approval(sim_state, 0.19) for _ in range(10)]
        assert results_below.count("approved") == 10, \
            "Risk 0.19 should always auto-approve"

        # At boundary - should use single approval logic
        results_at = [simulate_approval(sim_state, 0.2) for _ in range(50)]
        approved_at = results_at.count("approved")
        assert 30 <= approved_at <= 45, \
            f"Risk 0.2 (boundary) should approve ~80%, got {approved_at}/50"

    def test_approval_boundary_0_5(self, sim_state: SimState):
        """APPROVAL: Test boundary at 0.5."""
        # Just below boundary
        results_below = [simulate_approval(sim_state, 0.49) for _ in range(100)]
        approved_below = results_below.count("approved")
        assert 60 <= approved_below <= 95, \
            f"Risk 0.49 should approve ~80%, got {approved_below}%"

        # At boundary - should use two approval logic
        results_at = [simulate_approval(sim_state, 0.5) for _ in range(100)]
        approved_at = results_at.count("approved")
        assert 40 <= approved_at <= 80, \
            f"Risk 0.5 (boundary) should approve ~60%, got {approved_at}%"

    def test_approval_boundary_0_8(self, sim_state: SimState):
        """APPROVAL: Test boundary at 0.8."""
        # Just below boundary
        results_below = [simulate_approval(sim_state, 0.79) for _ in range(100)]
        approved_below = results_below.count("approved")
        assert 40 <= approved_below <= 80, \
            f"Risk 0.79 should approve ~60%, got {approved_below}%"

        # At boundary - should require observation
        results_at = [simulate_approval(sim_state, 0.8) for _ in range(10)]
        assert results_at.count("pending") == 10, \
            "Risk 0.8 (boundary) should always stay pending"

    def test_approval_all_tiers_in_simulation(self, sim_state: SimState):
        """APPROVAL: Verify all approval tiers function in full simulation."""
        config = SimConfig(
            n_cycles=1000,
            gap_rate=0.3,  # Higher rate to generate more helpers
            resource_budget=1.0,
            random_seed=42,
            timeout_seconds=300
        )

        # Pre-inject gaps with varying resolve times to create different risk levels
        import time
        for i in range(10):
            # Low risk pattern (fast resolve)
            sim_state.gap_history.append({
                "id": f"low_risk_{i}",
                "cycle": i,
                "problem_type": "low_risk_pattern",
                "resolve_time": 10.0 + i,  # 10-19 min
                "ts": time.time()
            })
            # High risk pattern (slow resolve)
            sim_state.gap_history.append({
                "id": f"high_risk_{i}",
                "cycle": i,
                "problem_type": "high_risk_pattern",
                "resolve_time": 90.0 + i,  # 90-99 min
                "ts": time.time()
            })

        from sim import run_simulation
        final_state = run_simulation(config, sim_state)

        # Check that we have helpers with different states
        helper_states = [h.get("state") for h in final_state.active_helpers]
        assert len(helper_states) > 0, "Should have helpers"

        # Verify approval receipts were generated
        approval_receipts = [
            r for r in final_state.receipt_ledger
            if r.get("receipt_type") == "approval"
        ]
        assert len(approval_receipts) > 0, "Should have approval receipts"
