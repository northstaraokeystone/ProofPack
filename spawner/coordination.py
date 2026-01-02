"""Sibling Coordination - Coordinate parallel helpers, detect winner.

When multiple helpers work on the same problem:
- First helper to reach confidence > 0.8 "wins"
- Winning solution triggers graduation evaluation
- All sibling helpers receive termination signal
"""

import time
from dataclasses import dataclass
from enum import Enum

from core.receipt import emit_receipt

from .registry import get_agent, get_agents_by_group, AgentState
from .prune import prune_siblings


# Winning threshold
SOLUTION_CONFIDENCE_THRESHOLD = 0.8


class Resolution(Enum):
    """How a coordination group was resolved."""
    WINNER_FOUND = "WINNER_FOUND"
    ALL_FAILED = "ALL_FAILED"
    TIMEOUT = "TIMEOUT"
    IN_PROGRESS = "IN_PROGRESS"


@dataclass
class CoordinationStatus:
    """Status of a coordination group."""
    group_id: str
    participant_count: int
    active_count: int
    winner_id: str | None
    resolution: Resolution


@dataclass
class SolutionEvent:
    """An event indicating an agent found a solution."""
    agent_id: str
    confidence: float
    timestamp: float
    solution_data: dict


def coordinate_siblings(
    group_id: str,
    solution_events: list[SolutionEvent],
    tenant_id: str = "default",
) -> tuple[CoordinationStatus, dict]:
    """Coordinate a group of sibling agents.

    Checks for a winner (confidence > 0.8) and prunes losers.

    Returns (CoordinationStatus, coordination_receipt)
    """
    agents = get_agents_by_group(group_id)

    if not agents:
        status = CoordinationStatus(
            group_id=group_id,
            participant_count=0,
            active_count=0,
            winner_id=None,
            resolution=Resolution.ALL_FAILED,
        )
        receipt = emit_receipt("coordination", {
            "tenant_id": tenant_id,
            "agent_group_id": group_id,
            "winner_id": None,
            "participants": [],
            "resolution": "ALL_FAILED",
        })
        return status, receipt

    # Count active agents
    active = [a for a in agents if a.state == AgentState.ACTIVE]

    # Find winner from solution events
    winner_id = None
    winning_event = None

    for event in sorted(solution_events, key=lambda e: e.timestamp):
        if event.confidence >= SOLUTION_CONFIDENCE_THRESHOLD:
            # Verify agent is in this group
            agent = get_agent(event.agent_id)
            if agent and agent.group_id == group_id:
                winner_id = event.agent_id
                winning_event = event
                break

    if winner_id:
        # We have a winner - prune siblings
        prune_siblings(group_id, winner_id, tenant_id)

        status = CoordinationStatus(
            group_id=group_id,
            participant_count=len(agents),
            active_count=1,  # Only winner remains
            winner_id=winner_id,
            resolution=Resolution.WINNER_FOUND,
        )

        receipt = emit_receipt("coordination", {
            "tenant_id": tenant_id,
            "agent_group_id": group_id,
            "winner_id": winner_id,
            "participants": [a.agent_id for a in agents],
            "resolution": "WINNER_FOUND",
            "winning_confidence": winning_event.confidence if winning_event else None,
        })

    elif not active:
        # No active agents and no winner
        status = CoordinationStatus(
            group_id=group_id,
            participant_count=len(agents),
            active_count=0,
            winner_id=None,
            resolution=Resolution.ALL_FAILED,
        )

        receipt = emit_receipt("coordination", {
            "tenant_id": tenant_id,
            "agent_group_id": group_id,
            "winner_id": None,
            "participants": [a.agent_id for a in agents],
            "resolution": "ALL_FAILED",
        })

    else:
        # Still in progress
        status = CoordinationStatus(
            group_id=group_id,
            participant_count=len(agents),
            active_count=len(active),
            winner_id=None,
            resolution=Resolution.IN_PROGRESS,
        )

        receipt = emit_receipt("coordination_check", {
            "tenant_id": tenant_id,
            "agent_group_id": group_id,
            "active_count": len(active),
            "resolution": "IN_PROGRESS",
        })

    return status, receipt


