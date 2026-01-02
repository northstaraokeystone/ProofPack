"""Effectiveness - fitness as a wave with learning weights.

Research anchor (QED v7:335-339):
"Fitness is weighted sum: 0.4 × roi + 0.3 × diversity + 0.2 × stability + 0.1 × recency.
Prevents single-metric death spiral."

Research anchor (QED v7:360-363):
"meta_fitness_receipt tracks paradigm shift outcomes...
Meta layer uses this to weight future paradigm proposals."

BASELINE ASSUMPTIONS BROKEN:
- NOT fixed weights (0.4, 0.3, 0.2, 0.1)
- NOT 30-day dormancy threshold
- Weights themselves are HYPOTHESES that learn from meta_fitness outcomes
- Dormancy is exponential decay P(active) = e^(-λt), not a cliff
"""
import time
from dataclasses import dataclass, field

from proofpack.core.receipt import StopRule, emit_receipt
from proofpack.loop.src.genesis import HelperBlueprint
from proofpack.loop.src.quantum import FitnessDistribution, exponential_decay


@dataclass
class WeightDistribution:
    """A weight that learns from outcomes."""
    name: str
    distribution: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=2, beta=2)
    )

    def sample(self) -> float:
        """Sample current weight from distribution."""
        return self.distribution.sample_thompson()

    def update(self, predicted_well: bool) -> "WeightDistribution":
        """Update weight based on whether this metric predicted outcomes."""
        new_dist = self.distribution.update(
            self.distribution.mean,
            success=predicted_well
        )
        return WeightDistribution(name=self.name, distribution=new_dist)


@dataclass
class EffectivenessWeights:
    """Adaptive weights that learn which metrics matter."""
    roi_weight: WeightDistribution = field(
        default_factory=lambda: WeightDistribution("roi", FitnessDistribution(alpha=4, beta=6))
    )
    diversity_weight: WeightDistribution = field(
        default_factory=lambda: WeightDistribution("diversity", FitnessDistribution(alpha=3, beta=7))
    )
    stability_weight: WeightDistribution = field(
        default_factory=lambda: WeightDistribution("stability", FitnessDistribution(alpha=2, beta=8))
    )
    recency_weight: WeightDistribution = field(
        default_factory=lambda: WeightDistribution("recency", FitnessDistribution(alpha=1, beta=9))
    )

    # Decay rate for dormancy (learns from data)
    decay_rate_dist: FitnessDistribution = field(
        default_factory=lambda: FitnessDistribution(alpha=2, beta=8)
    )

    def sample_weights(self) -> dict[str, float]:
        """Sample current weights from distributions."""
        raw = {
            "roi": self.roi_weight.sample(),
            "diversity": self.diversity_weight.sample(),
            "stability": self.stability_weight.sample(),
            "recency": self.recency_weight.sample()
        }
        # Normalize to sum to 1
        total = sum(raw.values())
        if total > 0:
            return {k: v / total for k, v in raw.items()}
        return {"roi": 0.25, "diversity": 0.25, "stability": 0.25, "recency": 0.25}


@dataclass
class EffectivenessMetrics:
    """Metrics for evaluating effectiveness - all distributions."""
    roi_dist: FitnessDistribution = field(default_factory=FitnessDistribution)
    diversity_dist: FitnessDistribution = field(default_factory=FitnessDistribution)
    stability_dist: FitnessDistribution = field(default_factory=FitnessDistribution)
    recency_dist: FitnessDistribution = field(default_factory=FitnessDistribution)


def compute_fitness(
    blueprint: HelperBlueprint,
    metrics: EffectivenessMetrics,
    weights: EffectivenessWeights,
    tenant_id: str = "default"
) -> tuple[float, dict]:
    """Compute fitness as weighted sum of sampled distributions.

    Fitness is a WAVE - we sample from it, not read a scalar.
    """
    # Sample weights
    sampled_weights = weights.sample_weights()

    # Sample metrics
    roi_sample = metrics.roi_dist.sample_thompson()
    diversity_sample = metrics.diversity_dist.sample_thompson()
    stability_sample = metrics.stability_dist.sample_thompson()
    recency_sample = metrics.recency_dist.sample_thompson()

    # Compute weighted sum
    fitness = (
        sampled_weights["roi"] * roi_sample +
        sampled_weights["diversity"] * diversity_sample +
        sampled_weights["stability"] * stability_sample +
        sampled_weights["recency"] * recency_sample
    )

    receipt = emit_receipt("effectiveness", {
        "blueprint_id": blueprint.id,
        "fitness": fitness,
        "sampled_weights": sampled_weights,
        "sampled_metrics": {
            "roi": roi_sample,
            "diversity": diversity_sample,
            "stability": stability_sample,
            "recency": recency_sample
        },
        "weight_confidences": {
            "roi": weights.roi_weight.distribution.confidence,
            "diversity": weights.diversity_weight.distribution.confidence,
            "stability": weights.stability_weight.distribution.confidence,
            "recency": weights.recency_weight.distribution.confidence
        }
    }, tenant_id=tenant_id)

    return fitness, receipt


