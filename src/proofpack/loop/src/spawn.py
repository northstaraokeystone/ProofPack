"""Auto-spawn helper agents when stuck.

When wound count exceeds threshold, spawn helpers using formula:
helpers = (wounds // 2) + 1

If convergence proof >0.95, multiply helpers by 1.5x
"""
import math
import time
from dataclasses import dataclass

from proofpack.config.features import FEATURE_AUTO_SPAWN_ENABLED
from proofpack.core.constants import (
    SPAWN_BASE_FORMULA,
    SPAWN_CONVERGENCE_MULTIPLIER,
    SPAWN_CONVERGENCE_THRESHOLD,
    WOUND_SPAWN_THRESHOLD,
)
from proofpack.core.receipt import dual_hash, emit_receipt, merkle


@dataclass
class SpawnResult:
    """Result of helper spawn operation."""
    wound_count: int
    helpers_spawned: int
    convergence_proof: float
    convergence_bonus_applied: bool
    merkle_root: str


def calculate_helpers_to_spawn(
    wound_count: int,
    convergence_proof: float = 0.0
) -> int:
    """Calculate number of helpers to spawn.

    Formula: (wounds // 2) + 1
    If convergence proof >0.95, multiply by 1.5x
    """
    base_helpers = SPAWN_BASE_FORMULA(wound_count)

    if convergence_proof >= SPAWN_CONVERGENCE_THRESHOLD:
        # Apply convergence bonus
        helpers = int(math.ceil(base_helpers * SPAWN_CONVERGENCE_MULTIPLIER))
    else:
        helpers = base_helpers

    return helpers


def should_spawn(
    wound_count: int,
    threshold: int = WOUND_SPAWN_THRESHOLD
) -> bool:
    """Determine if we should spawn helpers based on wound count."""
    return wound_count >= threshold


def spawn_helpers(
    wound_count: int,
    convergence_proof: float = 0.0,
    spawn_threshold: int = WOUND_SPAWN_THRESHOLD,
    tenant_id: str = "default"
) -> tuple[SpawnResult | None, dict | None]:
    """Spawn helper agents if wound count exceeds threshold.

    Returns (SpawnResult, receipt) or (None, None) if no spawn needed.
    """
    if not FEATURE_AUTO_SPAWN_ENABLED:
        # Feature disabled - log shadow result
        if wound_count >= spawn_threshold:
            emit_receipt("spawn_shadow", {
                "wound_count": wound_count,
                "would_spawn": calculate_helpers_to_spawn(wound_count, convergence_proof),
                "reason": "feature_disabled"
            }, tenant_id=tenant_id)
        return None, None

    if wound_count < spawn_threshold:
        return None, None

    t0 = time.perf_counter()

    # Calculate helpers to spawn
    helpers_to_spawn = calculate_helpers_to_spawn(wound_count, convergence_proof)
    convergence_bonus = convergence_proof >= SPAWN_CONVERGENCE_THRESHOLD

    # Create helper data for Merkle root
    helper_data = [
        {"helper_id": f"helper_{i}", "wound_trigger": wound_count}
        for i in range(helpers_to_spawn)
    ]
    merkle_root = merkle(helper_data)

    # Spawn helpers using genesis
    from loop.src.genesis import create_blueprint
    from loop.src.harvest import PatternEvidence

    spawned_blueprints = []
    for i in range(helpers_to_spawn):
        # Create synthetic pattern for spawn
        pattern = PatternEvidence(
            pattern_id=f"spawn_pattern_{i}_{int(time.time())}",
            pattern_type="wound_response",
            occurrences=wound_count,
            prior_confidence=0.5,
            posterior_confidence=max(0.5, 1.0 - (wound_count * 0.05)),
            actionability_score=0.8,
            false_positive_rate=0.1
        )
        blueprint, _ = create_blueprint(pattern, tenant_id)
        spawned_blueprints.append(blueprint)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    result = SpawnResult(
        wound_count=wound_count,
        helpers_spawned=helpers_to_spawn,
        convergence_proof=convergence_proof,
        convergence_bonus_applied=convergence_bonus,
        merkle_root=merkle_root
    )

    receipt = emit_receipt("spawn", {
        "wound_count": wound_count,
        "helpers_spawned": helpers_to_spawn,
        "convergence_proof": convergence_proof,
        "convergence_bonus": convergence_bonus,
        "merkle_root": merkle_root,
        "spawn_ms": elapsed_ms,
        "payload_hash": dual_hash(f"spawn:{wound_count}:{helpers_to_spawn}")
    }, tenant_id=tenant_id)

    return result, receipt


def stoprule_spawn_overflow(
    helpers_spawned: int,
    max_helpers: int = 20
):
    """Stoprule if too many helpers are spawned."""
    if helpers_spawned > max_helpers:
        emit_receipt("anomaly", {
            "metric": "spawn_count",
            "baseline": max_helpers,
            "delta": helpers_spawned - max_helpers,
            "classification": "violation",
            "action": "halt"
        })
