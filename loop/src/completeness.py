"""Completeness - asymptotic truth.

Research anchor (QED v7:406-412):
"Five levels: L0-L4. When L4 feeds back into L0, system can verify its own correctness."

Research anchor (QED v7:567-568):
"godel_layer() returns 'L0'. Base layer hits undecidability first."

BASELINE ASSUMPTION BROKEN:
- NOT self_verifying = (all_levels >= 0.999)
- Coverage can NEVER actually reach 1.0 (Gödel says no)
- Coverage approaches 1.0 asymptotically
- Self-verification is PROBABILISTIC

There's always a receipt type you haven't seen yet.
Self-verification is P(system can verify itself | observations).
The system is honest about its own uncertainty.
"""
import time
import math
from dataclasses import dataclass, field
from typing import Literal

from ledger.core import emit_receipt, StopRule
from loop.src.quantum import FitnessDistribution, shannon_entropy


Level = Literal["L0", "L1", "L2", "L3", "L4"]


@dataclass
class LevelCoverage:
    """Coverage for a single level - asymptotic, never 1.0."""
    level: Level
    coverage_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=1, beta=1)
    )
    receipt_types_seen: set[str] = field(default_factory=set)
    verification_attempts: int = 0
    verification_successes: int = 0

    def asymptotic_coverage(self) -> float:
        """Coverage approaches but never reaches 1.0.

        f(n) = 1 - 1/(1 + n) where n = types seen
        At n=0: f(0) = 0
        At n=∞: f(∞) → 1 (but never reaches)
        """
        n = len(self.receipt_types_seen)
        return 1.0 - 1.0 / (1.0 + n)

    def update_with_receipt(self, receipt_type: str) -> "LevelCoverage":
        """Update coverage with new receipt type observation."""
        new_seen = self.receipt_types_seen | {receipt_type}
        new_dist = self.coverage_dist.update(
            self.asymptotic_coverage(),
            success=True
        )
        return LevelCoverage(
            level=self.level,
            coverage_dist=new_dist,
            receipt_types_seen=new_seen,
            verification_attempts=self.verification_attempts,
            verification_successes=self.verification_successes
        )

    def update_with_verification(self, success: bool) -> "LevelCoverage":
        """Update after verification attempt."""
        return LevelCoverage(
            level=self.level,
            coverage_dist=self.coverage_dist.update(1.0 if success else 0.0, success),
            receipt_types_seen=self.receipt_types_seen,
            verification_attempts=self.verification_attempts + 1,
            verification_successes=self.verification_successes + (1 if success else 0)
        )


@dataclass
class CompletenessState:
    """System completeness across all levels."""
    l0: LevelCoverage = field(default_factory=lambda: LevelCoverage(level="L0"))
    l1: LevelCoverage = field(default_factory=lambda: LevelCoverage(level="L1"))
    l2: LevelCoverage = field(default_factory=lambda: LevelCoverage(level="L2"))
    l3: LevelCoverage = field(default_factory=lambda: LevelCoverage(level="L3"))
    l4: LevelCoverage = field(default_factory=lambda: LevelCoverage(level="L4"))

    # Self-verification probability distribution
    self_verify_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=1, beta=9)  # Start skeptical
    )

    def get_level(self, level: Level) -> LevelCoverage:
        """Get coverage for a specific level."""
        return {"L0": self.l0, "L1": self.l1, "L2": self.l2, "L3": self.l3, "L4": self.l4}[level]


def godel_layer() -> Level:
    """Base layer hits undecidability first.

    L0 is where the fundamental limits live.
    There will always be statements the system cannot prove about itself.
    """
    return "L0"


def asymptotic_limit(coverage: float) -> float:
    """The gap to perfect coverage - always positive, shrinking.

    gap(c) = 1 - c
    As c → 1, gap → 0 but gap > 0 always (Gödel)
    """
    return 1.0 - coverage


def compute_self_verification_probability(
    state: CompletenessState
) -> float:
    """P(system can verify itself) given current observations.

    NOT a boolean. A probability that asymptotically approaches
    but never reaches 1.0.
    """
    # Aggregate coverage across levels
    coverages = [
        state.l0.asymptotic_coverage(),
        state.l1.asymptotic_coverage(),
        state.l2.asymptotic_coverage(),
        state.l3.asymptotic_coverage(),
        state.l4.asymptotic_coverage()
    ]

    # L4 must feed back to L0 for self-verification
    l4_coverage = state.l4.asymptotic_coverage()
    l0_coverage = state.l0.asymptotic_coverage()
    feedback_strength = l4_coverage * l0_coverage

    # Overall self-verification probability
    # Product of coverages * feedback * sample from distribution
    product = math.prod(coverages) if all(c > 0 for c in coverages) else 0.0
    p_verify = product * feedback_strength * state.self_verify_dist.sample_thompson()

    # Asymptotic - can never be exactly 1.0
    return min(0.999999, p_verify)


