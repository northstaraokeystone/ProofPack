"""Gate decision logic.

Three-tier gate decision: GREEN, YELLOW, RED.
"""
import time
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from ledger.core import emit_receipt
from anchor import dual_hash
from constants import GATE_GREEN_THRESHOLD, GATE_YELLOW_THRESHOLD
from config.features import FEATURE_GATE_ENABLED, FEATURE_GATE_YELLOW_ONLY


class GateDecision(Enum):
    """Gate decision outcomes."""
    GREEN = "GREEN"   # Execute immediately
    YELLOW = "YELLOW" # Execute + spawn monitoring watchers
    RED = "RED"       # Block execution, require human approval


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


def gate_decision(
    confidence_score: float,
    thresholds: GateThresholds | None = None,
    action_id: str = "",
    context_drift: float = 0.0,
    reasoning_entropy: float = 0.0,
    tenant_id: str = "default"
) -> tuple[GateResult, dict]:
    """Make gate decision based on confidence score.

    - GREEN (>0.9): Execute immediately, emit execution_receipt
    - YELLOW (0.7-0.9): Execute + spawn monitoring watchers via loop/
    - RED (<0.7): Block execution, emit block_receipt, require human approval

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
        decision = GateDecision.GREEN
        requires_approval = False
        blocked_at = None
    elif FEATURE_GATE_YELLOW_ONLY and decision == GateDecision.RED:
        # YELLOW-only mode - treat RED as YELLOW
        decision = GateDecision.YELLOW
        requires_approval = False
        blocked_at = None

    result = GateResult(
        decision=decision,
        confidence_score=confidence_score,
        context_drift=context_drift,
        reasoning_entropy=reasoning_entropy,
        action_id=action_id,
        requires_approval=requires_approval,
        blocked_at=blocked_at
    )

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Emit appropriate receipt based on decision
    if decision == GateDecision.RED:
        receipt = emit_receipt("block", {
            "action_id": action_id,
            "reason": f"confidence_score {confidence_score:.3f} < {thresholds.yellow}",
            "requires_approval": True,
            "blocked_at": blocked_at,
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
            "payload_hash": dual_hash(f"{action_id}:{confidence_score}:{decision.value}")
        }, tenant_id=tenant_id)

    # Blockchain anchor on every decision
    anchor_receipt = emit_receipt("anchor", {
        "source": "gate_decision",
        "decision": decision.value,
        "action_id": action_id,
        "payload_hash": dual_hash(f"gate:{action_id}:{decision.value}")
    }, tenant_id=tenant_id)

    return result, receipt


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