def compute_activity_probability(
    blueprint: HelperBlueprint,
    weights: EffectivenessWeights,
    current_time: float | None = None
) -> float:
    """P(active) = e^(-λt) - exponential decay, not a hard cutoff.

    days = 29 has a survival chance. No cliff at day 30.
    """
    if current_time is None:
        current_time = time.time()

    time_since_activity = current_time - blueprint.last_activity_ts
    days_inactive = time_since_activity / (24 * 3600)

    # Sample decay rate from distribution
    decay_rate = weights.decay_rate_dist.sample_thompson()

    # Scale decay rate appropriately (per day)
    scaled_rate = decay_rate * 0.1  # ~10% decay per day at mean

    return exponential_decay(days_inactive, scaled_rate)


def update_weights_from_outcome(
    weights: EffectivenessWeights,
    prediction: dict[str, float],
    actual_success: bool,
    tenant_id: str = "default"
) -> tuple[EffectivenessWeights, dict]:
    """Update weights based on whether metrics predicted outcome correctly.

    If "roi" consistently predicts survival, its weight increases.
    If "recency" is noise, its weight decays.
    This is meta-learning.
    """
    # Did each metric predict correctly?
    # High metric value + success = correct prediction
    # High metric value + failure = incorrect prediction
    threshold = 0.5

    roi_predicted_well = (prediction["roi"] > threshold) == actual_success
    diversity_predicted_well = (prediction["diversity"] > threshold) == actual_success
    stability_predicted_well = (prediction["stability"] > threshold) == actual_success
    recency_predicted_well = (prediction["recency"] > threshold) == actual_success

    new_weights = EffectivenessWeights(
        roi_weight=weights.roi_weight.update(roi_predicted_well),
        diversity_weight=weights.diversity_weight.update(diversity_predicted_well),
        stability_weight=weights.stability_weight.update(stability_predicted_well),
        recency_weight=weights.recency_weight.update(recency_predicted_well),
        decay_rate_dist=weights.decay_rate_dist
    )

    receipt = emit_receipt("meta_fitness", {
        "prediction": prediction,
        "actual_success": actual_success,
        "metric_predictions": {
            "roi": roi_predicted_well,
            "diversity": diversity_predicted_well,
            "stability": stability_predicted_well,
            "recency": recency_predicted_well
        },
        "updated_weight_means": {
            "roi": new_weights.roi_weight.distribution.mean,
            "diversity": new_weights.diversity_weight.distribution.mean,
            "stability": new_weights.stability_weight.distribution.mean,
            "recency": new_weights.recency_weight.distribution.mean
        }
    }, tenant_id=tenant_id)

    return new_weights, receipt


def assess_dormancy(
    blueprint: HelperBlueprint,
    weights: EffectivenessWeights,
    tenant_id: str = "default"
) -> tuple[float, dict]:
    """Assess dormancy as probability, not binary state.

    No hard cutoff. Continuous probability.
    """
    p_active = compute_activity_probability(blueprint, weights)
    p_dormant = 1 - p_active

    time_since_activity = time.time() - blueprint.last_activity_ts
    days_inactive = time_since_activity / (24 * 3600)

    receipt = emit_receipt("dormancy_assessment", {
        "blueprint_id": blueprint.id,
        "days_inactive": days_inactive,
        "p_active": p_active,
        "p_dormant": p_dormant,
        "decay_rate_mean": weights.decay_rate_dist.mean,
        "decay_rate_variance": weights.decay_rate_dist.variance,
        "state_classification": "active" if p_active > 0.5 else "likely_dormant"
    }, tenant_id=tenant_id)

    return p_dormant, receipt


def rank_by_fitness(
    blueprints: list[HelperBlueprint],
    metrics_map: dict[str, EffectivenessMetrics],
    weights: EffectivenessWeights,
    tenant_id: str = "default"
) -> tuple[list[tuple[HelperBlueprint, float]], dict]:
    """Rank blueprints by sampled fitness.

    Thompson sampling means ranking may vary - that's exploration!
    """
    ranked = []
    for bp in blueprints:
        metrics = metrics_map.get(bp.id, EffectivenessMetrics())
        fitness, _ = compute_fitness(bp, metrics, weights, tenant_id)
        ranked.append((bp, fitness))

    # Sort by fitness (descending)
    ranked.sort(key=lambda x: x[1], reverse=True)

    receipt = emit_receipt("fitness_ranking", {
        "blueprints_ranked": len(ranked),
        "top_5": [
            {
                "id": bp.id,
                "fitness": fitness,
                "pattern": bp.pattern_id
            }
            for bp, fitness in ranked[:5]
        ],
        "weights_used": weights.sample_weights()
    }, tenant_id=tenant_id)

    return ranked, receipt


def stoprule_effectiveness_collapse(
    fitness: float,
    min_fitness_dist: FitnessDistribution
):
    """Stoprule if effectiveness collapses below threshold."""
    sampled_min = min_fitness_dist.sample_thompson()
    if fitness < sampled_min:
        emit_receipt("anomaly", {
            "metric": "effectiveness",
            "baseline": sampled_min,
            "delta": fitness - sampled_min,
            "classification": "degradation",
            "action": "alert"
        })
        raise StopRule(f"Effectiveness collapse: {fitness} < {sampled_min}")
