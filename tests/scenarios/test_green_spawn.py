"""Test GREEN gate spawning.

Pass criteria:
- GREEN gate spawns exactly 1 success_learner
- TTL is 60 seconds
- Agent is in ACTIVE state after spawn
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))



class TestGreenSpawn:
    """Test GREEN gate spawning behavior."""

    def setup_method(self):
        """Clear registry before each test."""
        from proofpack.spawner.registry import clear_registry
        clear_registry()

    def test_green_spawns_one_learner(self):
        """GREEN: spawns exactly 1 success_learner."""
        from proofpack.spawner.birth import simulate_spawn

        result = simulate_spawn("GREEN", 0.95)

        assert result["would_spawn"] == 1
        assert result["agent_types"] == ["success_learner"]
        assert result["ttl_seconds"] == 60

    def test_green_learner_ttl_60s(self):
        """GREEN: success_learner has TTL of 60 seconds."""
        from proofpack.spawner.birth import GREEN_LEARNER_TTL

        assert GREEN_LEARNER_TTL == 60

    def test_green_spawn_with_feature_enabled(self, monkeypatch):
        """GREEN: spawns agent when feature enabled."""
        monkeypatch.setattr("proofpack.config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("proofpack.config.features.FEATURE_GREEN_LEARNERS_ENABLED", True)

        from proofpack.spawner.birth import spawn_for_gate
        from proofpack.spawner.registry import get_population_count

        result, receipt = spawn_for_gate(
            gate_color="GREEN",
            confidence_score=0.95,
        )

        assert result is not None
        assert result.spawn_count == 1
        assert len(result.agent_ids) == 1
        assert get_population_count() == 1

    def test_green_spawn_with_feature_disabled(self, monkeypatch):
        """GREEN: no spawn when feature disabled."""
        monkeypatch.setattr("proofpack.config.features.FEATURE_AGENT_SPAWNING_ENABLED", False)

        from proofpack.spawner.birth import spawn_for_gate
        from proofpack.spawner.registry import get_population_count

        result, receipt = spawn_for_gate(
            gate_color="GREEN",
            confidence_score=0.95,
        )

        assert result is None
        assert get_population_count() == 0

    def test_green_learner_has_correct_metadata(self, monkeypatch):
        """GREEN: success_learner has correct metadata."""
        monkeypatch.setattr("proofpack.config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("proofpack.config.features.FEATURE_GREEN_LEARNERS_ENABLED", True)

        from proofpack.spawner.birth import spawn_for_gate
        from proofpack.spawner.registry import get_agent

        result, _ = spawn_for_gate("GREEN", 0.95)

        agent = get_agent(result.agent_ids[0])
        assert agent is not None
        assert agent.metadata.get("purpose") == "capture_success_pattern"
