"""Helper genesis - risk as uncertainty.

Research anchor (QED v7:365-367):
"Risk score 0.0-1.0 with confidence interval for every decision."

BASELINE ASSUMPTION BROKEN:
- NOT risk_score = 1.0 - (success_rate × confidence) as a scalar
- 2 backtests at 100% success = UNKNOWN risk, not low risk
- 50 backtests at 70% success = KNOWN risk

Risk isn't a number. It's a distribution. High variance means "we don't know"
and Thompson sampling EXPLORES things we don't know.
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from proofpack.core.receipt import StopRule, emit_receipt
from proofpack.loop.src.harvest import PatternEvidence
from proofpack.loop.src.quantum import FitnessDistribution, Superposition, sample_from_distributions

HelperState = Literal["SUPERPOSITION", "ACTIVE", "DORMANT", "TESTING"]


@dataclass
class HelperBlueprint:
    """A helper blueprint with risk as a distribution, not a scalar."""
    id: str
    pattern_id: str
    state: Superposition = field(default_factory=Superposition)

    # Risk distribution - mean + variance + observations
    risk_distribution: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=1, beta=1)
    )

    # Backtest evidence
    backtest_results: list[dict] = field(default_factory=list)
    backtest_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=1, beta=1)
    )

    # Metadata
    created_ts: float = field(default_factory=time.time)
    last_activity_ts: float = field(default_factory=time.time)

    def sample_risk(self) -> float:
        """Sample risk from distribution - Thompson sampling for exploration."""
        return self.risk_distribution.sample_thompson()

    @property
    def risk_uncertainty(self) -> float:
        """How uncertain are we about the risk? High = explore more."""
        return self.risk_distribution.variance

    def update_with_backtest(self, success: bool, details: dict) -> "HelperBlueprint":
        """Update risk distribution with backtest result."""
        # Success = lower risk, failure = higher risk
        # But the DISTRIBUTION is updated, not just a scalar
        new_risk = self.risk_distribution.update(
            1.0 if not success else 0.0,
            success=success
        )
        new_backtest = self.backtest_dist.update(1.0 if success else 0.0, success=success)

        new_results = self.backtest_results + [{
            "ts": time.time(),
            "success": success,
            "details": details
        }]

        return HelperBlueprint(
            id=self.id,
            pattern_id=self.pattern_id,
            state=self.state,
            risk_distribution=new_risk,
            backtest_results=new_results,
            backtest_dist=new_backtest,
            created_ts=self.created_ts,
            last_activity_ts=time.time()
        )


def create_blueprint(
    pattern: PatternEvidence,
    tenant_id: str = "default"
) -> tuple[HelperBlueprint, dict]:
    """Create a new helper blueprint from a pattern.

    Blueprint starts in SUPERPOSITION - not approved, not rejected.
    """
    blueprint_id = f"helper_{uuid.uuid4().hex[:8]}"

    # Initial risk is based on pattern confidence, but INVERTED
    # Low confidence pattern = HIGH risk uncertainty (need to explore)
    initial_alpha = 1.0 + pattern.posterior_confidence
    initial_beta = 1.0 + (1 - pattern.posterior_confidence)

    blueprint = HelperBlueprint(
        id=blueprint_id,
        pattern_id=pattern.pattern_id,
        state=Superposition(),  # Born in superposition
        risk_distribution=FitnessDistribution(
            alpha=initial_alpha,
            beta=initial_beta
        )
    )

    receipt = emit_receipt("helper_blueprint", {
        "blueprint_id": blueprint_id,
        "pattern_id": pattern.pattern_id,
        "initial_state": "SUPERPOSITION",
        "risk_distribution": {
            "mean": blueprint.risk_distribution.mean,
            "variance": blueprint.risk_distribution.variance,
            "confidence": blueprint.risk_distribution.confidence,
            "alpha": blueprint.risk_distribution.alpha,
            "beta": blueprint.risk_distribution.beta
        },
        "pattern_actionability": pattern.actionability_score,
        "pattern_confidence": pattern.posterior_confidence
    }, tenant_id=tenant_id)

    return blueprint, receipt


def run_backtest(
    blueprint: HelperBlueprint,
    historical_data: list[dict],
    tenant_id: str = "default"
) -> tuple[HelperBlueprint, dict]:
    """Run backtest on blueprint, update risk distribution.

    Each backtest updates our belief about risk.
    2 backtests at 100% = high uncertainty (Beta(3,1) has wide variance)
    50 backtests at 70% = lower uncertainty (Beta(36,16) is tighter)
    """
    t0 = time.perf_counter()

    # Simulate backtest (placeholder - real implementation would apply helper logic)
    successes = 0
    failures = 0
    details = []

    for data_point in historical_data:
        # Placeholder logic - would actually run helper
        result = _simulate_helper_execution(blueprint, data_point)
        if result["success"]:
            successes += 1
        else:
            failures += 1
        details.append(result)

    # Update blueprint with results
    updated_blueprint = blueprint
    for detail in details:
        updated_blueprint = updated_blueprint.update_with_backtest(
            detail["success"],
            detail
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000

    receipt = emit_receipt("backtest", {
        "blueprint_id": blueprint.id,
        "data_points": len(historical_data),
        "successes": successes,
        "failures": failures,
        "success_rate": successes / max(len(historical_data), 1),
        "risk_distribution": {
            "mean": updated_blueprint.risk_distribution.mean,
            "variance": updated_blueprint.risk_distribution.variance,
            "confidence": updated_blueprint.risk_distribution.confidence
        },
        "backtest_duration_ms": elapsed_ms,
        "uncertainty_reduced": blueprint.risk_uncertainty - updated_blueprint.risk_uncertainty
    }, tenant_id=tenant_id)

    return updated_blueprint, receipt


def _simulate_helper_execution(blueprint: HelperBlueprint, data: dict) -> dict:
    """Placeholder simulation - would be real helper execution."""
    import random
    # Success probability based on pattern actionability
    p_success = 0.7  # Placeholder
    success = random.random() < p_success
    return {
        "success": success,
        "data_id": data.get("id", "unknown"),
        "simulated": True
    }


def should_explore_helper(
    blueprint: HelperBlueprint,
    threshold_dist: FitnessDistribution
) -> tuple[bool, float, float]:
    """Decide whether to explore a helper using Thompson sampling.

    Returns (should_explore, sampled_risk, sampled_threshold)

    Sometimes a 0.19 risk gets flagged. Sometimes a 0.21 auto-approves.
    That's not a bug—that's exploration at the boundaries.
    """
    sampled_risk, sampled_threshold = sample_from_distributions(
        blueprint.risk_distribution,
        threshold_dist
    )

    # High variance in risk = high uncertainty = explore!
    # Thompson sampling naturally explores uncertain options
    should_explore = sampled_risk < sampled_threshold

    return should_explore, sampled_risk, sampled_threshold


def select_blueprints_for_approval(
    blueprints: list[HelperBlueprint],
    budget_dist: FitnessDistribution,
    tenant_id: str = "default"
) -> tuple[list[HelperBlueprint], dict]:
    """Select blueprints for approval using Thompson sampling.

    High-variance (uncertain) blueprints get explored.
    Low-variance (known-good) blueprints get exploited.
    """
    # Sample risk for each blueprint
    sampled = []
    for bp in blueprints:
        if bp.state.state == "SUPERPOSITION":  # Only consider unresolved
            risk_sample = bp.sample_risk()
            sampled.append((bp, risk_sample))

    # Sort by sampled risk (lower = better for approval)
    sampled.sort(key=lambda x: x[1])

    # Sample budget
    budget_sample = budget_dist.sample_thompson()
    num_to_select = max(1, int(budget_sample * len(sampled)))

    selected = [bp for bp, _ in sampled[:num_to_select]]

    receipt = emit_receipt("blueprint_selection", {
        "total_blueprints": len(blueprints),
        "in_superposition": len(sampled),
        "budget_sample": budget_sample,
        "selected_count": len(selected),
        "selected": [
            {
                "id": bp.id,
                "sampled_risk": bp.sample_risk(),
                "risk_uncertainty": bp.risk_uncertainty
            }
            for bp in selected
        ]
    }, tenant_id=tenant_id)

    return selected, receipt


def stoprule_genesis_failure(blueprint: HelperBlueprint, failure_dist: FitnessDistribution):
    """Stoprule if helper genesis has too many failures."""
    failure_rate = blueprint.risk_distribution.mean
    sampled_threshold = failure_dist.sample_thompson()

    if failure_rate > sampled_threshold:
        emit_receipt("anomaly", {
            "metric": "genesis_failure_rate",
            "baseline": sampled_threshold,
            "delta": failure_rate - sampled_threshold,
            "classification": "degradation",
            "action": "halt"
        })
        raise StopRule(f"Genesis failure: {failure_rate} > {sampled_threshold}")
