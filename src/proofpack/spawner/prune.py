"""Agent Pruning - Terminate agents that should no longer run.

Pruning reasons:
- TTL_EXPIRED: Agent exceeded its time-to-live
- SIBLING_SOLVED: Another agent in the group found the solution
- DEPTH_LIMIT: Agent attempted to spawn beyond max depth
- RESOURCE_CAP: Population limit reached
- LOW_EFFECTIVENESS: Agent performing poorly
"""

import time
from dataclasses import dataclass
from enum import Enum

from proofpack.core.receipt import emit_receipt

from .lifecycle import transition_agent
from .registry import (
    AgentState,
    get_agent,
    get_agents_by_group,
    get_expired_agents,
    remove_agent,
)


class PruneReason(Enum):
    """Reasons for pruning an agent."""
    TTL_EXPIRED = "TTL_EXPIRED"
    SIBLING_SOLVED = "SIBLING_SOLVED"
    DEPTH_LIMIT = "DEPTH_LIMIT"
    RESOURCE_CAP = "RESOURCE_CAP"
    LOW_EFFECTIVENESS = "LOW_EFFECTIVENESS"
    MANUAL = "MANUAL"


@dataclass
class PruneResult:
    """Result of a prune operation."""
    agent_id: str
    reason: PruneReason
    success: bool
    resources_freed: dict


def prune_agent(
    agent_id: str,
    reason: PruneReason,
    tenant_id: str = "default",
) -> tuple[PruneResult, dict]:
    """Terminate a single agent.

    Returns (PruneResult, pruning_receipt)
    """
    agent = get_agent(agent_id)

    if not agent:
        result = PruneResult(
            agent_id=agent_id,
            reason=reason,
            success=False,
            resources_freed={},
        )
        receipt = emit_receipt("pruning_error", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "error": "agent_not_found",
        })
        return result, receipt

    if agent.state in (AgentState.GRADUATED, AgentState.PRUNED):
        result = PruneResult(
            agent_id=agent_id,
            reason=reason,
            success=False,
            resources_freed={},
        )
        receipt = emit_receipt("pruning_error", {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "error": f"agent_already_terminal_{agent.state.value}",
        })
        return result, receipt

    # Transition to PRUNED state
    transition_agent(
        agent_id,
        AgentState.PRUNED,
        reason=reason.value,
        tenant_id=tenant_id,
    )

    # Calculate resources freed
    time_alive = time.time() - agent.spawned_at
    resources_freed = {
        "memory_mb": 1,  # Placeholder - actual implementation would track
        "compute_units": int(time_alive * 0.1),
    }

    # Remove from registry
    remove_agent(agent_id)

    result = PruneResult(
        agent_id=agent_id,
        reason=reason,
        success=True,
        resources_freed=resources_freed,
    )

    receipt = emit_receipt("pruning", {
        "tenant_id": tenant_id,
        "agents_terminated": [agent_id],
        "reason": reason.value,
        "resources_freed": resources_freed,
    })

    return result, receipt


def prune_expired(tenant_id: str = "default") -> tuple[list[PruneResult], dict]:
    """Prune all agents that have exceeded their TTL.

    Returns (list of PruneResults, batch_receipt)
    """
    expired = get_expired_agents()
    results = []

    for agent in expired:
        result, _ = prune_agent(
            agent.agent_id,
            PruneReason.TTL_EXPIRED,
            tenant_id,
        )
        if result.success:
            results.append(result)

    # Emit batch receipt
    if results:
        total_resources = {
            "memory_mb": sum(r.resources_freed.get("memory_mb", 0) for r in results),
            "compute_units": sum(r.resources_freed.get("compute_units", 0) for r in results),
        }

        receipt = emit_receipt("pruning", {
            "tenant_id": tenant_id,
            "agents_terminated": [r.agent_id for r in results],
            "reason": "TTL_EXPIRED",
            "resources_freed": total_resources,
        })
    else:
        receipt = emit_receipt("pruning_check", {
            "tenant_id": tenant_id,
            "expired_count": 0,
            "pruned_count": 0,
        })

    return results, receipt


def prune_siblings(
    group_id: str,
    winner_id: str,
    tenant_id: str = "default",
) -> tuple[list[PruneResult], dict]:
    """Prune all agents in a group except the winner.

    Called when one agent solves the problem before others.

    Returns (list of PruneResults, batch_receipt)
    """
    agents = get_agents_by_group(group_id)
    results = []

    for agent in agents:
        if agent.agent_id == winner_id:
            continue  # Don't prune the winner

        if agent.state in (AgentState.GRADUATED, AgentState.PRUNED):
            continue  # Already terminal

        result, _ = prune_agent(
            agent.agent_id,
            PruneReason.SIBLING_SOLVED,
            tenant_id,
        )
        if result.success:
            results.append(result)

    # Emit batch receipt
    if results:
        total_resources = {
            "memory_mb": sum(r.resources_freed.get("memory_mb", 0) for r in results),
            "compute_units": sum(r.resources_freed.get("compute_units", 0) for r in results),
        }

        receipt = emit_receipt("pruning", {
            "tenant_id": tenant_id,
            "agents_terminated": [r.agent_id for r in results],
            "reason": "SIBLING_SOLVED",
            "winner_id": winner_id,
            "group_id": group_id,
            "resources_freed": total_resources,
        })
    else:
        receipt = emit_receipt("sibling_prune_check", {
            "tenant_id": tenant_id,
            "group_id": group_id,
            "winner_id": winner_id,
            "siblings_pruned": 0,
        })

    return results, receipt


def prune_by_effectiveness(
    agent_id: str,
    effectiveness: float,
    threshold: float = 0.3,
    tenant_id: str = "default",
) -> tuple[PruneResult | None, dict | None]:
    """Prune agent if effectiveness is below threshold.

    Returns (PruneResult, receipt) or (None, None) if above threshold.
    """
    if effectiveness >= threshold:
        return None, None

    return prune_agent(
        agent_id,
        PruneReason.LOW_EFFECTIVENESS,
        tenant_id,
    )


def force_prune_oldest(
    count: int = 1,
    tenant_id: str = "default",
) -> tuple[list[PruneResult], dict]:
    """Force prune the N oldest agents to make room.

    Used when at resource cap and need to spawn new agents.

    Returns (list of PruneResults, batch_receipt)
    """
    from .registry import get_active_agents

    active = get_active_agents()

    # Sort by spawn time (oldest first)
    active.sort(key=lambda a: a.spawned_at)

    results = []
    for agent in active[:count]:
        result, _ = prune_agent(
            agent.agent_id,
            PruneReason.RESOURCE_CAP,
            tenant_id,
        )
        if result.success:
            results.append(result)

    # Emit batch receipt
    if results:
        total_resources = {
            "memory_mb": sum(r.resources_freed.get("memory_mb", 0) for r in results),
            "compute_units": sum(r.resources_freed.get("compute_units", 0) for r in results),
        }

        receipt = emit_receipt("pruning", {
            "tenant_id": tenant_id,
            "agents_terminated": [r.agent_id for r in results],
            "reason": "RESOURCE_CAP",
            "resources_freed": total_resources,
        })
    else:
        receipt = emit_receipt("force_prune_check", {
            "tenant_id": tenant_id,
            "requested": count,
            "pruned": 0,
        })

    return results, receipt
