"""Pattern harvesting - signal detection, not counting.

Research anchor (QED v7:393-394):
"Identifies recurring patterns (> 5 occurrences, median resolve > 30 min)"

BASELINE ASSUMPTIONS BROKEN:
- NOT hard cutoffs at 5 occurrences and 30 minutes
- 3 occurrences with tight variance might be more actionable than 10 with wild variance
- Occurrence count × resolve time is EVIDENCE with CONFIDENCE
- Let the distribution tell you

The signal-to-noise ratio of a gap pattern is the true measure.
"""
import time
from dataclasses import dataclass, field

from core.receipt import emit_receipt, StopRule
from loop.src.quantum import FitnessDistribution


@dataclass
class PatternEvidence:
    """Evidence for a pattern - distribution, not counts."""
    pattern_id: str
    occurrence_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=1, beta=1)
    )
    resolve_time_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=1, beta=1)
    )
    severity_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=1, beta=1)
    )
    timestamps: list[float] = field(default_factory=list)
    resolve_times: list[float] = field(default_factory=list)

    def update_occurrence(self, ts: float) -> "PatternEvidence":
        """Record an occurrence - Bayesian update."""
        new_occ = self.occurrence_dist.update(1.0, success=True)
        return PatternEvidence(
            pattern_id=self.pattern_id,
            occurrence_dist=new_occ,
            resolve_time_dist=self.resolve_time_dist,
            severity_dist=self.severity_dist,
            timestamps=self.timestamps + [ts],
            resolve_times=self.resolve_times
        )

    def update_resolve(self, resolve_minutes: float) -> "PatternEvidence":
        """Record a resolution time - update distribution."""
        # Normalize to [0,1] - 4 hours (240 min) as reference max
        normalized = min(1.0, resolve_minutes / 240.0)
        # Longer resolve time = worse (failure in the "quick resolution" sense)
        success = resolve_minutes < 60  # Under an hour is "success"
        new_resolve = self.resolve_time_dist.update(normalized, success=success)
        return PatternEvidence(
            pattern_id=self.pattern_id,
            occurrence_dist=self.occurrence_dist,
            resolve_time_dist=new_resolve,
            severity_dist=self.severity_dist,
            timestamps=self.timestamps,
            resolve_times=self.resolve_times + [resolve_minutes]
        )

    @property
    def actionability_score(self) -> float:
        """How actionable is this pattern? Sample from distributions.

        3 times with 4 hours each >> 100 times with wild variance
        """
        # Thompson sample from each dimension
        occurrence_sample = self.occurrence_dist.sample_thompson()
        resolve_sample = self.resolve_time_dist.sample_thompson()

        # High occurrence + high resolve time = highly actionable
        # But variance matters! Low variance = more confident = more actionable
        occurrence_confidence = self.occurrence_dist.confidence
        resolve_confidence = self.resolve_time_dist.confidence

        # Weighted by confidence
        actionability = (
            occurrence_sample * occurrence_confidence +
            resolve_sample * resolve_confidence
        ) / 2.0

        return actionability

    @property
    def posterior_confidence(self) -> float:
        """Overall confidence in this pattern being real and automatable."""
        # Combine confidences from all distributions
        confidences = [
            self.occurrence_dist.confidence,
            self.resolve_time_dist.confidence
        ]
        return sum(confidences) / len(confidences)


