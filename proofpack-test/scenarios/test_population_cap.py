"""Test population cap enforcement.

Pass criteria:
- Spawning stops at 50 total agents
- spawn_rejected receipt emitted when at capacity
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest


class TestPopulationCap:
    """Test population cap enforcement."""

    def setup_method(self):
        """Clear registry before each test."""
        from spawner.registry import clear_registry
        clear_registry()

    def test_max_population_is_fifty(self):
        """POPULATION: maximum is 50 agents."""
        from spawner.registry import MAX_AGENTS

        assert MAX_AGENTS == 50

    def test_can_spawn_when_under_limit(self):
        """POPULATION: can spawn when under limit."""
        from spawner.registry import can_spawn, get_population_count

        assert get_population_count() == 0
        assert can_spawn(1) is True
        assert can_spawn(50) is True

    def test_cannot_spawn_at_capacity(self, monkeypatch):
        """POPULATION: spawning blocked at capacity."""
        from spawner.registry import register_agent, AgentType, can_spawn, MAX_AGENTS

        # Fill up to capacity
        for i in range(MAX_AGENTS):
            agent, _ = register_agent(AgentType.HELPER, "RED", 0.5)
            assert agent is not None, f"Failed to register agent {i}"

        # Should not be able to spawn more
        assert can_spawn(1) is False

    def test_spawn_rejected_receipt(self, monkeypatch):
        """POPULATION: spawn_rejected receipt emitted at capacity."""
        from spawner.registry import register_agent, AgentType, MAX_AGENTS

        # Fill up to capacity
        for i in range(MAX_AGENTS):
            register_agent(AgentType.HELPER, "RED", 0.5)

        # Try to register one more
        agent, receipt = register_agent(AgentType.HELPER, "RED", 0.5)

        assert agent is None
        assert receipt["receipt_type"] == "spawn_rejected"
        assert receipt["reason"] == "RESOURCE_CAP"

    def test_population_count_accurate(self):
        """POPULATION: count excludes pruned/graduated agents."""
        from spawner.registry import register_agent, AgentType, get_population_count
        from spawner.lifecycle import transition_agent
        from spawner.registry import AgentState

        agent1, _ = register_agent(AgentType.HELPER, "RED", 0.5)
        agent2, _ = register_agent(AgentType.HELPER, "RED", 0.5)

        assert get_population_count() == 2

        # Transition one to PRUNED
        transition_agent(agent1.agent_id, AgentState.PRUNED)

        # Count should only include active agents
        # Note: after pruning, agent is still in registry but in PRUNED state
        assert get_population_count() == 1
