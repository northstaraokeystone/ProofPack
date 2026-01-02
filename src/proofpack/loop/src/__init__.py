"""Self-improving meta-layer with quantum-inspired computation.

Everything is a wave, not an event. This module implements:
- Probability distributions instead of scalars
- Thompson sampling for exploration-exploitation
- SUPERPOSITION states until measurement
- Exponential decay instead of hard cutoffs
- Adaptive intervals based on entropy

"The cap is not a number—it's the entropy budget."
"""

from proofpack.loop.src.quantum import (
    FitnessDistribution,
    Superposition,
    StateType,
    shannon_entropy,
    entropy_delta,
    collapse_state,
    exponential_decay,
    sample_from_distributions,
    emit_quantum_receipt,
    stoprule_entropy_violation,
)

from proofpack.loop.src.cycle import (
    CycleState,
    compute_stream_entropy,
    compute_next_interval,
    run_cycle,
    stoprule_cycle_timeout,
)

from proofpack.loop.src.sense import (
    ObservationWindow,
    observe_stream,
    sense_anomaly_evidence,
    sense_gap_signals,
    stoprule_observation_overflow,
)

from proofpack.loop.src.harvest import (
    PatternEvidence,
    harvest_patterns,
    compute_signal_to_noise,
    select_patterns_for_genesis,
    stoprule_pattern_explosion,
)

from proofpack.loop.src.genesis import (
    HelperBlueprint,
    HelperState,
    create_blueprint,
    run_backtest,
    should_explore_helper,
    select_blueprints_for_approval,
    stoprule_genesis_failure,
)

from proofpack.loop.src.effectiveness import (
    WeightDistribution,
    EffectivenessWeights,
    EffectivenessMetrics,
    compute_fitness,
    compute_activity_probability,
    update_weights_from_outcome,
    assess_dormancy,
    rank_by_fitness,
    stoprule_effectiveness_collapse,
)

from proofpack.loop.src.gate import (
    ApprovalGate,
    ApprovalDecision,
    should_require_approval,
    compute_auto_decline_probability,
    evaluate_approval,
    check_escalation_needed,
    batch_evaluate,
    stoprule_approval_backlog,
)

from proofpack.loop.src.completeness import (
    Level,
    LevelCoverage,
    CompletenessState,
    godel_layer,
    asymptotic_limit,
    compute_self_verification_probability,
    update_completeness,
    attempt_self_verification,
    compute_completeness_entropy,
    stoprule_completeness_regression,
)

from proofpack.loop.src.wounds import (
    WoundEvent,
    WoundTracker,
    track_confidence,
    get_wound_summary,
    stoprule_excessive_wounds,
)

from proofpack.loop.src.spawn import (
    SpawnResult,
    calculate_helpers_to_spawn,
    should_spawn,
    spawn_helpers,
    stoprule_spawn_overflow,
)

from proofpack.loop.src.convergence import (
    ConvergenceState,
    hash_question,
    track_question,
    detect_loops,
    compute_convergence_proof,
    stoprule_infinite_loop,
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