def harvest_patterns(
    gap_signals: list[dict],
    existing_patterns: dict[str, PatternEvidence],
    tenant_id: str = "default"
) -> tuple[dict, dict[str, PatternEvidence]]:
    """Harvest patterns from gap signals.

    Updates pattern evidence distributions, doesn't make hard decisions.
    """
    t0 = time.perf_counter()
    ts_now = time.time()

    # Update existing patterns with new evidence
    updated_patterns = dict(existing_patterns)

    for signal in gap_signals:
        pattern_id = signal.get("pattern_key", "unknown")

        if pattern_id not in updated_patterns:
            updated_patterns[pattern_id] = PatternEvidence(pattern_id=pattern_id)

        # Update with occurrence
        updated_patterns[pattern_id] = updated_patterns[pattern_id].update_occurrence(ts_now)

        # If we have resolve time data, update that too
        if "resolve_minutes" in signal:
            updated_patterns[pattern_id] = updated_patterns[pattern_id].update_resolve(
                signal["resolve_minutes"]
            )

    # Compute actionability for all patterns
    actionable_patterns = []
    for pid, pattern in updated_patterns.items():
        actionable_patterns.append({
            "pattern_id": pid,
            "actionability": pattern.actionability_score,
            "posterior_confidence": pattern.posterior_confidence,
            "occurrences": pattern.occurrence_dist.n_observations,
            "occurrence_confidence": pattern.occurrence_dist.confidence,
            "resolve_time_mean": pattern.resolve_time_dist.mean,
            "resolve_time_variance": pattern.resolve_time_dist.variance
        })

    # Sort by actionability (sampled, so order may vary!)
    actionable_patterns.sort(key=lambda x: x["actionability"], reverse=True)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    receipt = emit_receipt("harvest", {
        "signals_processed": len(gap_signals),
        "patterns_total": len(updated_patterns),
        "actionable_patterns": actionable_patterns[:10],  # Top 10
        "harvest_duration_ms": elapsed_ms,
        "posterior_confidence": sum(p["posterior_confidence"] for p in actionable_patterns) / max(len(actionable_patterns), 1)
    }, tenant_id=tenant_id)

    return receipt, updated_patterns


def compute_signal_to_noise(
    pattern: PatternEvidence,
    background_dist: FitnessDistribution
) -> float:
    """Compute signal-to-noise ratio for a pattern.

    Signal = pattern's occurrence rate
    Noise = background variation
    """
    signal = pattern.occurrence_dist.sample_thompson()
    noise = background_dist.sample_thompson()

    if noise < 0.001:
        return signal * 1000  # Very low noise = high SNR
    return signal / noise


def select_patterns_for_genesis(
    patterns: dict[str, PatternEvidence],
    budget_dist: FitnessDistribution,
    tenant_id: str = "default"
) -> tuple[list[PatternEvidence], dict]:
    """Select patterns for helper genesis using Thompson sampling.

    NOT a hard threshold. Sample from actionability distributions.
    High-variance patterns get explored; known-good get exploited.
    """
    # Thompson sample from each pattern
    sampled_scores = []
    for pid, pattern in patterns.items():
        # Sample actionability - exploration happens here
        sampled = pattern.actionability_score  # Already uses Thompson sampling
        sampled_scores.append((pid, pattern, sampled))

    # Sort by sampled score
    sampled_scores.sort(key=lambda x: x[2], reverse=True)

    # Sample budget from distribution
    budget_sample = budget_dist.sample_thompson()
    num_to_select = max(1, int(budget_sample * len(patterns)))

    selected = [p for _, p, _ in sampled_scores[:num_to_select]]

    receipt = emit_receipt("pattern_selection", {
        "total_patterns": len(patterns),
        "budget_sample": budget_sample,
        "selected_count": len(selected),
        "selected_patterns": [
            {
                "pattern_id": p.pattern_id,
                "actionability": p.actionability_score,
                "confidence": p.posterior_confidence
            }
            for p in selected
        ]
    }, tenant_id=tenant_id)

    return selected, receipt


def stoprule_pattern_explosion(
    pattern_count: int,
    max_dist: FitnessDistribution
):
    """Stoprule if too many patterns emerge - entropy overload."""
    sampled_max = max_dist.sample_thompson() * 1000
    if pattern_count > sampled_max:
        emit_receipt("anomaly", {
            "metric": "pattern_count",
            "baseline": sampled_max,
            "delta": pattern_count - sampled_max,
            "classification": "deviation",
            "action": "prune"
        })
        raise StopRule(f"Pattern explosion: {pattern_count} > {sampled_max}")
