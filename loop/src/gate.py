"""Approval gate - measurement collapses the wave function.

Research anchor (QED v7:346-347):
"Selection samples from fitness distributions (mean, variance).
High-variance patterns get explored."

Research anchor (QED v7:604-605):
"HITL unavailable 7 days → auto escalate. After 14 days → proposals auto-decline."

BASELINE ASSUMPTIONS BROKEN:
- NOT if risk >= 0.2: require_approval
- NOT hard 14-day auto-decline cliff
- Before human approval, helpers exist in SUPERPOSITION
- Approval SAMPLES from risk_distribution and threshold_distribution
- Auto-decline is a probability that DECAYS, not a cliff

Measurement collapses possibility. That's not comparison to threshold—
it's sampling from distributions.
"""
import time
from dataclasses import dataclass, field
from typing import Literal

from ledger.core import emit_receipt, StopRule
from loop.src.quantum import (
    FitnessDistribution,
    collapse_state,
    sample_from_distributions,
    exponential_decay
)
from loop.src.genesis import HelperBlueprint


ApprovalDecision = Literal["approve", "reject", "defer", "auto_decline"]


@dataclass
class ApprovalGate:
    """Approval gate with probabilistic thresholds."""
    # Risk threshold is a distribution, not a constant
    risk_threshold_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=2, beta=8)  # Biased toward caution
    )

    # Auto-decline decay rate (days)
    decline_decay_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=3, beta=7)
    )

    # Escalation timing (distributions)
    escalate_after_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=5, beta=5)
    )


def should_require_approval(
    blueprint: HelperBlueprint,
    gate: ApprovalGate
) -> tuple[bool, float, float]:
    """Decide if approval is required using Thompson sampling.

    Sometimes a 0.19 risk gets flagged. Sometimes a 0.21 auto-approves.
    That's exploration at the boundaries.
    """
    sampled_risk, sampled_threshold = sample_from_distributions(
        blueprint.risk_distribution,
        gate.risk_threshold_dist
    )

    requires_approval = sampled_risk > sampled_threshold

    return requires_approval, sampled_risk, sampled_threshold


def compute_auto_decline_probability(
    days_pending: float,
    gate: ApprovalGate
) -> float:
    """P(auto_decline) grows with time - exponential approach to 1.0.

    NOT a cliff at day 14. Probability increases smoothly.
    Day 7 might have 30% chance. Day 14 might have 70%.
    Day 21 might have 90%. Never exactly 100%.
    """
    # Sample decay rate
    decay_rate = gate.decline_decay_dist.sample_thompson()

    # Scale appropriately (per day)
    scaled_rate = decay_rate * 0.1

    # P(decline) = 1 - e^(-λt) - inverse of survival
    p_survive = exponential_decay(days_pending, scaled_rate)
    p_decline = 1 - p_survive

    return p_decline


def evaluate_approval(
    blueprint: HelperBlueprint,
    gate: ApprovalGate,
    human_decision: ApprovalDecision | None = None,
    tenant_id: str = "default"
) -> tuple[HelperBlueprint, dict]:
    """Evaluate blueprint for approval.

    If human_decision provided, collapse superposition.
    Otherwise, sample from distributions.
    """
    ts_now = time.time()
    days_pending = (ts_now - blueprint.created_ts) / (24 * 3600)

    # Check auto-decline probability
    p_auto_decline = compute_auto_decline_probability(days_pending, gate)

    # Should we require approval?
    requires_approval, sampled_risk, sampled_threshold = should_require_approval(
        blueprint, gate
    )

    if human_decision is not None:
        # MEASUREMENT - collapse the wave function
        new_state = collapse_state(
            blueprint.state,
            "approve" if human_decision == "approve" else "reject",
            f"human_decision_{human_decision}",
            ts_now
        )
        decision = human_decision
        collapse_reason = f"human_measurement_{human_decision}"

    elif p_auto_decline > 0.9:
        # High probability of auto-decline
        # But still sample! Sometimes it survives.
        import random
        if random.random() < p_auto_decline:
            new_state = collapse_state(
                blueprint.state,
                "reject",
                "auto_decline_timeout",
                ts_now
            )
            decision = "auto_decline"
            collapse_reason = "probabilistic_timeout"
        else:
            # Survived the sampling!
            new_state = blueprint.state  # Still in superposition
            decision = "defer"
            collapse_reason = "survived_decline_sampling"

    elif not requires_approval and sampled_risk < sampled_threshold * 0.5:
        # Low enough risk to auto-approve (sampled)
        new_state = collapse_state(
            blueprint.state,
            "approve",
            "auto_approve_low_risk",
            ts_now
        )
        decision = "approve"
        collapse_reason = "risk_below_threshold"

    else:
        # Defer - stay in superposition
        new_state = blueprint.state
        decision = "defer"
        collapse_reason = "awaiting_measurement"

    updated_blueprint = HelperBlueprint(
        id=blueprint.id,
        pattern_id=blueprint.pattern_id,
        state=new_state,
        risk_distribution=blueprint.risk_distribution,
        backtest_results=blueprint.backtest_results,
        backtest_dist=blueprint.backtest_dist,
        created_ts=blueprint.created_ts,
        last_activity_ts=ts_now if decision != "defer" else blueprint.last_activity_ts
    )

    receipt = emit_receipt("approval", {
        "blueprint_id": blueprint.id,
        "decision": decision,
        "state_before": blueprint.state.state,
        "state_after": new_state.state,
        "days_pending": days_pending,
        "p_auto_decline": p_auto_decline,
        "sampled_risk": sampled_risk,
        "sampled_threshold": sampled_threshold,
        "risk_uncertainty": blueprint.risk_uncertainty,
        "collapse_reason": collapse_reason,
        "superposition": {
            "p_active": new_state.probability_active(),
            "amplitude_active": new_state.amplitude_active,
            "amplitude_dormant": new_state.amplitude_dormant
        }
    }, tenant_id=tenant_id)

    return updated_blueprint, receipt