def declare_winner(
    agent_id: str,
    confidence: float,
    solution_data: dict | None = None,
    tenant_id: str = "default",
) -> tuple[bool, dict]:
    """Declare an agent as the winner of its group.

    This triggers sibling pruning and graduation evaluation.

    Returns (success, receipt)
    """
    agent = get_agent(agent_id)

    if not agent:
        receipt = emit_receipt("winner_declaration_error", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "error": "agent_not_found",
        })
        return False, receipt

    if confidence < SOLUTION_CONFIDENCE_THRESHOLD:
        receipt = emit_receipt("winner_declaration_error", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "error": f"confidence_{confidence}_below_threshold_{SOLUTION_CONFIDENCE_THRESHOLD}",
        })
        return False, receipt

    # Create solution event
    event = SolutionEvent(
        agent_id=agent_id,
        confidence=confidence,
        timestamp=time.time(),
        solution_data=solution_data or {},
    )

    # Coordinate the group
    status, coord_receipt = coordinate_siblings(
        agent.group_id,
        [event],
        tenant_id,
    )

    if status.resolution == Resolution.WINNER_FOUND:
        # Trigger graduation evaluation
        from .graduate import evaluate_graduation

        # Estimate effectiveness from confidence
        effectiveness = confidence
        # Autonomy based on depth (deeper = less autonomous)
        autonomy = max(0.5, 1.0 - (agent.depth * 0.2))

        grad_result, grad_receipt = evaluate_graduation(
            agent_id,
            effectiveness,
            autonomy,
            tenant_id,
        )

        receipt = emit_receipt("winner_declared", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "group_id": agent.group_id,
            "confidence": confidence,
            "graduated": grad_result.graduated,
            "siblings_pruned": status.participant_count - 1,
        })

        return True, receipt

    receipt = emit_receipt("winner_declaration_failed", {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "reason": "coordination_did_not_resolve",
    })
    return False, receipt


def check_group_status(
    group_id: str,
    tenant_id: str = "default",
) -> CoordinationStatus:
    """Check the current status of a coordination group."""
    agents = get_agents_by_group(group_id)
    active = [a for a in agents if a.state == AgentState.ACTIVE]
    graduated = [a for a in agents if a.state == AgentState.GRADUATED]

    if graduated:
        winner = graduated[0]
        return CoordinationStatus(
            group_id=group_id,
            participant_count=len(agents),
            active_count=len(active),
            winner_id=winner.agent_id,
            resolution=Resolution.WINNER_FOUND,
        )

    if not active and agents:
        return CoordinationStatus(
            group_id=group_id,
            participant_count=len(agents),
            active_count=0,
            winner_id=None,
            resolution=Resolution.ALL_FAILED,
        )

    return CoordinationStatus(
        group_id=group_id,
        participant_count=len(agents),
        active_count=len(active),
        winner_id=None,
        resolution=Resolution.IN_PROGRESS,
    )


def timeout_group(
    group_id: str,
    tenant_id: str = "default",
) -> tuple[CoordinationStatus, dict]:
    """Mark a coordination group as timed out and prune all agents.

    Returns (final_status, receipt)
    """
    from .prune import prune_agent, PruneReason

    agents = get_agents_by_group(group_id)

    for agent in agents:
        if agent.state == AgentState.ACTIVE:
            prune_agent(agent.agent_id, PruneReason.TTL_EXPIRED, tenant_id)

    status = CoordinationStatus(
        group_id=group_id,
        participant_count=len(agents),
        active_count=0,
        winner_id=None,
        resolution=Resolution.TIMEOUT,
    )

    receipt = emit_receipt("coordination", {
        "tenant_id": tenant_id,
        "agent_group_id": group_id,
        "winner_id": None,
        "participants": [a.agent_id for a in agents],
        "resolution": "TIMEOUT",
    })

    return status, receipt
