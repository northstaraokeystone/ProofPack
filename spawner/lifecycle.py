"""Agent Lifecycle - Track agent state transitions.

States: SPAWNED -> ACTIVE -> (GRADUATED | PRUNED)

Single state machine for agent lifecycle. No ad-hoc state tracking.
"""

import time
from dataclasses import dataclass

from core.receipt import emit_receipt

from .registry import (
    AgentState,
    get_agent,
    update_agent_state,
)


@dataclass
class LifecycleEvent:
    """A lifecycle transition event."""
    agent_id: str
    from_state: AgentState
    to_state: AgentState
    timestamp: float
    reason: str


# Valid state transitions
VALID_TRANSITIONS = {
    AgentState.SPAWNED: {AgentState.ACTIVE, AgentState.PRUNED},
    AgentState.ACTIVE: {AgentState.GRADUATED, AgentState.PRUNED},
    AgentState.GRADUATED: set(),  # Terminal state
    AgentState.PRUNED: set(),     # Terminal state
}


def get_agent_state(agent_id: str) -> AgentState | None:
    """Get current state of an agent."""
    agent = get_agent(agent_id)
    return agent.state if agent else None


def can_transition(agent_id: str, to_state: AgentState) -> bool:
    """Check if a state transition is valid."""
    agent = get_agent(agent_id)
    if not agent:
        return False

    valid_next = VALID_TRANSITIONS.get(agent.state, set())
    return to_state in valid_next


def transition_agent(
    agent_id: str,
    to_state: AgentState,
    reason: str = "",
    tenant_id: str = "default",
) -> tuple[LifecycleEvent | None, dict | None]:
    """Transition an agent to a new state.

    Returns (LifecycleEvent, receipt) or (None, None) if invalid.
    """
    agent = get_agent(agent_id)
    if not agent:
        return None, None

    from_state = agent.state

    # Validate transition
    if not can_transition(agent_id, to_state):
        receipt = emit_receipt("lifecycle_error", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "error": "invalid_transition",
        })
        return None, receipt

    # Perform transition
    success, _ = update_agent_state(agent_id, to_state, tenant_id)
    if not success:
        return None, None

    event = LifecycleEvent(
        agent_id=agent_id,
        from_state=from_state,
        to_state=to_state,
        timestamp=time.time(),
        reason=reason,
    )

    receipt = emit_receipt("lifecycle", {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "from_state": from_state.value,
        "to_state": to_state.value,
        "reason": reason,
    })

    return event, receipt


def activate_agent(
    agent_id: str,
    tenant_id: str = "default",
) -> tuple[LifecycleEvent | None, dict | None]:
    """Transition agent from SPAWNED to ACTIVE."""
    return transition_agent(
        agent_id,
        AgentState.ACTIVE,
        reason="agent_started_work",
        tenant_id=tenant_id,
    )


def get_time_alive(agent_id: str) -> float:
    """Get seconds since agent was spawned."""
    agent = get_agent(agent_id)
    if not agent:
        return 0.0
    return time.time() - agent.spawned_at


def get_ttl_remaining(agent_id: str) -> float:
    """Get seconds remaining before TTL expiry."""
    agent = get_agent(agent_id)
    if not agent:
        return 0.0

    elapsed = time.time() - agent.spawned_at
    return max(0.0, agent.ttl_seconds - elapsed)


def is_terminal(agent_id: str) -> bool:
    """Check if agent is in a terminal state."""
    state = get_agent_state(agent_id)
    return state in (AgentState.GRADUATED, AgentState.PRUNED)


# Re-export AgentState for convenience
__all__ = [
    "AgentState",
    "LifecycleEvent",
    "get_agent_state",
    "can_transition",
    "transition_agent",
    "activate_agent",
    "get_time_alive",
    "get_ttl_remaining",
    "is_terminal",
]
