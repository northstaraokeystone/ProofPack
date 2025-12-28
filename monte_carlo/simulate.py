"""Run simulated variations of an action.

Performance constraint: 100 simulations must complete in <200ms.
"""
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ledger.core import emit_receipt
from anchor import dual_hash
from constants import (
    MONTE_CARLO_DEFAULT_SIMS,
    MONTE_CARLO_DEFAULT_NOISE,
    MONTE_CARLO_LATENCY_BUDGET_MS
)
from config.features import FEATURE_MONTE_CARLO_ENABLED


@dataclass
class Action:
    """Represents an action to simulate."""
    action_id: str
    action_type: str
    parameters: dict
    expected_outcome: float  # Expected value 0-1


@dataclass
class SimulationResult:
    """Result of a single simulation run."""
    run_id: int
    outcome: float
    noise_applied: float
    success: bool


@dataclass
class SimulationBatch:
    """Results of a batch of simulations."""
    action_id: str
    n_simulations: int
    results: list[SimulationResult]
    total_ms: float
    outcomes: list[float] = field(default_factory=list)

    def __post_init__(self):
        self.outcomes = [r.outcome for r in self.results]


def apply_noise(value: float, noise_level: float) -> float:
    """Apply gaussian noise to a value."""
    noisy = value + random.gauss(0, noise_level)
    return max(0.0, min(1.0, noisy))


def simulate_single(
    action: Action,
    run_id: int,
    noise: float
) -> SimulationResult:
    """Run a single simulation of an action."""
    # Apply noise to expected outcome
    noisy_outcome = apply_noise(action.expected_outcome, noise)

    # Determine success based on outcome threshold
    success = noisy_outcome >= 0.5

    return SimulationResult(
        run_id=run_id,
        outcome=noisy_outcome,
        noise_applied=noise,
        success=success
    )


def simulate_action(
    action: Action,
    n_sims: int = MONTE_CARLO_DEFAULT_SIMS,
    noise: float = MONTE_CARLO_DEFAULT_NOISE,
    tenant_id: str = "default"
) -> tuple[SimulationBatch, dict]:
    """Run N simulated variations of an action.

    Returns (SimulationBatch, receipt)

    Performance: Must complete in <200ms for 100 sims.
    """
    t0 = time.perf_counter()

    if not FEATURE_MONTE_CARLO_ENABLED:
        # Shadow mode - run but don't affect decisions
        pass

    results = []
    for i in range(n_sims):
        result = simulate_single(action, i, noise)
        results.append(result)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    batch = SimulationBatch(
        action_id=action.action_id,
        n_simulations=n_sims,
        results=results,
        total_ms=elapsed_ms
    )

    # Check latency budget
    if elapsed_ms > MONTE_CARLO_LATENCY_BUDGET_MS:
        stoprule_simulation_timeout(elapsed_ms, MONTE_CARLO_LATENCY_BUDGET_MS)

    receipt = emit_receipt("monte_carlo_simulation", {
        "action_id": action.action_id,
        "n_simulations": n_sims,
        "noise_level": noise,
        "simulation_ms": elapsed_ms,
        "outcomes_hash": dual_hash(str(batch.outcomes)),
        "success_rate": sum(1 for r in results if r.success) / n_sims
    }, tenant_id=tenant_id)

    return batch, receipt


def stoprule_simulation_timeout(elapsed_ms: float, budget_ms: float):
    """Stoprule if simulation exceeds latency budget."""
    emit_receipt("anomaly", {
        "metric": "monte_carlo_latency",
        "baseline": budget_ms,
        "delta": elapsed_ms - budget_ms,
        "classification": "degradation",
        "action": "alert"
    })
