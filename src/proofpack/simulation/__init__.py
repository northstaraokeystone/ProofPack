"""Monte Carlo variance reduction via simulation.

Run variations before committing to action. Statistical confidence, not single-shot.
"""
from .simulate import SimulationResult, simulate_action
from .threshold import check_stability, is_stable
from .variance import VarianceResult, calculate_variance

__all__ = [
    "simulate_action",
    "SimulationResult",
    "calculate_variance",
    "VarianceResult",
    "is_stable",
    "check_stability",
]
