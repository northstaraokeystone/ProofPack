"""Test wound detection.

Pass criteria:
- 15% confidence drop triggers wound
- wound_receipt emitted
- Wound tracking accumulates
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from proofpack.core.constants import WOUND_DROP_THRESHOLD
from proofpack.loop.src.wounds import WoundTracker, get_wound_summary, track_confidence


class TestWounds:
    """Test wound detection and tracking."""

    def test_15_percent_drop_triggers_wound(self):
        """WOUNDS: 15% drop triggers wound detection."""
        tracker = WoundTracker()

        # First reading
        tracker, wound1, _ = track_confidence(tracker, 0.9)
        assert wound1 is None, "First reading should not trigger wound"

        # 15% drop (from 0.9 to 0.75)
        tracker, wound2, _ = track_confidence(tracker, 0.75)
        assert wound2 is not None, "15% drop should trigger wound"
        assert wound2.drop_magnitude >= WOUND_DROP_THRESHOLD

    def test_small_drop_no_wound(self):
        """WOUNDS: Small drop (10%) does not trigger wound."""
        tracker = WoundTracker()

        tracker, _, _ = track_confidence(tracker, 0.9)
        tracker, wound, _ = track_confidence(tracker, 0.81)  # 10% drop

        assert wound is None, "10% drop should not trigger wound"

    def test_wound_count_accumulates(self):
        """WOUNDS: Multiple wounds accumulate."""
        tracker = WoundTracker()

        # Create multiple wounds
        confidences = [0.9, 0.7, 0.85, 0.65, 0.8, 0.6]  # 3 wounds: 0.9->0.7, 0.85->0.65, 0.8->0.6

        for conf in confidences:
            tracker, _, _ = track_confidence(tracker, conf)

        assert tracker.wound_count == 3, f"Expected 3 wounds, got {tracker.wound_count}"

    def test_wound_event_has_required_fields(self):
        """WOUNDS: Wound event contains all required fields."""
        tracker = WoundTracker()

        tracker, _, _ = track_confidence(tracker, 0.9)
        tracker, wound, _ = track_confidence(tracker, 0.7)  # 20% drop

        assert wound is not None
        assert wound.wound_index == 1
        assert wound.confidence_before == 0.9
        assert wound.confidence_after == 0.7
        assert wound.drop_magnitude == pytest.approx(0.2, abs=0.01)
        assert wound.timestamp > 0

    def test_wound_summary_correct(self):
        """WOUNDS: Summary statistics are accurate."""
        tracker = WoundTracker()

        # Create some wounds
        confidences = [0.9, 0.7, 0.85, 0.65]
        for conf in confidences:
            tracker, _, _ = track_confidence(tracker, conf)

        summary, receipt = get_wound_summary(tracker)

        assert summary["total_wounds"] == 2
        assert "wound_density" in summary
        assert "average_drop_magnitude" in summary

    def test_confidence_history_maintained(self):
        """WOUNDS: Confidence history is maintained."""
        tracker = WoundTracker()

        readings = [0.9, 0.85, 0.8, 0.75]
        for conf in readings:
            tracker, _, _ = track_confidence(tracker, conf)

        assert len(tracker.confidence_history) == 4
        assert tracker.confidence_history == readings

    def test_window_size_limit(self):
        """WOUNDS: History respects window size limit."""
        tracker = WoundTracker(window_size=5)

        # Add 10 readings
        for i in range(10):
            tracker, _, _ = track_confidence(tracker, 0.5 + (i * 0.01))

        assert len(tracker.confidence_history) == 5

    def test_custom_threshold(self):
        """WOUNDS: Custom drop threshold works."""
        tracker = WoundTracker(drop_threshold=0.25)

        tracker, _, _ = track_confidence(tracker, 0.9)
        tracker, wound, _ = track_confidence(tracker, 0.75)  # 15% drop

        assert wound is None, "15% drop should not trigger wound with 25% threshold"

        tracker, wound2, _ = track_confidence(tracker, 0.45)  # 30% drop

        assert wound2 is not None, "30% drop should trigger wound with 25% threshold"
