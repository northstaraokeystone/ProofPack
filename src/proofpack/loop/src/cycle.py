"""Adaptive heartbeat - the cycle IS the system observing itself.

Observation frequency matches information density.
High entropy = lots happening = observe more.
Low entropy = stable = coast.

Research anchor (QED v7:305-308):
"Every cycle computes Shannon entropy of receipt stream. If cycle_entropy_delta < 0,
system is degrading. Protective action triggered."

Baseline assumption BROKEN: Cycle does NOT run every 60 seconds.
The interval adapts based on entropy gradient.
"""
import time
from dataclasses import dataclass, field

from proofpack.core.receipt import StopRule, emit_receipt
from proofpack.loop.src.quantum import (
    FitnessDistribution,
    entropy_delta,
    shannon_entropy,
    stoprule_entropy_violation,
)


@dataclass
class CycleState:
    """Adaptive cycle state - interval is a distribution, not a constant."""
    # Interval bounds (not fixed values!)
    min_interval_ms: float = 1000.0    # 1 second minimum
    max_interval_ms: float = 300000.0  # 5 minutes maximum

    # Current learned interval distribution
    interval_distribution: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=2, beta=2)
    )

    # Entropy tracking (start at 0.0 to avoid initial degradation detection)
    prev_entropy: float = 0.0
    entropy_history: list[float] = field(default_factory=list)

    # Adaptive parameters (themselves distributions!)
    responsiveness: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=5, beta=5)
    )


def compute_stream_entropy(receipts: list[dict]) -> float:
    """Compute Shannon entropy of receipt type distribution."""
    if not receipts:
        return 0.0

    type_counts: dict[str, int] = {}
    for r in receipts:
        rtype = r.get("receipt_type", "unknown")
        type_counts[rtype] = type_counts.get(rtype, 0) + 1

    total = len(receipts)
    probabilities = [count / total for count in type_counts.values()]

    return shannon_entropy(probabilities)


def compute_next_interval(
    state: CycleState,
    current_entropy: float
) -> tuple[float, CycleState]:
    """Compute next cycle interval based on entropy gradient.

    High entropy delta (system changing fast) → shorter interval
    Low entropy delta (system stable) → longer interval
    Negative delta (degrading) → protective response
    """
    delta = entropy_delta(state.prev_entropy, current_entropy)

    # Sample responsiveness from distribution - how quickly should we adapt?
    responsiveness = state.responsiveness.sample_thompson()

    # Entropy-driven interval calculation
    # High entropy (lots happening) → observe more frequently
    # Low entropy (stable) → can coast
    if current_entropy > 0:
        # Higher entropy → shorter interval
        entropy_factor = 1.0 / (1.0 + current_entropy)
    else:
        entropy_factor = 1.0

    # Delta-driven adaptation
    # Negative delta (degrading) → much shorter interval
    # Positive delta (improving) → can relax slightly
    if delta < 0:
        delta_factor = 0.5  # Double observation frequency when degrading
    elif delta > 0.1:
        delta_factor = 1.5  # Relax when stable/improving
    else:
        delta_factor = 1.0

    # Sample base interval from distribution
    base_interval = state.interval_distribution.sample_thompson()

    # Scale to actual interval range
    interval_range = state.max_interval_ms - state.min_interval_ms
    scaled_base = state.min_interval_ms + (base_interval * interval_range)

    # Apply entropy and delta factors with responsiveness
    adapted_interval = scaled_base * entropy_factor * delta_factor
    adapted_interval = adapted_interval ** (1 - responsiveness * 0.5)  # Responsiveness dampens

    # Bound to valid range
    next_interval = max(state.min_interval_ms, min(state.max_interval_ms, adapted_interval))

    # Update state
    new_history = state.entropy_history[-100:] + [current_entropy]  # Keep last 100

    # Learn from this cycle - did we observe something useful?
    # If entropy changed significantly, this interval was informative
    information_gain = abs(delta)
    was_useful = information_gain > 0.01

    new_interval_dist = state.interval_distribution.update(
        base_interval,
        success=was_useful
    )

    new_state = CycleState(
        min_interval_ms=state.min_interval_ms,
        max_interval_ms=state.max_interval_ms,
        interval_distribution=new_interval_dist,
        prev_entropy=current_entropy,
        entropy_history=new_history,
        responsiveness=state.responsiveness
    )

    return next_interval, new_state


def run_cycle(
    receipts: list[dict],
    state: CycleState,
    tenant_id: str = "default"
) -> tuple[dict, CycleState]:
    """Execute one observation cycle.

    Returns cycle_receipt and updated state.
    """
    t0 = time.perf_counter()

    # Compute current entropy
    current_entropy = compute_stream_entropy(receipts)

    # Compute entropy delta
    delta = entropy_delta(state.prev_entropy, current_entropy)

    # Check for degradation
    if delta < -0.3:  # Significant negative delta
        # Sample from threshold distribution - not a hard cutoff!
        threshold_dist = FitnessDistribution(alpha=3, beta=7)  # Biased toward caution
        sampled_threshold = threshold_dist.sample_thompson()
        if abs(delta) > sampled_threshold:
            stoprule_entropy_violation(delta, threshold_dist)

    # Compute next interval
    next_interval, new_state = compute_next_interval(state, current_entropy)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    receipt = emit_receipt("cycle", {
        "stream_size": len(receipts),
        "entropy": current_entropy,
        "entropy_delta": delta,
        "prev_entropy": state.prev_entropy,
        "interval_used_ms": elapsed_ms,
        "next_interval_ms": next_interval,
        "interval_distribution": {
            "mean": new_state.interval_distribution.mean,
            "variance": new_state.interval_distribution.variance,
            "confidence": new_state.interval_distribution.confidence
        },
        "entropy_trend": _compute_trend(new_state.entropy_history),
        "degradation_detected": delta < -0.1
    }, tenant_id=tenant_id)

    return receipt, new_state


def _compute_trend(history: list[float]) -> str:
    """Compute entropy trend from history."""
    if len(history) < 3:
        return "insufficient_data"

    recent = history[-5:]
    older = history[-10:-5] if len(history) >= 10 else history[:len(history)//2]

    if not older:
        return "insufficient_data"

    recent_avg = sum(recent) / len(recent)
    older_avg = sum(older) / len(older)

    diff = recent_avg - older_avg
    if diff > 0.1:
        return "increasing"
    elif diff < -0.1:
        return "decreasing"
    else:
        return "stable"


def stoprule_cycle_timeout(elapsed_ms: float, max_dist: FitnessDistribution):
    """Stoprule if cycle takes too long - but threshold is sampled!"""
    sampled_max = max_dist.sample_thompson() * 10000  # Scale to ms
    if elapsed_ms > sampled_max:
        emit_receipt("anomaly", {
            "metric": "cycle_duration",
            "baseline": sampled_max,
            "delta": elapsed_ms - sampled_max,
            "classification": "deviation",
            "action": "alert"
        })
        raise StopRule(f"Cycle timeout: {elapsed_ms}ms > {sampled_max}ms")
