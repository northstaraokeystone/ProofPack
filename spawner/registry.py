"""Agent Registry - Track all active agents, enforce population limits.

Maintains an in-memory registry of active agents with their state.
Enforces the 50-agent population cap to prevent resource exhaustion.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from proofpack.core.receipt import emit_receipt

# Population limits
MAX_AGENTS = 50
MAX_DEPTH = 3
DEFAULT_TTL_SECONDS = 300


class AgentType(Enum):
    """Types of spawned agents."""
    SUCCESS_LEARNER = "success_learner"  # GREEN gate: captures successful patterns
    DRIFT_WATCHER = "drift_watcher"      # YELLOW gate: monitors context drift
    WOUND_WATCHER = "wound_watcher"      # YELLOW gate: monitors confidence drops
    SUCCESS_WATCHER = "success_watcher"  # YELLOW gate: monitors outcome vs prediction
    HELPER = "helper"                     # RED gate: tries decomposition angles


class AgentState(Enum):
    """Agent lifecycle states."""
    SPAWNED = "SPAWNED"
    ACTIVE = "ACTIVE"
    GRADUATED = "GRADUATED"
    PRUNED = "PRUNED"


@dataclass
class Agent:
    """A spawned agent instance."""
    agent_id: str
    agent_type: AgentType
    parent_id: str | None
    depth: int
    group_id: str
    state: AgentState
    spawned_at: float
    ttl_seconds: int
    confidence_at_spawn: float
    gate_color: str
    metadata: dict = field(default_factory=dict)


# In-memory agent registry (production would use ledger)
_agents: dict[str, Agent] = {}
_agent_groups: dict[str, list[str]] = {}  # group_id -> [agent_ids]


def register_agent(
    agent_type: AgentType,
    gate_color: str,
    confidence_at_spawn: float,
    parent_id: str | None = None,
    group_id: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    metadata: dict | None = None,
    tenant_id: str = "default",
) -> tuple[Agent | None, dict]:
    """Register a new agent in the registry.

    Returns (Agent, receipt) or (None, rejection_receipt) if at capacity.
    """
    # Check population cap
    active_count = get_population_count()
    if active_count >= MAX_AGENTS:
        receipt = emit_receipt("spawn_rejected", {
            "tenant_id": tenant_id,
            "reason": "RESOURCE_CAP",
            "current_population": active_count,
            "max_population": MAX_AGENTS,
            "agent_type": agent_type.value,
        })
        return None, receipt

    # Calculate depth
    depth = 0
    if parent_id and parent_id in _agents:
        parent = _agents[parent_id]
        depth = parent.depth + 1

        if depth > MAX_DEPTH:
            receipt = emit_receipt("spawn_rejected", {
                "tenant_id": tenant_id,
                "reason": "DEPTH_LIMIT",
                "parent_id": parent_id,
                "depth": depth,
                "max_depth": MAX_DEPTH,
            })
            return None, receipt

    # Create agent
    agent_id = str(uuid.uuid4())
    if group_id is None:
        group_id = str(uuid.uuid4())

    agent = Agent(
        agent_id=agent_id,
        agent_type=agent_type,
        parent_id=parent_id,
        depth=depth,
        group_id=group_id,
        state=AgentState.SPAWNED,
        spawned_at=time.time(),
        ttl_seconds=ttl_seconds,
        confidence_at_spawn=confidence_at_spawn,
        gate_color=gate_color,
        metadata=metadata or {},
    )

    # Register
    _agents[agent_id] = agent

    # Add to group
    if group_id not in _agent_groups:
        _agent_groups[group_id] = []
    _agent_groups[group_id].append(agent_id)

    # Emit receipt (not spawn receipt - that's in birth.py)
    receipt = emit_receipt("agent_registered", {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "agent_type": agent_type.value,
        "parent_id": parent_id,
        "depth": depth,
        "group_id": group_id,
        "ttl_seconds": ttl_seconds,
        "confidence_at_spawn": confidence_at_spawn,
        "gate_color": gate_color,
    })

    return agent, receipt


def get_agent(agent_id: str) -> Agent | None:
    """Get agent by ID."""
    return _agents.get(agent_id)


def get_active_agents() -> list[Agent]:
    """Get all agents in SPAWNED or ACTIVE state."""
    return [
        a for a in _agents.values()
        if a.state in (AgentState.SPAWNED, AgentState.ACTIVE)
    ]


def get_agents_by_group(group_id: str) -> list[Agent]:
    """Get all agents in a group."""
    agent_ids = _agent_groups.get(group_id, [])
    return [_agents[aid] for aid in agent_ids if aid in _agents]


def get_population_count() -> int:
    """Get count of non-terminated agents."""
    return len([
        a for a in _agents.values()
        if a.state in (AgentState.SPAWNED, AgentState.ACTIVE)
    ])


def can_spawn(count: int = 1) -> bool:
    """Check if we can spawn N more agents."""
    return get_population_count() + count <= MAX_AGENTS


def update_agent_state(
    agent_id: str,
    new_state: AgentState,
    tenant_id: str = "default",
) -> tuple[bool, dict | None]:
    """Update agent state. Returns (success, receipt)."""
    if agent_id not in _agents:
        return False, None

    agent = _agents[agent_id]
    old_state = agent.state
    agent.state = new_state

    receipt = emit_receipt("agent_state_change", {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "old_state": old_state.value,
        "new_state": new_state.value,
    })

    return True, receipt


def remove_agent(agent_id: str) -> bool:
    """Remove agent from registry (after pruning/graduation)."""
    if agent_id not in _agents:
        return False

    agent = _agents[agent_id]

    # Remove from group
    if agent.group_id in _agent_groups:
        if agent_id in _agent_groups[agent.group_id]:
            _agent_groups[agent.group_id].remove(agent_id)

    del _agents[agent_id]
    return True


def get_expired_agents() -> list[Agent]:
    """Get agents that have exceeded their TTL."""
    now = time.time()
    return [
        a for a in _agents.values()
        if a.state in (AgentState.SPAWNED, AgentState.ACTIVE)
        and (now - a.spawned_at) > a.ttl_seconds
    ]


def get_agents_by_parent(parent_id: str) -> list[Agent]:
    """Get all child agents of a parent."""
    return [a for a in _agents.values() if a.parent_id == parent_id]


def clear_registry() -> None:
    """Clear all agents (for testing)."""
    global _agents, _agent_groups
    _agents = {}
    _agent_groups = {}
