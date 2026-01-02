"""Spawner Module - Agent lifecycle management.

Spawned agents are confidence-triggered helpers that assist when the system
is uncertain. Traffic lights don't just stop - they create helpers.

Agent Types by Gate Color:
- GREEN (>0.9): success_learner - captures what worked
- YELLOW (0.7-0.9): drift/wound/success_watcher - monitors execution
- RED (<0.7): helper agents - try different decomposition angles

Lifecycle:
- SPAWNED: Agent created, awaiting activation
- ACTIVE: Agent working on problem
- GRADUATED: Agent promoted to permanent pattern (effectiveness >= 0.85)
- PRUNED: Agent terminated (TTL, sibling solved, depth limit, low effectiveness)

Constraints:
- Maximum depth: 3 levels (no infinite recursion)
- Maximum population: 50 agents (resource cap)
- Default TTL: 300 seconds (5 minutes)
- Every function emits receipt per CLAUDEME LAW_1
"""

from .birth import spawn_for_gate, simulate_spawn
from .lifecycle import AgentState, get_agent_state, transition_agent
from .registry import (
    register_agent,
    get_active_agents,
    get_population_count,
    can_spawn,
)
from .graduate import evaluate_graduation, promote_to_pattern
from .prune import prune_agent, prune_expired, prune_siblings
from .recursion import can_spawn_child, get_lineage
from .coordination import coordinate_siblings, declare_winner
from .topology import classify_topology, TopologyClass
from .patterns import store_pattern, find_matching_pattern

__all__ = [
    # Birth
    "spawn_for_gate",
    "simulate_spawn",
    # Lifecycle
    "AgentState",
    "get_agent_state",
    "transition_agent",
    # Registry
    "register_agent",
    "get_active_agents",
    "get_population_count",
    "can_spawn",
    # Graduate
    "evaluate_graduation",
    "promote_to_pattern",
    # Prune
    "prune_agent",
    "prune_expired",
    "prune_siblings",
    # Recursion
    "can_spawn_child",
    "get_lineage",
    # Coordination
    "coordinate_siblings",
    "declare_winner",
    # Topology
    "classify_topology",
    "TopologyClass",
    # Patterns
    "store_pattern",
    "find_matching_pattern",
]
