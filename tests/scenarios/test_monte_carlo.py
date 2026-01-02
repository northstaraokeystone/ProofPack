"""Test Monte Carlo variance calculation.

Pass criteria:
- 100 simulations complete in <200ms
- Variance calculation is correct
- Stability threshold works
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time

from proofpack.core.constants import MONTE_CARLO_DEFAULT_SIMS, MONTE_CARLO_LATENCY_BUDGET_MS
from proofpack.simulation.simulate import Action, simulate_action
from proofpack.simulation.threshold import check_stability, is_stable
from proofpack.simulation.variance import calculate_variance


class TestMonteCarlo:
    """Test Monte Carlo simulation and variance."""

    def test_100_sims_under_200ms(self):
        """MONTE CARLO: 100 simulations complete within latency budget."""
        action = Action(
            action_id="test_latency_001",
            action_type="test",
            parameters={},
            expected_outcome=0.8
        )

        t0 = time.perf_counter()
        batch, _ = simulate_action(action, n_sims=100)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert len(batch.results) == 100
        assert elapsed_ms < MONTE_CARLO_LATENCY_BUDGET_MS, \
            f"Simulation took {elapsed_ms}ms, budget is {MONTE_CARLO_LATENCY_BUDGET_MS}ms"

    def test_variance_calculation_correct(self):
        """MONTE CARLO: Variance calculation produces expected results."""
        # Known outcomes with predictable variance
        outcomes = [0.5, 0.5, 0.5, 0.5, 0.5]  # Zero variance

        result, receipt = calculate_variance(outcomes)

        assert result.variance_score == 0.0, \
            f"Expected zero variance for identical values, got {result.variance_score}"
        assert result.mean_outcome == 0.5

    def test_variance_high_spread(self):
        """MONTE CARLO: High spread results in high variance."""
        outcomes = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]  # Maximum variance

        result, _ = calculate_variance(outcomes)

        assert result.variance_score > 0.5, \
            f"Expected high variance for spread values, got {result.variance_score}"
        assert result.range_spread == 1.0

    def test_stability_threshold_works(self):
        """MONTE CARLO: Stability check respects threshold."""
        low_variance = 0.1
        high_variance = 0.5

        assert is_stable(low_variance) is True
        assert is_stable(high_variance) is False

    def test_stability_check_emits_receipt(self):
        """MONTE CARLO: Stability check emits receipt."""
        result, receipt = check_stability(0.15, action_id="test_stability")

        assert result.is_stable is True
        assert receipt["receipt_type"] == "stability_check"
        assert receipt["variance_score"] == 0.15
        assert receipt["is_stable"] is True

    def test_simulation_with_noise(self):
        """MONTE CARLO: Noise affects outcome distribution."""
        action = Action(
            action_id="test_noise_001",
            action_type="test",
            parameters={},
            expected_outcome=0.8
        )

        # High noise should increase variance
        batch_high_noise, _ = simulate_action(action, n_sims=100, noise=0.2)
        batch_low_noise, _ = simulate_action(action, n_sims=100, noise=0.01)

        variance_high, _ = calculate_variance(batch_high_noise.outcomes)
        variance_low, _ = calculate_variance(batch_low_noise.outcomes)

        assert variance_high.variance_score > variance_low.variance_score, \
            "Higher noise should produce higher variance"

    def test_default_n_simulations(self):
        """MONTE CARLO: Default N is 100."""
        action = Action(
            action_id="test_default_n",
            action_type="test",
            parameters={},
            expected_outcome=0.5
        )

        batch, _ = simulate_action(action)

        assert len(batch.results) == MONTE_CARLO_DEFAULT_SIMS

    def test_empty_outcomes_handled(self):
        """MONTE CARLO: Empty outcomes list handled gracefully."""
        result, receipt = calculate_variance([])

        assert result.variance_score == 1.0  # Maximum uncertainty
        assert "error" in receipt
