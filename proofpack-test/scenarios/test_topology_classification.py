"""Test topology classification.

Pass criteria:
- OPEN: effectiveness >= 0.85, autonomy > 0.75
- CLOSED: effectiveness < 0.85
- HYBRID: transfer_score > 0.70
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest


class TestTopologyClassification:
    """Test META-LOOP topology classification for agents."""

    def setup_method(self):
        """Clear registry before each test."""
        from spawner.registry import clear_registry
        clear_registry()

    def test_open_topology_thresholds(self):
        """TOPOLOGY: OPEN requires effectiveness >= 0.85, autonomy > 0.75."""
        from spawner.topology import (
            AGENT_ESCAPE_VELOCITY,
            AGENT_AUTONOMY_THRESHOLD,
        )

        assert AGENT_ESCAPE_VELOCITY == 0.85
        assert AGENT_AUTONOMY_THRESHOLD == 0.75

    def test_open_classification(self):
        """TOPOLOGY: high effectiveness + autonomy = OPEN."""
        from spawner.topology import classify_topology, TopologyClass

        result, _ = classify_topology(
            agent_id="test",
            effectiveness=0.90,
            autonomy_score=0.80,
        )

        assert result.classification == TopologyClass.OPEN
        assert result.recommended_action.value == "GRADUATE"

    def test_closed_classification(self):
        """TOPOLOGY: low effectiveness = CLOSED."""
        from spawner.topology import classify_topology, TopologyClass

        result, _ = classify_topology(
            agent_id="test",
            effectiveness=0.60,
            autonomy_score=0.80,
        )

        assert result.classification == TopologyClass.CLOSED
        assert result.recommended_action.value == "PRUNE"

    def test_hybrid_classification(self):
        """TOPOLOGY: high transfer score = HYBRID."""
        from spawner.topology import classify_topology, TopologyClass, AGENT_TRANSFER_THRESHOLD

        assert AGENT_TRANSFER_THRESHOLD == 0.70

        result, _ = classify_topology(
            agent_id="test",
            effectiveness=0.70,  # Below OPEN threshold
            autonomy_score=0.60,
            transfer_score=0.75,  # Above transfer threshold
        )

        assert result.classification == TopologyClass.HYBRID
        assert result.recommended_action.value == "TRANSFER"

    def test_topology_receipt_emitted(self):
        """TOPOLOGY: topology receipt emitted on classification."""
        from spawner.topology import classify_topology

        result, receipt = classify_topology(
            agent_id="test",
            effectiveness=0.85,
            autonomy_score=0.80,
        )

        assert receipt["receipt_type"] == "topology"
        assert receipt["classification"] == result.classification.value
        assert receipt["recommended_action"] == result.recommended_action.value

    def test_open_requires_both_thresholds(self):
        """TOPOLOGY: OPEN requires both effectiveness AND autonomy."""
        from spawner.topology import classify_topology, TopologyClass

        # High effectiveness, low autonomy -> CLOSED
        result, _ = classify_topology(
            agent_id="test",
            effectiveness=0.90,
            autonomy_score=0.50,  # Below threshold
        )
        assert result.classification == TopologyClass.CLOSED

        # Low effectiveness, high autonomy -> CLOSED
        result, _ = classify_topology(
            agent_id="test",
            effectiveness=0.50,  # Below threshold
            autonomy_score=0.90,
        )
        assert result.classification == TopologyClass.CLOSED

    def test_batch_classification(self):
        """TOPOLOGY: batch classification works correctly."""
        from spawner.topology import batch_classify, TopologyClass

        agents = [
            ("agent1", 0.90, 0.80, 0.0),  # OPEN
            ("agent2", 0.60, 0.50, 0.0),  # CLOSED
            ("agent3", 0.70, 0.60, 0.75), # HYBRID
        ]

        results = batch_classify(agents)

        assert len(results) == 3
        assert results[0].classification == TopologyClass.OPEN
        assert results[1].classification == TopologyClass.CLOSED
        assert results[2].classification == TopologyClass.HYBRID