def check_escalation_needed(
    blueprint: HelperBlueprint,
    gate: ApprovalGate,
    tenant_id: str = "default"
) -> tuple[bool, dict]:
    """Check if escalation is needed - probabilistic, not threshold.

    HITL unavailable doesn't trigger at day 7 exactly.
    It's a probability that increases.
    """
    days_pending = (time.time() - blueprint.created_ts) / (24 * 3600)

    # Sample escalation threshold
    escalate_threshold = gate.escalate_after_dist.sample_thompson() * 14  # Scale to days

    # Probability increases with how much we've exceeded threshold
    if days_pending > escalate_threshold:
        excess_days = days_pending - escalate_threshold
        p_escalate = 1 - exponential_decay(excess_days, 0.2)
    else:
        p_escalate = 0.0

    # Sample decision
    import random
    should_escalate = random.random() < p_escalate

    receipt = emit_receipt("escalation_check", {
        "blueprint_id": blueprint.id,
        "days_pending": days_pending,
        "escalate_threshold_sampled": escalate_threshold,
        "p_escalate": p_escalate,
        "should_escalate": should_escalate,
        "state": blueprint.state.state
    }, tenant_id=tenant_id)

    return should_escalate, receipt


def batch_evaluate(
    blueprints: list[HelperBlueprint],
    gate: ApprovalGate,
    tenant_id: str = "default"
) -> tuple[list[HelperBlueprint], dict]:
    """Batch evaluate blueprints - Thompson sampling for selection.

    High-variance (uncertain) blueprints get evaluated more frequently.
    """
    evaluated = []
    decisions = []

    for bp in blueprints:
        if bp.state.state == "SUPERPOSITION":
            updated_bp, receipt = evaluate_approval(bp, gate, tenant_id=tenant_id)
            evaluated.append(updated_bp)
            decisions.append({
                "id": bp.id,
                "decision": receipt.get("decision"),
                "sampled_risk": receipt.get("sampled_risk")
            })
        else:
            evaluated.append(bp)  # Already collapsed

    summary_receipt = emit_receipt("batch_approval", {
        "total_blueprints": len(blueprints),
        "in_superposition": len([b for b in blueprints if b.state.state == "SUPERPOSITION"]),
        "decisions": decisions,
        "approved": len([d for d in decisions if d["decision"] == "approve"]),
        "rejected": len([d for d in decisions if d["decision"] in ("reject", "auto_decline")]),
        "deferred": len([d for d in decisions if d["decision"] == "defer"])
    }, tenant_id=tenant_id)

    return evaluated, summary_receipt


def stoprule_approval_backlog(
    pending_count: int,
    max_pending_dist: FitnessDistribution
):
    """Stoprule if approval backlog grows too large."""
    sampled_max = max_pending_dist.sample_thompson() * 100
    if pending_count > sampled_max:
        emit_receipt("anomaly", {
            "metric": "approval_backlog",
            "baseline": sampled_max,
            "delta": pending_count - sampled_max,
            "classification": "deviation",
            "action": "escalate"
        })
        raise StopRule(f"Approval backlog: {pending_count} > {sampled_max}")
