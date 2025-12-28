"""Test helper spawning formula.

Pass criteria:
- 5 wounds triggers spawn
- Formula: (wounds // 2) + 1
- Convergence bonus applies correctly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from loop.src.spawn import calculate_helpers_to_spawn, should_spawn, spawn_helpers
from constants import (
    WOUND_SPAWN_THRESHOLD,
    SPAWN_CONVERGENCE_THRESHOLD,
    SPAWN_CONVERGENCE_MULTIPLIER
)


class TestSpawn:
    """Test helper spawning logic."""

    def test_5_wounds_3_helpers(self):
        """SPAWN: 5 wounds produces 3 helpers."""
        # Formula: (5 // 2) + 1 = 3
        helpers = calculate_helpers_to_spawn(5)
        assert helpers == 3, f"Expected 3 helpers for 5 wounds, got {helpers}"

    def test_10_wounds_6_helpers(self):
        """SPAWN: 10 wounds produces 6 helpers."""
        # Formula: (10 // 2) + 1 = 6
        helpers = calculate_helpers_to_spawn(10)
        assert helpers == 6, f"Expected 6 helpers for 10 wounds, got {helpers}"

    def test_formula_various_inputs(self):
        """SPAWN: Formula works for various wound counts."""
        test_cases = [
            (1, 1),   # (1 // 2) + 1 = 1
            (2, 2),   # (2 // 2) + 1 = 2
            (3, 2),   # (3 // 2) + 1 = 2
            (4, 3),   # (4 // 2) + 1 = 3
            (7, 4),   # (7 // 2) + 1 = 4
            (15, 8),  # (15 // 2) + 1 = 8
        ]

        for wounds, expected in test_cases:
            helpers = calculate_helpers_to_spawn(wounds)
            assert helpers == expected, \
                f"For {wounds} wounds, expected {expected} helpers, got {helpers}"

    def test_convergence_bonus_applied(self):
        """SPAWN: Convergence proof >0.95 multiplies by 1.5x."""
        wounds = 10
        base_helpers = calculate_helpers_to_spawn(wounds, convergence_proof=0.0)
        bonus_helpers = calculate_helpers_to_spawn(wounds, convergence_proof=0.96)

        expected_bonus = int(base_helpers * SPAWN_CONVERGENCE_MULTIPLIER + 0.5)  # ceil

        assert bonus_helpers == expected_bonus, \
            f"Expected {expected_bonus} helpers with bonus, got {bonus_helpers}"

    def test_convergence_below_threshold_no_bonus(self):
        """SPAWN: Convergence proof below 0.95 gets no bonus."""
        wounds = 10
        base = calculate_helpers_to_spawn(wounds, convergence_proof=0.0)
        no_bonus = calculate_helpers_to_spawn(wounds, convergence_proof=0.94)

        assert no_bonus == base, \
            "Convergence below threshold should not apply bonus"

    def test_should_spawn_threshold(self):
        """SPAWN: should_spawn respects threshold."""
        assert should_spawn(4) is False
        assert should_spawn(5) is True
        assert should_spawn(10) is True

    def test_spawn_helpers_below_threshold(self):
        """SPAWN: No spawn when below threshold."""
        result, receipt = spawn_helpers(3)

        assert result is None
        assert receipt is None

    def test_zero_wounds_one_helper(self):
        """SPAWN: Zero wounds still produces 1 helper (minimum)."""
        helpers = calculate_helpers_to_spawn(0)
        assert helpers == 1, "Minimum helpers should be 1"

    def test_convergence_exactly_at_threshold(self):
        """SPAWN: Convergence at exactly 0.95 gets bonus."""
        wounds = 6
        base = calculate_helpers_to_spawn(wounds, convergence_proof=0.0)
        at_threshold = calculate_helpers_to_spawn(wounds, convergence_proof=SPAWN_CONVERGENCE_THRESHOLD)

        assert at_threshold > base, \
            f"Convergence at threshold should apply bonus"
