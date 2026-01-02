"""Stream observation - sensing the receipt stream.

The sense module observes without collapsing. It gathers evidence
for distributions without making hard decisions.

Everything observed becomes a probability update, not a state change.
"""
import time
from dataclasses import dataclass, field
from collections import defaultdict

from core.receipt import emit_receipt, StopRule
from loop.src.quantum import FitnessDistribution, shannon_entropy


@dataclass
class ObservationWindow:
    """A window of observations with uncertainty tracking."""
    receipts: list[dict] = field(default_factory=list)
    type_distributions: dict[str, FitnessDistribution] = field(default_factory=dict)
    timing_distribution: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=2, beta=2)
    )
    gap_evidence: list[dict] = field(default_factory=list)


def observe_stream(
    stream: list[dict],
    window: ObservationWindow,
    tenant_id: str = "default"
) -> tuple[dict, ObservationWindow]:
    """Observe receipt stream, update distributions, don't collapse.

    This is pure observation - gathering evidence without judgment.
    """
    t0 = time.perf_counter()

    # Track type occurrences
    type_counts: dict[str, int] = defaultdict(int)
    timestamps: list[float] = []
    gaps_detected: list[dict] = []

    for receipt in stream:
        rtype = receipt.get("receipt_type", "unknown")
        type_counts[rtype] += 1

        ts = receipt.get("ts")
        if ts:
            timestamps.append(float(ts) if isinstance(ts, (int, float)) else time.time())

        # Look for gap signals
        if receipt.get("classification") == "deviation":
            gaps_detected.append({
                "receipt_type": rtype,
                "ts": ts,
                "metric": receipt.get("metric", "unknown")
            })

    # Update type distributions
    new_type_dists = dict(window.type_distributions)
    for rtype, count in type_counts.items():
        if rtype not in new_type_dists:
            new_type_dists[rtype] = FitnessDistribution()
        # Update distribution with observation
        frequency = count / max(len(stream), 1)
        new_type_dists[rtype] = new_type_dists[rtype].update(frequency, success=count > 0)

    # Update timing distribution if we have timestamps
    new_timing_dist = window.timing_distribution
    if len(timestamps) >= 2:
        timestamps.sort()
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            # Normalize to [0,1] range for beta distribution
            normalized = min(1.0, avg_interval / 3600)  # 1 hour as reference
            new_timing_dist = window.timing_distribution.update(normalized, success=True)

    # Compute stream characteristics
    entropy = shannon_entropy([c / len(stream) for c in type_counts.values()]) if stream else 0.0

    # Signal-to-noise estimation
    signal_types = {"anomaly", "bias", "impact", "decision_health"}
    signal_count = sum(type_counts.get(t, 0) for t in signal_types)
    noise_count = len(stream) - signal_count
    snr = signal_count / max(noise_count, 1)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    new_window = ObservationWindow(
        receipts=window.receipts[-1000:] + stream,  # Rolling window
        type_distributions=new_type_dists,
        timing_distribution=new_timing_dist,
        gap_evidence=window.gap_evidence + gaps_detected
    )

    receipt = emit_receipt("observation", {
        "stream_size": len(stream),
        "unique_types": len(type_counts),
        "type_distribution": {k: v for k, v in type_counts.items()},
        "entropy": entropy,
        "signal_to_noise_ratio": snr,
        "gaps_detected": len(gaps_detected),
        "timing_confidence": new_timing_dist.confidence,
        "observation_duration_ms": elapsed_ms,
        "distributions_updated": list(new_type_dists.keys())
    }, tenant_id=tenant_id)

    return receipt, new_window


def sense_anomaly_evidence(
    window: ObservationWindow,
    metric: str,
    tenant_id: str = "default"
) -> tuple[FitnessDistribution, dict]:
    """Sense evidence for a specific anomaly metric.

    Returns a distribution representing our belief about the metric,
    NOT a scalar decision.
    """
    # Find relevant receipts
    relevant = [
        r for r in window.receipts
        if r.get("metric") == metric or r.get("receipt_type") == metric
    ]

    if not relevant:
        # No evidence - return prior (maximum uncertainty)
        prior = FitnessDistribution(alpha=1, beta=1)
        receipt = emit_receipt("sense_evidence", {
            "metric": metric,
            "evidence_count": 0,
            "distribution": {
                "mean": prior.mean,
                "variance": prior.variance,
                "confidence": prior.confidence
            },
            "verdict": "insufficient_evidence"
        }, tenant_id=tenant_id)
        return prior, receipt

    # Build distribution from evidence
    dist = FitnessDistribution()
    for r in relevant:
        delta = r.get("delta", 0)
        # Negative delta = failure, positive = success
        success = delta >= 0
        normalized_delta = min(1.0, max(0.0, abs(delta)))
        dist = dist.update(normalized_delta, success=success)

    receipt = emit_receipt("sense_evidence", {
        "metric": metric,
        "evidence_count": len(relevant),
        "distribution": {
            "mean": dist.mean,
            "variance": dist.variance,
            "confidence": dist.confidence
        },
        "verdict": "evidence_gathered"
    }, tenant_id=tenant_id)

    return dist, receipt


def sense_gap_signals(
    window: ObservationWindow,
    tenant_id: str = "default"
) -> tuple[list[dict], dict]:
    """Identify gap signals from observation window.

    Gaps are patterns that might benefit from automation.
    Each gap has a distribution of evidence, not a hard count.
    """
    # Group gaps by metric/pattern
    gap_groups: dict[str, list[dict]] = defaultdict(list)
    for gap in window.gap_evidence:
        key = f"{gap.get('receipt_type', 'unknown')}:{gap.get('metric', 'unknown')}"
        gap_groups[key] += [gap]

    # Convert groups to distributions
    gap_signals = []
    for key, gaps in gap_groups.items():
        # Each occurrence is evidence - build distribution
        dist = FitnessDistribution()
        for g in gaps:
            dist = dist.update(1.0, success=True)  # Each gap is evidence of pattern

        gap_signals.append({
            "pattern_key": key,
            "evidence_count": len(gaps),
            "confidence": dist.confidence,
            "distribution": {
                "mean": dist.mean,
                "variance": dist.variance,
                "alpha": dist.alpha,
                "beta": dist.beta
            }
        })

    receipt = emit_receipt("gap_signals", {
        "total_gaps": len(window.gap_evidence),
        "unique_patterns": len(gap_signals),
        "signals": gap_signals
    }, tenant_id=tenant_id)

    return gap_signals, receipt


def stoprule_observation_overflow(window_size: int, max_dist: FitnessDistribution):
    """Stoprule if observation window grows too large."""
    sampled_max = max_dist.sample_thompson() * 10000  # Scale appropriately
    if window_size > sampled_max:
        emit_receipt("anomaly", {
            "metric": "observation_window",
            "baseline": sampled_max,
            "delta": window_size - sampled_max,
            "classification": "deviation",
            "action": "compact"
        })
        raise StopRule(f"Observation window overflow: {window_size} > {sampled_max}")