def update_completeness(
    state: CompletenessState,
    receipts: list[dict],
    tenant_id: str = "default"
) -> tuple[CompletenessState, dict]:
    """Update completeness state with new receipts.

    Each new receipt type observed increases coverage asymptotically.
    """
    # Classify receipts to levels
    level_map = {
        "ingest": "L0",
        "anchor": "L0",
        "scan": "L1",
        "observation": "L1",
        "harvest": "L2",
        "helper_blueprint": "L2",
        "backtest": "L2",
        "effectiveness": "L3",
        "approval": "L3",
        "meta_fitness": "L4",
        "completeness": "L4",
        "anomaly": "L0",  # Anomalies feed back to base
        "cycle": "L1"
    }

    # Update each level
    new_l0, new_l1, new_l2, new_l3, new_l4 = state.l0, state.l1, state.l2, state.l3, state.l4

    for receipt in receipts:
        rtype = receipt.get("receipt_type", "unknown")
        level = level_map.get(rtype, "L0")

        if level == "L0":
            new_l0 = new_l0.update_with_receipt(rtype)
        elif level == "L1":
            new_l1 = new_l1.update_with_receipt(rtype)
        elif level == "L2":
            new_l2 = new_l2.update_with_receipt(rtype)
        elif level == "L3":
            new_l3 = new_l3.update_with_receipt(rtype)
        elif level == "L4":
            new_l4 = new_l4.update_with_receipt(rtype)

    new_state = CompletenessState(
        l0=new_l0,
        l1=new_l1,
        l2=new_l2,
        l3=new_l3,
        l4=new_l4,
        self_verify_dist=state.self_verify_dist
    )

    p_self_verify = compute_self_verification_probability(new_state)

    receipt = emit_receipt("completeness", {
        "level_coverages": {
            "L0": new_l0.asymptotic_coverage(),
            "L1": new_l1.asymptotic_coverage(),
            "L2": new_l2.asymptotic_coverage(),
            "L3": new_l3.asymptotic_coverage(),
            "L4": new_l4.asymptotic_coverage()
        },
        "asymptotic_gaps": {
            "L0": asymptotic_limit(new_l0.asymptotic_coverage()),
            "L1": asymptotic_limit(new_l1.asymptotic_coverage()),
            "L2": asymptotic_limit(new_l2.asymptotic_coverage()),
            "L3": asymptotic_limit(new_l3.asymptotic_coverage()),
            "L4": asymptotic_limit(new_l4.asymptotic_coverage())
        },
        "p_self_verification": p_self_verify,
        "godel_layer": godel_layer(),
        "total_receipt_types_seen": sum([
            len(new_l0.receipt_types_seen),
            len(new_l1.receipt_types_seen),
            len(new_l2.receipt_types_seen),
            len(new_l3.receipt_types_seen),
            len(new_l4.receipt_types_seen)
        ]),
        "feedback_active": new_l4.asymptotic_coverage() > 0 and new_l0.asymptotic_coverage() > 0
    }, tenant_id=tenant_id)

    return new_state, receipt


def attempt_self_verification(
    state: CompletenessState,
    tenant_id: str = "default"
) -> tuple[bool, CompletenessState, dict]:
    """Attempt self-verification.

    Result is probabilistic. Success updates our belief.
    Failure also updates our belief.
    """
    p_success = compute_self_verification_probability(state)

    # Sample whether this attempt succeeds
    import random
    success = random.random() < p_success

    # Update L0 (base layer) with verification result
    new_l0 = state.l0.update_with_verification(success)

    # Update self-verification distribution
    new_self_verify = state.self_verify_dist.update(
        p_success,
        success=success
    )

    new_state = CompletenessState(
        l0=new_l0,
        l1=state.l1,
        l2=state.l2,
        l3=state.l3,
        l4=state.l4,
        self_verify_dist=new_self_verify
    )

    receipt = emit_receipt("self_verification_attempt", {
        "p_success_before": p_success,
        "success": success,
        "verification_attempts": new_l0.verification_attempts,
        "verification_successes": new_l0.verification_successes,
        "self_verify_confidence": new_self_verify.confidence,
        "godel_limit_acknowledged": True,
        "asymptotic_note": "Coverage can never reach 1.0"
    }, tenant_id=tenant_id)

    return success, new_state, receipt


def compute_completeness_entropy(state: CompletenessState) -> float:
    """Entropy across coverage levels.

    High entropy = coverages are uneven = focus needed
    Low entropy = coverages are balanced = healthy
    """
    coverages = [
        state.l0.asymptotic_coverage(),
        state.l1.asymptotic_coverage(),
        state.l2.asymptotic_coverage(),
        state.l3.asymptotic_coverage(),
        state.l4.asymptotic_coverage()
    ]

    # Normalize to probabilities
    total = sum(coverages)
    if total == 0:
        return 0.0

    probs = [c / total for c in coverages]
    return shannon_entropy(probs)


def stoprule_completeness_regression(
    new_coverage: float,
    old_coverage: float,
    threshold_dist: FitnessDistribution
):
    """Stoprule if coverage regresses significantly."""
    regression = old_coverage - new_coverage
    sampled_threshold = threshold_dist.sample_thompson() * 0.1  # 10% scale

    if regression > sampled_threshold:
        emit_receipt("anomaly", {
            "metric": "completeness_regression",
            "baseline": old_coverage,
            "delta": -regression,
            "classification": "degradation",
            "action": "escalate"
        })
        raise StopRule(f"Completeness regression: {regression} > {sampled_threshold}")
