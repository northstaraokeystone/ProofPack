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
HIGH_VARIANCE_THRESHOLD = 0.3  # Adds +1 helper when exceeded

# Spawn formula
def _spawn_base_formula(wounds: int) -> int:
    return (wounds // 2) + 1

SPAWN_BASE_FORMULA: Callable[[int], int] = _spawn_base_formula
SPAWN_CONVERGENCE_MULTIPLIER = 1.5
SPAWN_CONVERGENCE_THRESHOLD = 0.95

# Agent spawning limits
AGENT_MAX_DEPTH = 3          # Maximum recursion depth
AGENT_MAX_POPULATION = 50    # Maximum total active agents
AGENT_DEFAULT_TTL = 300      # Default TTL in seconds (5 minutes)
AGENT_GREEN_TTL = 60         # Success learner TTL (1 minute)
AGENT_YELLOW_TTL_BUFFER = 30 # Added to action duration for watchers
AGENT_MIN_HELPERS = 1        # Minimum helpers for RED gate
AGENT_MAX_HELPERS = 6        # Maximum helpers for RED gate

# Agent topology thresholds (META-LOOP classification)
AGENT_ESCAPE_VELOCITY = 0.85     # Effectiveness threshold for OPEN topology
AGENT_AUTONOMY_THRESHOLD = 0.75  # Autonomy threshold for graduation
AGENT_TRANSFER_THRESHOLD = 0.70  # Transfer score threshold for HYBRID topology

# Agent coordination
SOLUTION_CONFIDENCE_THRESHOLD = 0.8  # Confidence to declare winner

# SLO thresholds
GATE_LATENCY_MS = 50
MONTE_CARLO_LATENCY_MS = 200
SPAWN_LATENCY_MS = 50           # Agent spawn should complete in <50ms
COORDINATION_LATENCY_MS = 100   # Sibling coordination should complete in <100ms
GRADUATION_LATENCY_MS = 200     # Graduation evaluation should complete in <200ms

# Convergence detection
CONVERGENCE_LOOP_THRESHOLD = 5  # Same question N times = loop
