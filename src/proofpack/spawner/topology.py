"""Topology Classification - Apply META-LOOP classification to agents.

Agents are patterns. Apply the same topology rules:
- OPEN: effectiveness >= 0.85, autonomy > 0.75 -> Graduate to permanent helper
- CLOSED: effectiveness < 0.85 -> Prune, extract learnings
- HYBRID: transfer_score > 0.70 -> Transfer to other subsystem
"""

from dataclasses import dataclass
from enum import Enum

from proofpack.core.receipt import emit_receipt

# Topology thresholds (from constants.py)
AGENT_ESCAPE_VELOCITY = 0.85
AGENT_AUTONOMY_THRESHOLD = 0.75
AGENT_TRANSFER_THRESHOLD = 0.70


class TopologyClass(Enum):
    """Agent topology classification."""
    OPEN = "OPEN"       # Graduate to permanent helper
    CLOSED = "CLOSED"   # Prune, extract learnings
    HYBRID = "HYBRID"   # Transfer to other subsystem


class RecommendedAction(Enum):
    """Recommended action based on topology."""
    GRADUATE = "GRADUATE"
    PRUNE = "PRUNE"
    TRANSFER = "TRANSFER"


@dataclass
class TopologyResult:
    """Result of topology classification."""
    agent_id: str
    classification: TopologyClass
    effectiveness: float
    autonomy_score: float
    transfer_score: float
    recommended_action: RecommendedAction


def classify_topology(
    agent_id: str,
    effectiveness: float,
    autonomy_score: float,
    transfer_score: float = 0.0,
    tenant_id: str = "default",
) -> tuple[TopologyResult, dict]:
    """Classify an agent's topology and determine lifecycle outcome.

    Classification rules:
    - OPEN: effectiveness >= 0.85 AND autonomy > 0.75
    - HYBRID: transfer_score > 0.70 (even if not fully effective)
    - CLOSED: everything else

    Returns (TopologyResult, topology_receipt)
    """
    # Determine classification
    if effectiveness >= AGENT_ESCAPE_VELOCITY and autonomy_score > AGENT_AUTONOMY_THRESHOLD:
        classification = TopologyClass.OPEN
        recommended_action = RecommendedAction.GRADUATE
    elif transfer_score > AGENT_TRANSFER_THRESHOLD:
        classification = TopologyClass.HYBRID
        recommended_action = RecommendedAction.TRANSFER
    else:
        classification = TopologyClass.CLOSED
        recommended_action = RecommendedAction.PRUNE

    result = TopologyResult(
        agent_id=agent_id,
        classification=classification,
        effectiveness=effectiveness,
        autonomy_score=autonomy_score,
        transfer_score=transfer_score,
        recommended_action=recommended_action,
    )

    receipt = emit_receipt("topology", {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "classification": classification.value,
        "effectiveness": effectiveness,
        "autonomy_score": autonomy_score,
        "transfer_score": transfer_score,
        "recommended_action": recommended_action.value,
    })

    return result, receipt


def apply_topology_action(
    result: TopologyResult,
    solution_approach: dict | None = None,
    target_subsystem: str | None = None,
    tenant_id: str = "default",
) -> tuple[bool, dict]:
    """Apply the recommended action based on topology classification.

    Returns (success, action_receipt)
    """
    if result.recommended_action == RecommendedAction.GRADUATE:
        from .graduate import evaluate_graduation, promote_to_pattern

        grad_result, grad_receipt = evaluate_graduation(
            result.agent_id,
            result.effectiveness,
            result.autonomy_score,
            tenant_id,
        )

        if grad_result.graduated and solution_approach:
            pattern_id, _ = promote_to_pattern(
                result.agent_id,
                solution_approach,
                tenant_id,
            )
            receipt = emit_receipt("topology_action", {
                "tenant_id": tenant_id,
                "agent_id": result.agent_id,
                "action": "GRADUATE",
                "success": True,
                "pattern_id": pattern_id,
            })
            return True, receipt

        return grad_result.graduated, grad_receipt

    elif result.recommended_action == RecommendedAction.PRUNE:
        from .prune import PruneReason, prune_agent

        prune_result, prune_receipt = prune_agent(
            result.agent_id,
            PruneReason.LOW_EFFECTIVENESS,
            tenant_id,
        )

        # Extract learnings before fully removing
        learnings = extract_learnings(result.agent_id)

        receipt = emit_receipt("topology_action", {
            "tenant_id": tenant_id,
            "agent_id": result.agent_id,
            "action": "PRUNE",
            "success": prune_result.success,
            "learnings_extracted": bool(learnings),
        })

        return prune_result.success, receipt

    elif result.recommended_action == RecommendedAction.TRANSFER:
        # Transfer agent to another subsystem
        if not target_subsystem:
            receipt = emit_receipt("topology_action_error", {
                "tenant_id": tenant_id,
                "agent_id": result.agent_id,
                "action": "TRANSFER",
                "error": "no_target_subsystem_specified",
            })
            return False, receipt

        success = transfer_agent(result.agent_id, target_subsystem, tenant_id)

        receipt = emit_receipt("topology_action", {
            "tenant_id": tenant_id,
            "agent_id": result.agent_id,
            "action": "TRANSFER",
            "success": success,
            "target_subsystem": target_subsystem,
        })

        return success, receipt

    return False, emit_receipt("topology_action_error", {
        "tenant_id": tenant_id,
        "agent_id": result.agent_id,
        "error": "unknown_action",
    })


def extract_learnings(agent_id: str) -> dict | None:
    """Extract learnings from a CLOSED topology agent before pruning.

    This captures what didn't work so we can avoid similar approaches.
    """
    from .registry import get_agent

    agent = get_agent(agent_id)
    if not agent:
        return None

    learnings = {
        "agent_type": agent.agent_type.value,
        "gate_color": agent.gate_color,
        "confidence_at_spawn": agent.confidence_at_spawn,
        "decomposition_angle": agent.metadata.get("decomposition_angle"),
        "outcome": "ineffective",
        "avoid_pattern": True,
    }

    return learnings


def transfer_agent(
    agent_id: str,
    target_subsystem: str,
    tenant_id: str = "default",
) -> bool:
    """Transfer an agent to another subsystem.

    Currently a placeholder - would integrate with subsystem routing.
    """
    from .registry import get_agent

    agent = get_agent(agent_id)
    if not agent:
        return False

    # Update agent metadata to mark as transferred
    agent.metadata["transferred_to"] = target_subsystem
    agent.metadata["transfer_reason"] = "HYBRID_topology"

    emit_receipt("agent_transfer", {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "from_subsystem": "spawner",
        "to_subsystem": target_subsystem,
    })

    return True


def get_topology_thresholds() -> dict:
    """Return current topology thresholds for display."""
    return {
        "escape_velocity": AGENT_ESCAPE_VELOCITY,
        "autonomy_threshold": AGENT_AUTONOMY_THRESHOLD,
        "transfer_threshold": AGENT_TRANSFER_THRESHOLD,
    }


def batch_classify(
    agents: list[tuple[str, float, float, float]],
    tenant_id: str = "default",
) -> list[TopologyResult]:
    """Classify multiple agents at once.

    Args:
        agents: List of (agent_id, effectiveness, autonomy, transfer_score) tuples

    Returns:
        List of TopologyResults
    """
    results = []
    for agent_id, eff, auto, trans in agents:
        result, _ = classify_topology(
            agent_id, eff, auto, trans, tenant_id
        )
        results.append(result)

    return results
