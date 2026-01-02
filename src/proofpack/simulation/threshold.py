"""Determine if variance is acceptable.

Stable = good to proceed. Unstable = needs more exploration.
"""
import time
from dataclasses import dataclass

from proofpack.core.receipt import emit_receipt
from proofpack.core.constants import MONTE_CARLO_VARIANCE_THRESHOLD
from proofpack.config.features import FEATURE_MONTE_CARLO_ENABLED


@dataclass
class StabilityResult:
    """Result of stability check."""
    is_stable: bool
    variance_score: float
    threshold: float
    margin: float  # How far from threshold


def is_stable(
    variance_score: float,
    threshold: float = MONTE_CARLO_VARIANCE_THRESHOLD
) -> bool:
    """Simple check if variance is below threshold."""
    return variance_score <= threshold


def check_stability(
    variance_score: float,
    threshold: float = MONTE_CARLO_VARIANCE_THRESHOLD,
    action_id: str = "",
    tenant_id: str = "default"
) -> tuple[StabilityResult, dict]:
    """Check if variance is acceptable for proceeding.

    Returns (StabilityResult, receipt)
    """
    t0 = time.perf_counter()

    stable = variance_score <= threshold
    margin = threshold - variance_score  # Positive = below threshold

    result = StabilityResult(
        is_stable=stable,
        variance_score=variance_score,
        threshold=threshold,
        margin=margin
    )

    elapsed_ms = (time.perf_counter() - t0) * 1000

    receipt = emit_receipt("stability_check", {
        "action_id": action_id,
        "is_stable": stable,
        "variance_score": variance_score,
        "threshold": threshold,
        "margin": margin,
        "check_ms": elapsed_ms,
        "feature_enabled": FEATURE_MONTE_CARLO_ENABLED
    }, tenant_id=tenant_id)

    return result, receipt


def stoprule_unstable_action(variance_score: float, threshold: float):
    """Stoprule if action is critically unstable."""
    if variance_score > threshold * 2:  # 2x threshold = critical
        emit_receipt("anomaly", {
            "metric": "action_stability",
            "baseline": threshold,
            "delta": variance_score - threshold,
            "classification": "violation",
            "action": "halt"
        })
