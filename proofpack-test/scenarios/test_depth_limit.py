"""Test depth limit enforcement.

Pass criteria:
- Spawning stops at depth 3
- depth_limit_receipt emitted when blocking
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest


class TestDepthLimit:
    """Test depth limit enforcement."""

    def setup_method(self):
        """Clear registry before each test."""
        from spawner.registry import clear_registry
        clear_registry()

    def test_max_depth_is_three(self):
        """DEPTH: maximum depth is 3."""
        from spawner.registry import MAX_DEPTH

        assert MAX_DEPTH == 3

    def test_can_spawn_at_depth_zero(self):
        """DEPTH: root spawn (depth 0) allowed."""
        from spawner.recursion import can_spawn_child

        approval, _ = can_spawn_child(None)

        assert approval.approved is True
        assert approval.current_depth == 0

    def test_cannot_spawn_at_depth_three(self, monkeypatch):
        """DEPTH: spawning blocked at depth 3."""
        monkeypatch.setattr("config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("config.features.FEATURE_RED_HELPERS_ENABLED", True)

        from spawner.registry import register_agent, AgentType, get_agent
        from spawner.recursion import can_spawn_child

        # Create agent chain: root -> child -> grandchild
        root, _ = register_agent(AgentType.HELPER, "RED", 0.5)
        child, _ = register_agent(AgentType.HELPER, "RED", 0.5, parent_id=root.agent_id)
        grandchild, _ = register_agent(AgentType.HELPER, "RED", 0.5, parent_id=child.agent_id)

        # Verify depths
        assert root.depth == 0
        assert child.depth == 1
        assert grandchild.depth == 2

        # Try to spawn from grandchild (would be depth 3)
        approval, receipt = can_spawn_child(grandchild.agent_id)

        assert approval.approved is False
        assert "depth_limit" in approval.reason

    def test_depth_limit_receipt_emitted(self, monkeypatch):
        """DEPTH: depth_limit receipt emitted when blocking."""
        monkeypatch.setattr("config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("config.features.FEATURE_RED_HELPERS_ENABLED", True)

        from spawner.registry import register_agent, AgentType
        from spawner.recursion import can_spawn_child

        # Create depth 2 agent
        root, _ = register_agent(AgentType.HELPER, "RED", 0.5)
        child, _ = register_agent(AgentType.HELPER, "RED", 0.5, parent_id=root.agent_id)
        grandchild, _ = register_agent(AgentType.HELPER, "RED", 0.5, parent_id=child.agent_id)

        approval, receipt = can_spawn_child(grandchild.agent_id)

        assert receipt is not None
        assert receipt["receipt_type"] == "depth_limit"

    def test_lineage_tracking(self, monkeypatch):
        """DEPTH: lineage correctly tracks parent chain."""
        monkeypatch.setattr("config.features.FEATURE_AGENT_SPAWNING_ENABLED", True)
        monkeypatch.setattr("config.features.FEATURE_RED_HELPERS_ENABLED", True)

        from spawner.registry import register_agent, AgentType
        from spawner.recursion import get_lineage

        root, _ = register_agent(AgentType.HELPER, "RED", 0.5)
        child, _ = register_agent(AgentType.HELPER, "RED", 0.5, parent_id=root.agent_id)
        grandchild, _ = register_agent(AgentType.HELPER, "RED", 0.5, parent_id=child.agent_id)

        lineage = get_lineage(grandchild.agent_id)

        assert lineage is not None
        assert lineage.depth == 2
        assert len(lineage.parent_chain) == 2
        assert lineage.parent_chain[0] == child.agent_id
        assert lineage.parent_chain[1] == root.agent_id
        assert lineage.can_spawn_children is False
