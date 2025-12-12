"""Quantum-inspired foundation: distributions, sampling, collapse.

Everything is a wave, not an event. This module provides the primitives
for representing uncertainty and sampling decisions from distributions.

Research anchors:
- QED v7:461-462: simulate_superposition(), simulate_measurement(), wavefunction_collapse()
- QED v7:540-541: Shannon entropy H = -Σ p(x) log p(x)
- QED v7:346-347: Selection samples from fitness distributions (mean, variance)
"""
import math
import random
from dataclasses import dataclass, field
from typing import Literal

from ledger.core import emit_receipt, StopRule


# === STATE ENUM - Probability amplitudes until measured ===
StateType = Literal["SUPERPOSITION", "ACTIVE", "DORMANT", "COLLAPSED"]


@dataclass
class FitnessDistribution:
    """A value we're uncertain about: mean + variance + observation count.

    This is the core primitive. NOT a scalar. A wave of possibility.
    Uses Beta distribution for bounded [0,1] outcomes (success rates).
    Uses Normal approximation for unbounded metrics.
    """
    alpha: float = 1.0  # Beta prior: successes + 1
    beta: float = 1.0   # Beta prior: failures + 1
    n_observations: int = 0
    sum_values: float = 0.0
    sum_squared: float = 0.0

    @property
    def mean(self) -> float:
        """Expected value of the distribution."""
        if self.n_observations == 0:
            return self.alpha / (self.alpha + self.beta)  # Prior mean
        return self.sum_values / self.n_observations

    @property
    def variance(self) -> float:
        """Uncertainty in our belief. High variance = we don't know."""
        if self.n_observations < 2:
            # Prior variance for Beta(alpha, beta)
            a, b = self.alpha, self.beta
            return (a * b) / ((a + b) ** 2 * (a + b + 1))
        mean = self.mean
        return (self.sum_squared / self.n_observations) - mean ** 2

    @property
    def confidence(self) -> float:
        """How sure are we? Inverse of variance, bounded [0,1]."""
        # More observations = more confidence
        # Lower variance = more confidence
        var = max(self.variance, 1e-10)
        obs_factor = min(1.0, self.n_observations / 30)  # Asymptotic approach
        var_factor = 1.0 / (1.0 + var * 10)
        return obs_factor * var_factor

    def update(self, value: float, success: bool = True) -> "FitnessDistribution":
        """Bayesian update with new evidence. Returns updated distribution."""
        new_alpha = self.alpha + (1 if success else 0)
        new_beta = self.beta + (0 if success else 1)
        new_n = self.n_observations + 1
        new_sum = self.sum_values + value
        new_sum_sq = self.sum_squared + value ** 2

        return FitnessDistribution(
            alpha=new_alpha,
            beta=new_beta,
            n_observations=new_n,
            sum_values=new_sum,
            sum_squared=new_sum_sq
        )

    def sample_thompson(self) -> float:
        """Thompson sampling: draw from posterior to balance explore/exploit.

        High variance patterns get explored; known-good patterns get exploited.
        This is Shannon 1948, not metaphor.
        """
        # Sample from Beta(alpha, beta) for bounded [0,1] outcomes
        try:
            return random.betavariate(self.alpha, self.beta)
        except ValueError:
            return self.mean


@dataclass
class Superposition:
    """A state that exists as probability amplitudes until measured.

    Before human approval, helpers exist in superposition.
    Measurement collapses to definite state.
    """
    state: StateType = "SUPERPOSITION"
    amplitude_active: float = 0.5    # |active⟩ probability amplitude
    amplitude_dormant: float = 0.5   # |dormant⟩ probability amplitude
    collapse_time: float | None = None
    collapse_reason: str | None = None

    def probability_active(self) -> float:
        """P(active) = |amplitude_active|^2 normalized."""
        total = self.amplitude_active ** 2 + self.amplitude_dormant ** 2
        if total == 0:
            return 0.5
        return (self.amplitude_active ** 2) / total

    def evolve(self, evidence_for_active: float) -> "Superposition":
        """Evolve amplitudes based on evidence. Not collapse, just rotation."""
        # Evidence shifts probability amplitudes
        new_active = self.amplitude_active * (1 + evidence_for_active)
        new_dormant = self.amplitude_dormant * (1 - evidence_for_active)
        # Normalize
        norm = math.sqrt(new_active ** 2 + new_dormant ** 2)
        if norm > 0:
            new_active /= norm
            new_dormant /= norm
        return Superposition(
            state="SUPERPOSITION",
            amplitude_active=new_active,
            amplitude_dormant=new_dormant
        )


