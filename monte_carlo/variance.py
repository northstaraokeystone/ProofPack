"""Calculate variance across simulations.

High variance = unstable action = lower confidence.
"""
import math
import time
from dataclasses import dataclass

from ledger.core import emit_receipt
from anchor import dual_hash


@dataclass
class VarianceResult:
    """Result of variance calculation."""
    variance_score: float
    mean_outcome: float
    std_dev: float
    min_outcome: float
    max_outcome: float
    range_spread: float


def calculate_variance(
    outcomes: list[float],
    tenant_id: str = "default"
) -> tuple[VarianceResult, dict]:
    """Calculate variance across simulation outcomes.

    Returns (VarianceResult, receipt)
    """
    t0 = time.perf_counter()

    if not outcomes:
        result = VarianceResult(
            variance_score=1.0,  # Maximum uncertainty
            mean_outcome=0.0,
            std_dev=0.0,
            min_outcome=0.0,
            max_outcome=0.0,
            range_spread=0.0
        )
        receipt = emit_receipt("variance_calculation", {
            "variance_score": 1.0,
            "mean_outcome": 0.0,
            "error": "empty_outcomes"
        }, tenant_id=tenant_id)
        return result, receipt

    n = len(outcomes)
    mean = sum(outcomes) / n

    # Calculate variance
    variance = sum((x - mean) ** 2 for x in outcomes) / n
    std_dev = math.sqrt(variance)

    min_outcome = min(outcomes)
    max_outcome = max(outcomes)
    range_spread = max_outcome - min_outcome

    # Normalize variance to 0-1 scale
    # For outcomes in [0,1], max variance is 0.25 (when half are 0 and half are 1)
    variance_score = min(variance / 0.25, 1.0)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    result = VarianceResult(
        variance_score=variance_score,
        mean_outcome=mean,
        std_dev=std_dev,
        min_outcome=min_outcome,
        max_outcome=max_outcome,
        range_spread=range_spread
    )

    receipt = emit_receipt("variance_calculation", {
        "variance_score": variance_score,
        "mean_outcome": mean,
        "std_dev": std_dev,
        "range_spread": range_spread,
        "n_outcomes": n,
        "calculation_ms": elapsed_ms,
        "outcomes_hash": dual_hash(str(outcomes))
    }, tenant_id=tenant_id)

    return result, receipt


def stoprule_high_variance(variance_score: float, threshold: float = 0.5):
    """Stoprule if variance exceeds critical threshold."""
    if variance_score > threshold:
        emit_receipt("anomaly", {
            "metric": "monte_carlo_variance",
            "baseline": threshold,
            "delta": variance_score - threshold,
            "classification": "deviation",
            "action": "escalate"
        })
