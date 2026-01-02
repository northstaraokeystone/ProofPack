"""Gate decision logic.

Three-tier gate decision: GREEN, YELLOW, RED.
Traffic lights that birth agents when uncertain.
"""
import time
from dataclasses import dataclass, field
from enum import Enum

from core.receipt import emit_receipt
from core.receipt import dual_hash
from constants import GATE_GREEN_THRESHOLD, GATE_YELLOW_THRESHOLD
from config.features import (
    FEATURE_GATE_ENABLED,
    FEATURE_GATE_YELLOW_ONLY,
    FEATURE_AGENT_SPAWNING_ENABLED,
)


class GateDecision(Enum):
    """Gate decision outcomes."""
    GREEN = "GREEN"   # Execute immediately, spawn success_learner
    YELLOW = "YELLOW" # Execute + spawn monitoring watchers
    RED = "RED"       # Block execution, spawn helpers


@dataclass
class GateThresholds:
    """Configurable gate thresholds."""
    green: float = GATE_GREEN_THRESHOLD
    yellow: float = GATE_YELLOW_THRESHOLD


@dataclass
class GateResult:
    """Result of gate evaluation."""
    decision: GateDecision
    confidence_score: float
    context_drift: float
    reasoning_entropy: float
    action_id: str
    requires_approval: bool
    blocked_at: float | None
    spawned_agents: list[str] = field(default_factory=list)


def gate_decision(
    confidence_score: float,
    thresholds: GateThresholds | None = None,
    action_id: str = "",
    context_drift: float = 0.0,
    reasoning_entropy: float = 0.0,
    wound_count: int = 0,
    variance: float = 0.0,
    action_duration_seconds: int = 0,
    parent_agent_id: str | None = None,
    tenant_id: str = "default"
) -> tuple[GateResult, dict]:
    """Make gate decision and spawn appropriate agents.

    Decision rules:
    - GREEN (>0.9): Execute, spawn 1 success_learner
    - YELLOW (0.7-0.9): Execute + watch, spawn 3 watchers
    - RED (<0.7): Block, spawn (wound_count // 2) + 1 helpers

    Returns (GateResult, receipt)
    """
    t0 = time.perf_counter()

    if thresholds is None:
        thresholds = GateThresholds()

    # Determine decision
    if confidence_score >= thresholds.green:
        decision = GateDecision.GREEN
        requires_approval = False
        blocked_at = None
    elif confidence_score >= thresholds.yellow:
        decision = GateDecision.YELLOW
        requires_approval = False
        blocked_at = None
    else:
        decision = GateDecision.RED
        requires_approval = True
        blocked_at = time.time()

    # Check feature flags
    if not FEATURE_GATE_ENABLED:
        # Shadow mode - log but don't block
        _original_decision = decision  # noqa: F841 - kept for debugging
        decision = GateDecision.GREEN
        requires_approval = False
        blocked_at = None
    elif FEATURE_GATE_YELLOW_ONLY and decision == GateDecision.RED:
        # YELLOW-only mode - treat RED as YELLOW
        decision = GateDecision.YELLOW
        requires_approval = False
        blocked_at = None

    # Spawn agents based on decision
    spawned_agents = []
    if FEATURE_AGENT_SPAWNING_ENABLED:
        spawned_agents = _spawn_for_decision(
            decision=decision,
            confidence_score=confidence_score,
            wound_count=wound_count,
            variance=variance,
            action_duration_seconds=action_duration_seconds,
            parent_agent_id=parent_agent_id,
            tenant_id=tenant_id,
        )

    result = GateResult(
        decision=decision,
        confidence_score=confidence_score,
        context_drift=context_drift,
        reasoning_entropy=reasoning_entropy,
        action_id=action_id,
        requires_approval=requires_approval,
        blocked_at=blocked_at,
        spawned_agents=spawned_agents,
    )

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Emit appropriate receipt based on decision
    if decision == GateDecision.RED:
        receipt = emit_receipt("block", {
            "action_id": action_id,
            "reason": f"confidence_score {confidence_score:.3f} < {thresholds.yellow}",
            "requires_approval": True,
            "blocked_at": blocked_at,
            "spawned_agents": spawned_agents,
            "payload_hash": dual_hash(f"{action_id}:{confidence_score}")
        }, tenant_id=tenant_id)
    else:
        receipt = emit_receipt("gate_decision", {
            "action_id": action_id,
            "confidence_score": confidence_score,
            "decision": decision.value,
            "context_drift": context_drift,
            "reasoning_entropy": reasoning_entropy,
            "decision_ms": elapsed_ms,
            "spawned_agents": spawned_agents,
            "payload_hash": dual_hash(f"{action_id}:{confidence_score}:{decision.value}")
        }, tenant_id=tenant_id)

    # Blockchain anchor on every decision
    emit_receipt("anchor", {
        "source": "gate_decision",
        "decision": decision.value,
        "action_id": action_id,
        "payload_hash": dual_hash(f"gate:{action_id}:{decision.value}")
    }, tenant_id=tenant_id)

    return result, receipt


def _spawn_for_decision(
    decision: GateDecision,
    confidence_score: float,
    wound_count: int,
    variance: float,
    action_duration_seconds: int,
    parent_agent_id: str | None,
    tenant_id: str,
) -> list[str]:
    """Spawn agents based on gate decision.

    Returns list of spawned agent IDs.
    """
    try:
        from spawner.birth import spawn_for_gate
        from spawner.patterns import find_matching_pattern, apply_pattern

        # Check for matching pattern first (for RED gate)
        if decision == GateDecision.RED:
            pattern, _ = find_matching_pattern(
                "RED", confidence_score, tenant_id=tenant_id
            )
            if pattern:
                # Apply pattern instead of spawning
                apply_pattern(pattern, tenant_id)
                return []  # No agents spawned - pattern applied

        result, _ = spawn_for_gate(
            gate_color=decision.value,
            confidence_score=confidence_score,
            wound_count=wound_count,
            variance=variance,
            action_duration_seconds=action_duration_seconds,
            parent_agent_id=parent_agent_id,
            tenant_id=tenant_id,
        )

        return result.agent_ids if result else []

    except ImportError:
        # Spawner module not available
        return []


def get_spawn_preview(
    confidence_score: float,
    wound_count: int = 0,
    variance: float = 0.0,
) -> dict:
    """Preview what agents would be spawned for a given confidence.

    For use by CLI: proof gate check <action_id>
    """
    try:
        from spawner.birth import simulate_spawn

        if confidence_score >= GATE_GREEN_THRESHOLD:
            gate_color = "GREEN"
        elif confidence_score >= GATE_YELLOW_THRESHOLD:
            gate_color = "YELLOW"
        else:
            gate_color = "RED"

        return simulate_spawn(gate_color, confidence_score, wound_count, variance)

    except ImportError:
        return {"error": "spawner module not available"}


def stoprule_gate_latency(elapsed_ms: float, budget_ms: float = 50.0):
    """Stoprule if gate decision exceeds latency budget."""
    if elapsed_ms > budget_ms:
        emit_receipt("anomaly", {
            "metric": "gate_latency",
            "baseline": budget_ms,
            "delta": elapsed_ms - budget_ms,
            "classification": "degradation",
            "action": "alert"
        })
