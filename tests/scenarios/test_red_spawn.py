"""Test RED gate spawning.

Pass criteria:
- RED gate spawns (wound_count // 2) + 1 helpers
- Minimum 1, maximum 6 helpers
- High variance adds +1 helper
- TTL is 300 seconds
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))



class TestRedSpawn:
    """Test RED gate spawning behavior."""

    def setup_method(self):
        """Clear registry before each test."""
        from proofpack.spawner.registry import clear_registry
        clear_registry()

    def test_red_spawn_formula(self):
        """RED: spawns (wound_count // 2) + 1 helpers."""
        from proofpack.spawner.birth import calculate_helper_count

        test_cases = [
            (0, 1),   # (0 // 2) + 1 = 1
            (1, 1),   # (1 // 2) + 1 = 1
            (2, 2),   # (2 // 2) + 1 = 2
            (5, 3),   # (5 // 2) + 1 = 3
            (10, 6),  # (10 // 2) + 1 = 6, capped at 6
            (20, 6),  # Capped at 6
        ]

        for wounds, expected in test_cases:
            result = calculate_helper_count(wounds)
            assert result == expected, f"For {wounds} wounds, expected {expected}, got {result}"

    def test_red_minimum_one_helper(self):
        """RED: minimum 1 helper."""
        from proofpack.spawner.birth import MIN_HELPERS, calculate_helper_count

        assert MIN_HELPERS == 1
        assert calculate_helper_count(0) >= 1

    def test_red_maximum_six_helpers(self):
        """RED: maximum 6 helpers."""
        from proofpack.spawner.birth import MAX_HELPERS, calculate_helper_count

        assert MAX_HELPERS == 6
        assert calculate_helper_count(100) <= 6

    def test_red_high_variance_bonus(self):
        """RED: variance > 0.3 adds +1 helper."""
        from proofpack.spawner.birth import HIGH_VARIANCE_THRESHOLD, calculate_helper_count

        base = calculate_helper_count(4, variance=0.0)  # 3
        with_variance = calculate_helper_count(4, variance=0.35)  # 4

        assert HIGH_VARIANCE_THRESHOLD == 0.3
        assert with_variance == base + 1

    def test_red_spawn_with_feature_enabled(self, monkeypatch):
        """RED: spawns helpers when feature enabled."""
        monkeypatch.setattr("proofpack.config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("proofpack.config.features.FEATURE_RED_HELPERS_ENABLED", True)

        from proofpack.spawner.birth import spawn_for_gate
        from proofpack.spawner.registry import get_population_count

        result, _ = spawn_for_gate(
            gate_color="RED",
            confidence_score=0.5,
            wound_count=5,
        )

        assert result is not None
        assert result.spawn_count == 3  # (5 // 2) + 1
        assert get_population_count() == 3

    def test_red_helpers_have_decomposition_angles(self, monkeypatch):
        """RED: helpers have different decomposition angles."""
        monkeypatch.setattr("proofpack.config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("proofpack.config.features.FEATURE_RED_HELPERS_ENABLED", True)

        from proofpack.spawner.birth import spawn_for_gate
        from proofpack.spawner.registry import get_agent

        result, _ = spawn_for_gate("RED", 0.5, wound_count=10)

        angles = set()
        for agent_id in result.agent_ids:
            agent = get_agent(agent_id)
            angle = agent.metadata.get("decomposition_angle")
            if angle:
                angles.add(angle)

        # Should have multiple different angles
        assert len(angles) >= 2

    def test_red_ttl_300s(self, monkeypatch):
        """RED: helpers have TTL of 300 seconds."""
        monkeypatch.setattr("proofpack.config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("proofpack.config.features.FEATURE_RED_HELPERS_ENABLED", True)

        from proofpack.spawner.birth import spawn_for_gate
        from proofpack.spawner.registry import DEFAULT_TTL_SECONDS, get_agent

        result, _ = spawn_for_gate("RED", 0.5, wound_count=5)

        agent = get_agent(result.agent_ids[0])
        assert agent.ttl_seconds == DEFAULT_TTL_SECONDS
        assert DEFAULT_TTL_SECONDS == 300
