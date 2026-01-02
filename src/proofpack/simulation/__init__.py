"""Monte Carlo variance reduction via simulation.

Run variations before committing to action. Statistical confidence, not single-shot.
"""
from .simulate import simulate_action, SimulationResult
from .variance import calculate_variance, VarianceResult
from .threshold import is_stable, check_stability

__all__ = [
    "simulate_action",
    "SimulationResult",
    "calculate_variance",
    "VarianceResult",
    "is_stable",
    "check_stability",
]
