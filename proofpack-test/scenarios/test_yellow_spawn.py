"""Test YELLOW gate spawning.

Pass criteria:
- YELLOW gate spawns exactly 3 watchers
- Types: drift_watcher, wound_watcher, success_watcher
- TTL is action_duration + 30 seconds
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest


class TestYellowSpawn:
    """Test YELLOW gate spawning behavior."""

    def setup_method(self):
        """Clear registry before each test."""
        from spawner.registry import clear_registry
        clear_registry()

    def test_yellow_spawns_three_watchers(self):
        """YELLOW: spawns exactly 3 watchers."""
        from spawner.birth import simulate_spawn

        result = simulate_spawn("YELLOW", 0.82)

        assert result["would_spawn"] == 3
        assert "drift_watcher" in result["agent_types"]
        assert "wound_watcher" in result["agent_types"]
        assert "success_watcher" in result["agent_types"]

    def test_yellow_watcher_types(self, monkeypatch):
        """YELLOW: spawns correct watcher types."""
        monkeypatch.setattr("config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("config.features.FEATURE_YELLOW_WATCHERS_ENABLED", True)

        from spawner.birth import spawn_for_gate
        from spawner.registry import get_agent, AgentType

        result, _ = spawn_for_gate("YELLOW", 0.82)

        assert result.spawn_count == 3

        types = set()
        for agent_id in result.agent_ids:
            agent = get_agent(agent_id)
            types.add(agent.agent_type)

        assert AgentType.DRIFT_WATCHER in types
        assert AgentType.WOUND_WATCHER in types
        assert AgentType.SUCCESS_WATCHER in types

    def test_yellow_ttl_includes_action_duration(self, monkeypatch):
        """YELLOW: TTL = action_duration + 30s buffer."""
        monkeypatch.setattr("config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("config.features.FEATURE_YELLOW_WATCHERS_ENABLED", True)

        from spawner.birth import spawn_for_gate, YELLOW_WATCHER_TTL_BUFFER
        from spawner.registry import get_agent

        action_duration = 120  # 2 minutes

        result, _ = spawn_for_gate(
            "YELLOW", 0.82,
            action_duration_seconds=action_duration,
        )

        agent = get_agent(result.agent_ids[0])
        expected_ttl = action_duration + YELLOW_WATCHER_TTL_BUFFER

        assert agent.ttl_seconds == expected_ttl

    def test_yellow_with_feature_disabled(self, monkeypatch):
        """YELLOW: no spawn when feature disabled."""
        monkeypatch.setattr("config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("config.features.FEATURE_YELLOW_WATCHERS_ENABLED", False)

        from spawner.birth import spawn_for_gate
        from spawner.registry import get_population_count

        result, _ = spawn_for_gate("YELLOW", 0.82)

        assert result is None
        assert get_population_count() == 0

    def test_yellow_watcher_metadata(self, monkeypatch):
        """YELLOW: watchers have correct purpose metadata."""
        monkeypatch.setattr("config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("config.features.FEATURE_YELLOW_WATCHERS_ENABLED", True)

        from spawner.birth import spawn_for_gate
        from spawner.registry import get_agent

        result, _ = spawn_for_gate("YELLOW", 0.82)

        purposes = set()
        for agent_id in result.agent_ids:
            agent = get_agent(agent_id)
            purposes.add(agent.metadata.get("purpose"))

        assert "monitor_context_drift" in purposes
        assert "monitor_confidence_changes" in purposes
        assert "monitor_outcome_vs_prediction" in purposes
