"""Self-improving meta-layer with quantum-inspired computation.

Everything is a wave, not an event. This module implements:
- Probability distributions instead of scalars
- Thompson sampling for exploration-exploitation
- SUPERPOSITION states until measurement
- Exponential decay instead of hard cutoffs
- Adaptive intervals based on entropy

"The cap is not a number—it's the entropy budget."
"""

from proofpack.loop.src.completeness import (
    CompletenessState,
    Level,
    LevelCoverage,
    asymptotic_limit,
    attempt_self_verification,
    compute_completeness_entropy,
    compute_self_verification_probability,
    godel_layer,
    stoprule_completeness_regression,
    update_completeness,
)
from proofpack.loop.src.convergence import (
    ConvergenceState,
    compute_convergence_proof,
    detect_loops,
    hash_question,
    stoprule_infinite_loop,
    track_question,
)
from proofpack.loop.src.cycle import (
    CycleState,
    compute_next_interval,
    compute_stream_entropy,
    run_cycle,
    stoprule_cycle_timeout,
)
from proofpack.loop.src.effectiveness import (
    EffectivenessMetrics,
    EffectivenessWeights,
    WeightDistribution,
    assess_dormancy,
    compute_activity_probability,
    compute_fitness,
    rank_by_fitness,
    stoprule_effectiveness_collapse,
    update_weights_from_outcome,
)
from proofpack.loop.src.gate import (
    ApprovalDecision,
    ApprovalGate,
    batch_evaluate,
    check_escalation_needed,
    compute_auto_decline_probability,
    evaluate_approval,
    should_require_approval,
    stoprule_approval_backlog,
)
from proofpack.loop.src.genesis import (
    HelperBlueprint,
    HelperState,
    create_blueprint,
    run_backtest,
    select_blueprints_for_approval,
    should_explore_helper,
    stoprule_genesis_failure,
)
from proofpack.loop.src.harvest import (
    PatternEvidence,
    compute_signal_to_noise,
    harvest_patterns,
    select_patterns_for_genesis,
    stoprule_pattern_explosion,
)
from proofpack.loop.src.quantum import (
    FitnessDistribution,
    StateType,
    Superposition,
    collapse_state,
    emit_quantum_receipt,
    entropy_delta,
    exponential_decay,
    sample_from_distributions,
    shannon_entropy,
    stoprule_entropy_violation,
)
from proofpack.loop.src.sense import (
    ObservationWindow,
    observe_stream,
    sense_anomaly_evidence,
    sense_gap_signals,
    stoprule_observation_overflow,
)
from proofpack.loop.src.spawn import (
    SpawnResult,
    calculate_helpers_to_spawn,
    should_spawn,
    spawn_helpers,
    stoprule_spawn_overflow,
)
from proofpack.loop.src.wounds import (
    WoundEvent,
    WoundTracker,
    get_wound_summary,
    stoprule_excessive_wounds,
    track_confidence,
)

__all__ = [
    # quantum.py - The Foundation
    "FitnessDistribution",
    "Superposition",
    "StateType",
    "shannon_entropy",
    "entropy_delta",
    "collapse_state",
    "exponential_decay",
    "sample_from_distributions",
    "emit_quantum_receipt",
    "stoprule_entropy_violation",

    # cycle.py - The Adaptive Heartbeat
    "CycleState",
    "compute_stream_entropy",
    "compute_next_interval",
    "run_cycle",
    "stoprule_cycle_timeout",

    # sense.py - Observing the Stream
    "ObservationWindow",
    "observe_stream",
    "sense_anomaly_evidence",
    "sense_gap_signals",
    "stoprule_observation_overflow",

    # harvest.py - Finding Signal in Noise
    "PatternEvidence",
    "harvest_patterns",
    "compute_signal_to_noise",
    "select_patterns_for_genesis",
    "stoprule_pattern_explosion",

    # genesis.py - Birth from Uncertainty
    "HelperBlueprint",
    "HelperState",
    "create_blueprint",
    "run_backtest",
    "should_explore_helper",
    "select_blueprints_for_approval",
    "stoprule_genesis_failure",

    # effectiveness.py - Fitness as a Wave
    "WeightDistribution",
    "EffectivenessWeights",
    "EffectivenessMetrics",
    "compute_fitness",
    "compute_activity_probability",
    "update_weights_from_outcome",
    "assess_dormancy",
    "rank_by_fitness",
    "stoprule_effectiveness_collapse",

    # gate.py - Measurement Collapses Possibility
    "ApprovalGate",
    "ApprovalDecision",
    "should_require_approval",
    "compute_auto_decline_probability",
    "evaluate_approval",
    "check_escalation_needed",
    "batch_evaluate",
    "stoprule_approval_backlog",

    # completeness.py - Asymptotic Truth
    "Level",
    "LevelCoverage",
    "CompletenessState",
    "godel_layer",
    "asymptotic_limit",
    "compute_self_verification_probability",
    "update_completeness",
    "attempt_self_verification",
    "compute_completeness_entropy",
    "stoprule_completeness_regression",

    # wounds.py - Tracking Confidence Drops
    "WoundEvent",
    "WoundTracker",
    "track_confidence",
    "get_wound_summary",
    "stoprule_excessive_wounds",

    # spawn.py - Auto-Spawning Helpers
    "SpawnResult",
    "calculate_helpers_to_spawn",
    "should_spawn",
    "spawn_helpers",
    "stoprule_spawn_overflow",

    # convergence.py - Loop Detection
    "ConvergenceState",
    "hash_question",
    "track_question",
    "detect_loops",
    "compute_convergence_proof",
    "stoprule_infinite_loop",
]
