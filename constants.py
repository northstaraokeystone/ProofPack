"""ProofPack constants and thresholds.

All magic numbers live here. No exceptions.
"""
from typing import Callable

# Gate thresholds
GATE_GREEN_THRESHOLD = 0.9
GATE_YELLOW_THRESHOLD = 0.7

# Wound detection
WOUND_DROP_THRESHOLD = 0.15
WOUND_SPAWN_THRESHOLD = 5

# Monte Carlo
MONTE_CARLO_DEFAULT_SIMS = 100
MONTE_CARLO_DEFAULT_NOISE = 0.05
MONTE_CARLO_VARIANCE_THRESHOLD = 0.2
MONTE_CARLO_LATENCY_BUDGET_MS = 200

# Spawn formula
SPAWN_BASE_FORMULA: Callable[[int], int] = lambda wounds: (wounds // 2) + 1
SPAWN_CONVERGENCE_MULTIPLIER = 1.5
SPAWN_CONVERGENCE_THRESHOLD = 0.95

# SLO thresholds
GATE_LATENCY_MS = 50
MONTE_CARLO_LATENCY_MS = 200

# Convergence detection
CONVERGENCE_LOOP_THRESHOLD = 5  # Same question N times = loop
