"""Agent Graduation - Promote successful agents to permanent patterns.

When an agent achieves effectiveness >= 0.85 and autonomy > 0.75,
it graduates to become a permanent helper pattern.
"""

import time
import uuid
from dataclasses import dataclass

from proofpack.core.receipt import emit_receipt

from .registry import AgentState, get_agent
from .lifecycle import transition_agent


# Graduation thresholds (from constants.py - duplicated here for now)
AGENT_ESCAPE_VELOCITY = 0.85
AGENT_AUTONOMY_THRESHOLD = 0.75


@dataclass
class GraduationResult:
    """Result of graduation evaluation."""
    agent_id: str
    graduated: bool
    effectiveness: float
    autonomy_score: float
    pattern_id: str | None
    reason: str


def evaluate_graduation(
    agent_id: str,
    effectiveness: float,
    autonomy_score: float,
    tenant_id: str = "default",
) -> tuple[GraduationResult, dict]:
    """Evaluate if an agent should graduate to permanent pattern.

    Graduation criteria:
    - effectiveness >= AGENT_ESCAPE_VELOCITY (0.85)
    - autonomy_score > AGENT_AUTONOMY_THRESHOLD (0.75)

    Returns (GraduationResult, receipt)
    """
    agent = get_agent(agent_id)

    if not agent:
        result = GraduationResult(
            agent_id=agent_id,
            graduated=False,
            effectiveness=effectiveness,
            autonomy_score=autonomy_score,
            pattern_id=None,
            reason="agent_not_found",
        )
        receipt = emit_receipt("graduation_error", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "error": "agent_not_found",
        })
        return result, receipt

    if agent.state != AgentState.ACTIVE:
        result = GraduationResult(
            agent_id=agent_id,
            graduated=False,
            effectiveness=effectiveness,
            autonomy_score=autonomy_score,
            pattern_id=None,
            reason=f"invalid_state_{agent.state.value}",
        )
        receipt = emit_receipt("graduation_error", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "error": f"agent_in_state_{agent.state.value}",
        })
        return result, receipt

    # Check graduation criteria
    meets_effectiveness = effectiveness >= AGENT_ESCAPE_VELOCITY
    meets_autonomy = autonomy_score > AGENT_AUTONOMY_THRESHOLD

    if meets_effectiveness and meets_autonomy:
        # Graduate the agent
        pattern_id = str(uuid.uuid4())

        # Transition to GRADUATED state
        transition_agent(
            agent_id,
            AgentState.GRADUATED,
            reason="met_graduation_criteria",
            tenant_id=tenant_id,
        )

        result = GraduationResult(
            agent_id=agent_id,
            graduated=True,
            effectiveness=effectiveness,
            autonomy_score=autonomy_score,
            pattern_id=pattern_id,
            reason="met_criteria",
        )

        receipt = emit_receipt("graduation", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "solution_pattern_id": pattern_id,
            "effectiveness": effectiveness,
            "autonomy_score": autonomy_score,
            "promoted_to": "permanent_helper",
        })

    else:
        reasons = []
        if not meets_effectiveness:
            reasons.append(f"effectiveness_{effectiveness:.2f}_below_{AGENT_ESCAPE_VELOCITY}")
        if not meets_autonomy:
            reasons.append(f"autonomy_{autonomy_score:.2f}_below_{AGENT_AUTONOMY_THRESHOLD}")

        result = GraduationResult(
            agent_id=agent_id,
            graduated=False,
            effectiveness=effectiveness,
            autonomy_score=autonomy_score,
            pattern_id=None,
            reason="; ".join(reasons),
        )

        receipt = emit_receipt("graduation_evaluation", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "graduated": False,
            "effectiveness": effectiveness,
            "autonomy_score": autonomy_score,
            "effectiveness_threshold": AGENT_ESCAPE_VELOCITY,
            "autonomy_threshold": AGENT_AUTONOMY_THRESHOLD,
            "reason": result.reason,
        })

    return result, receipt


def promote_to_pattern(
    agent_id: str,
    solution_approach: dict,
    tenant_id: str = "default",
) -> tuple[str | None, dict]:
    """Promote a graduated agent's approach to a permanent pattern.

    This extracts the solution pattern from the agent and stores it
    in the patterns registry for reuse.

    Args:
        agent_id: ID of graduated agent
        solution_approach: Dict describing what the agent did to succeed

    Returns:
        (pattern_id, receipt) or (None, error_receipt)
    """
    agent = get_agent(agent_id)

    if not agent:
        receipt = emit_receipt("promote_error", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "error": "agent_not_found",
        })
        return None, receipt

    if agent.state != AgentState.GRADUATED:
        receipt = emit_receipt("promote_error", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "error": f"agent_not_graduated_state_{agent.state.value}",
        })
        return None, receipt

    # Import patterns module
    from .patterns import store_pattern

    # Create pattern from agent's approach
    pattern = {
        "agent_type": agent.agent_type.value,
        "gate_color": agent.gate_color,
        "original_confidence": agent.confidence_at_spawn,
        "decomposition_angle": agent.metadata.get("decomposition_angle"),
        "solution_approach": solution_approach,
        "created_from_agent": agent_id,
        "created_at": time.time(),
    }

    pattern_id, receipt = store_pattern(pattern, tenant_id)

    return pattern_id, receipt


def get_graduation_threshold() -> dict:
    """Return the graduation thresholds for display."""
    return {
        "effectiveness": AGENT_ESCAPE_VELOCITY,
        "autonomy": AGENT_AUTONOMY_THRESHOLD,
    }
