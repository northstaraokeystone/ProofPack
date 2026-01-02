"""Test sibling coordination.

Pass criteria:
- First solution triggers sibling termination
- Winner declared when confidence > 0.8
- All siblings receive termination signal
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))



class TestSiblingWin:
    """Test sibling coordination and winner declaration."""

    def setup_method(self):
        """Clear registry before each test."""
        from proofpack.spawner.registry import clear_registry
        clear_registry()

    def test_solution_threshold_is_0_8(self):
        """SIBLING: solution threshold is 0.8."""
        from proofpack.spawner.coordination import SOLUTION_CONFIDENCE_THRESHOLD

        assert SOLUTION_CONFIDENCE_THRESHOLD == 0.8

    def test_winner_declared_at_threshold(self, monkeypatch):
        """SIBLING: winner declared when confidence >= 0.8."""
        from proofpack.spawner.coordination import declare_winner
        from proofpack.spawner.lifecycle import activate_agent
        from proofpack.spawner.registry import AgentType, register_agent

        # Create group of siblings
        group_id = "test-group"
        agent1, _ = register_agent(AgentType.HELPER, "RED", 0.5, group_id=group_id)
        agent2, _ = register_agent(AgentType.HELPER, "RED", 0.5, group_id=group_id)
        agent3, _ = register_agent(AgentType.HELPER, "RED", 0.5, group_id=group_id)

        # Activate all
        activate_agent(agent1.agent_id)
        activate_agent(agent2.agent_id)
        activate_agent(agent3.agent_id)

        # Agent 2 finds solution with 0.85 confidence
        success, receipt = declare_winner(agent2.agent_id, 0.85)

        assert success is True

    def test_siblings_pruned_on_win(self, monkeypatch):
        """SIBLING: other siblings pruned when one wins."""
        from proofpack.spawner.coordination import declare_winner
        from proofpack.spawner.lifecycle import activate_agent
        from proofpack.spawner.registry import AgentState, AgentType, get_agent, register_agent

        # Create group of siblings
        group_id = "test-group"
        agent1, _ = register_agent(AgentType.HELPER, "RED", 0.5, group_id=group_id)
        agent2, _ = register_agent(AgentType.HELPER, "RED", 0.5, group_id=group_id)
        agent3, _ = register_agent(AgentType.HELPER, "RED", 0.5, group_id=group_id)

        # Activate all
        activate_agent(agent1.agent_id)
        activate_agent(agent2.agent_id)
        activate_agent(agent3.agent_id)

        # Agent 2 wins
        declare_winner(agent2.agent_id, 0.85)

        # Check that siblings were pruned
        # Note: pruned agents are removed from registry
        a1 = get_agent(agent1.agent_id)
        a3 = get_agent(agent3.agent_id)

        # Siblings should be gone (pruned and removed)
        assert a1 is None or a1.state == AgentState.PRUNED
        assert a3 is None or a3.state == AgentState.PRUNED

    def test_below_threshold_not_winner(self, monkeypatch):
        """SIBLING: below threshold does not declare winner."""
        from proofpack.spawner.coordination import declare_winner
        from proofpack.spawner.lifecycle import activate_agent
        from proofpack.spawner.registry import AgentType, register_agent

        agent, _ = register_agent(AgentType.HELPER, "RED", 0.5)
        activate_agent(agent.agent_id)

        # Try to declare winner with 0.75 confidence (below 0.8)
        success, receipt = declare_winner(agent.agent_id, 0.75)

        assert success is False

    def test_coordination_receipt_emitted(self, monkeypatch):
        """SIBLING: coordination receipt emitted on resolution."""
        import time

        from proofpack.spawner.coordination import SolutionEvent, coordinate_siblings
        from proofpack.spawner.lifecycle import activate_agent
        from proofpack.spawner.registry import AgentType, register_agent

        group_id = "test-group"
        agent1, _ = register_agent(AgentType.HELPER, "RED", 0.5, group_id=group_id)
        activate_agent(agent1.agent_id)

        event = SolutionEvent(
            agent_id=agent1.agent_id,
            confidence=0.9,
            timestamp=time.time(),
            solution_data={},
        )

        status, receipt = coordinate_siblings(group_id, [event])

        assert receipt["receipt_type"] in ("coordination", "coordination_check")
