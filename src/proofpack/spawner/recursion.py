"""Recursion Control - Manage recursive spawning with depth limits.

Key insight: Spawned agents are not exempt from gating. Each helper agent
that proposes an action goes through the same gate.

Maximum depth: 3 levels (parent -> child -> grandchild)
At depth 3, no further spawning is allowed (prune instead).
"""

from dataclasses import dataclass

from proofpack.core.receipt import emit_receipt

from .registry import MAX_DEPTH, Agent, get_agent, get_agents_by_parent


@dataclass
class LineageInfo:
    """Lineage information for an agent."""
    agent_id: str
    depth: int
    parent_chain: list[str]
    can_spawn_children: bool


@dataclass
class SpawnApproval:
    """Result of spawn approval check."""
    approved: bool
    current_depth: int
    max_depth: int
    reason: str


def can_spawn_child(
    parent_agent_id: str | None,
    tenant_id: str = "default",
) -> tuple[SpawnApproval, dict]:
    """Check if a parent agent can spawn children.

    Returns (SpawnApproval, receipt)
    """
    if parent_agent_id is None:
        # Root-level spawn - always allowed (depth 0)
        approval = SpawnApproval(
            approved=True,
            current_depth=0,
            max_depth=MAX_DEPTH,
            reason="root_spawn",
        )
        receipt = emit_receipt("spawn_approval", {
            "tenant_id": tenant_id,
            "parent_agent_id": None,
            "approved": True,
            "current_depth": 0,
            "reason": "root_spawn",
        })
        return approval, receipt

    agent = get_agent(parent_agent_id)

    if not agent:
        approval = SpawnApproval(
            approved=False,
            current_depth=-1,
            max_depth=MAX_DEPTH,
            reason="parent_not_found",
        )
        receipt = emit_receipt("spawn_approval", {
            "tenant_id": tenant_id,
            "parent_agent_id": parent_agent_id,
            "approved": False,
            "reason": "parent_not_found",
        })
        return approval, receipt

    child_depth = agent.depth + 1

    if child_depth >= MAX_DEPTH:
        # Emit depth limit receipt
        approval = SpawnApproval(
            approved=False,
            current_depth=agent.depth,
            max_depth=MAX_DEPTH,
            reason=f"depth_limit_reached_{child_depth}_>= {MAX_DEPTH}",
        )
        receipt = emit_receipt("depth_limit", {
            "tenant_id": tenant_id,
            "parent_agent_id": parent_agent_id,
            "current_depth": agent.depth,
            "requested_depth": child_depth,
            "max_depth": MAX_DEPTH,
            "action": "spawn_blocked",
        })
        return approval, receipt

    approval = SpawnApproval(
        approved=True,
        current_depth=agent.depth,
        max_depth=MAX_DEPTH,
        reason="within_depth_limit",
    )
    receipt = emit_receipt("spawn_approval", {
        "tenant_id": tenant_id,
        "parent_agent_id": parent_agent_id,
        "approved": True,
        "current_depth": agent.depth,
        "child_depth": child_depth,
        "reason": "within_depth_limit",
    })
    return approval, receipt


def get_lineage(agent_id: str) -> LineageInfo | None:
    """Get the full lineage of an agent (chain of parents).

    Returns None if agent not found.
    """
    agent = get_agent(agent_id)
    if not agent:
        return None

    # Build parent chain
    parent_chain = []
    current = agent

    while current.parent_id:
        parent_chain.append(current.parent_id)
        parent = get_agent(current.parent_id)
        if not parent:
            break
        current = parent

    return LineageInfo(
        agent_id=agent_id,
        depth=agent.depth,
        parent_chain=parent_chain,
        can_spawn_children=agent.depth < MAX_DEPTH - 1,
    )


def get_depth(agent_id: str) -> int:
    """Get the depth of an agent. Returns -1 if not found."""
    agent = get_agent(agent_id)
    return agent.depth if agent else -1


def get_descendants(agent_id: str) -> list[Agent]:
    """Get all descendants of an agent (children, grandchildren, etc.)."""
    result = []
    to_process = [agent_id]

    while to_process:
        current_id = to_process.pop(0)
        children = get_agents_by_parent(current_id)
        result.extend(children)
        to_process.extend([c.agent_id for c in children])

    return result


def count_descendants(agent_id: str) -> int:
    """Count all descendants of an agent."""
    return len(get_descendants(agent_id))


def get_root_ancestor(agent_id: str) -> str | None:
    """Get the root ancestor of an agent (the original spawner).

    Returns agent_id itself if it has no parent.
    Returns None if agent not found.
    """
    agent = get_agent(agent_id)
    if not agent:
        return None

    if not agent.parent_id:
        return agent_id

    current = agent
    while current.parent_id:
        parent = get_agent(current.parent_id)
        if not parent:
            return current.agent_id
        current = parent

    return current.agent_id


def validate_recursive_spawn(
    spawn_request: dict,
    parent_agent_id: str | None,
    tenant_id: str = "default",
) -> tuple[bool, dict]:
    """Validate a recursive spawn request.

    Checks:
    - Depth limit not exceeded
    - Parent is in valid state for spawning
    - Requested spawn count is reasonable

    Returns (is_valid, receipt)
    """
    # Check depth
    approval, _ = can_spawn_child(parent_agent_id, tenant_id)

    if not approval.approved:
        receipt = emit_receipt("recursive_spawn_rejected", {
            "tenant_id": tenant_id,
            "parent_agent_id": parent_agent_id,
            "reason": approval.reason,
            "current_depth": approval.current_depth,
            "max_depth": approval.max_depth,
        })
        return False, receipt

    # If parent exists, check its state
    if parent_agent_id:
        agent = get_agent(parent_agent_id)
        if agent:
            from .registry import AgentState
            if agent.state not in (AgentState.SPAWNED, AgentState.ACTIVE):
                receipt = emit_receipt("recursive_spawn_rejected", {
                    "tenant_id": tenant_id,
                    "parent_agent_id": parent_agent_id,
                    "reason": f"parent_in_terminal_state_{agent.state.value}",
                })
                return False, receipt

    receipt = emit_receipt("recursive_spawn_approved", {
        "tenant_id": tenant_id,
        "parent_agent_id": parent_agent_id,
        "child_depth": approval.current_depth + 1,
    })
    return True, receipt