def shannon_entropy(probabilities: list[float]) -> float:
    """H = -Σ p(x) log p(x) - Shannon 1948.

    Measures uncertainty/information content.
    High entropy = lots of uncertainty = need more observation.
    Low entropy = stable = can coast.
    """
    h = 0.0
    for p in probabilities:
        if p > 0:
            h -= p * math.log2(p)
    return h


def entropy_delta(prev_entropy: float, curr_entropy: float) -> float:
    """If delta < 0, system is degrading. Protective action triggered."""
    return curr_entropy - prev_entropy


def collapse_state(
    superposition: Superposition,
    measurement: Literal["approve", "reject", "timeout"],
    reason: str,
    ts: float
) -> Superposition:
    """Measurement collapses the wave function to a definite state.

    The approval isn't comparing risk to threshold. It's SAMPLING from
    risk_distribution and SAMPLING from threshold_distribution.
    """
    if measurement == "approve":
        new_state = "ACTIVE"
    elif measurement == "reject":
        new_state = "DORMANT"
    else:  # timeout - probabilistic collapse
        if random.random() < superposition.probability_active():
            new_state = "ACTIVE"
        else:
            new_state = "DORMANT"

    return Superposition(
        state=new_state,
        amplitude_active=1.0 if new_state == "ACTIVE" else 0.0,
        amplitude_dormant=0.0 if new_state == "ACTIVE" else 1.0,
        collapse_time=ts,
        collapse_reason=reason
    )


def exponential_decay(
    time_since_last_activity: float,
    decay_rate: float
) -> float:
    """P(active) = e^(-λt) - Not a hard cutoff that destroys information.

    days = 29 has a survival chance, not instant death at day 30.
    """
    return math.exp(-decay_rate * time_since_last_activity)


def sample_from_distributions(
    dist_a: FitnessDistribution,
    dist_b: FitnessDistribution
) -> tuple[float, float]:
    """Sample from two distributions for comparison.

    Sometimes a 0.19 risk gets flagged. Sometimes a 0.21 auto-approves.
    That's not a bug—that's exploration at the boundaries.
    """
    return dist_a.sample_thompson(), dist_b.sample_thompson()


def emit_quantum_receipt(
    action: str,
    distribution: FitnessDistribution,
    superposition: Superposition | None = None,
    tenant_id: str = "default"
) -> dict:
    """Emit receipt for quantum state operations."""
    data = {
        "action": action,
        "distribution": {
            "mean": distribution.mean,
            "variance": distribution.variance,
            "confidence": distribution.confidence,
            "n_observations": distribution.n_observations,
            "alpha": distribution.alpha,
            "beta": distribution.beta
        }
    }
    if superposition:
        data["superposition"] = {
            "state": superposition.state,
            "p_active": superposition.probability_active(),
            "amplitude_active": superposition.amplitude_active,
            "amplitude_dormant": superposition.amplitude_dormant,
            "collapse_time": superposition.collapse_time,
            "collapse_reason": superposition.collapse_reason
        }
    return emit_receipt("quantum_state", data, tenant_id=tenant_id)


def stoprule_entropy_violation(current: float, threshold_dist: FitnessDistribution):
    """Stoprule when entropy conservation is violated."""
    sampled_threshold = threshold_dist.sample_thompson()
    if current < sampled_threshold:
        emit_receipt("anomaly", {
            "metric": "entropy_conservation",
            "baseline": sampled_threshold,
            "delta": current - sampled_threshold,
            "classification": "degradation",
            "action": "escalate"
        })
        raise StopRule(f"Entropy violation: {current} < {sampled_threshold}")
