"""Track confidence drops (wounds) over time.

A wound is a significant confidence drop that indicates the system is struggling.
Tracking wounds helps detect when the system needs help.

When wound count exceeds threshold, triggers spawn evaluation.
"""
import time
from dataclasses import dataclass, field

from core.receipt import emit_receipt
from core.receipt import dual_hash
from constants import WOUND_DROP_THRESHOLD, WOUND_SPAWN_THRESHOLD
from config.features import FEATURE_WOUND_DETECTION_ENABLED, FEATURE_AGENT_SPAWNING_ENABLED


@dataclass
class WoundEvent:
    """A single wound event (confidence drop)."""
    wound_index: int
    confidence_before: float
    confidence_after: float
    drop_magnitude: float
    timestamp: float
    action_id: str


@dataclass
class WoundTracker:
    """Tracks wounds over a rolling window."""
    window_size: int = 100
    drop_threshold: float = WOUND_DROP_THRESHOLD
    spawn_threshold: int = WOUND_SPAWN_THRESHOLD
    confidence_history: list[float] = field(default_factory=list)
    wound_events: list[WoundEvent] = field(default_factory=list)
    wound_count: int = 0


def track_confidence(
    tracker: WoundTracker,
    new_confidence: float,
    action_id: str = "",
    variance: float = 0.0,
    tenant_id: str = "default"
) -> tuple[WoundTracker, WoundEvent | None, dict | None]:
    """Track a new confidence value, detect wounds, trigger spawning.

    Returns (updated_tracker, wound_event_if_detected, receipt_if_wound)
    """
    # Add to history
    new_history = tracker.confidence_history + [new_confidence]

    # Trim to window size
    if len(new_history) > tracker.window_size:
        new_history = new_history[-tracker.window_size:]

    # Check for wound (drop from previous)
    wound_event = None
    receipt = None

    if len(tracker.confidence_history) > 0:
        prev_confidence = tracker.confidence_history[-1]
        drop = prev_confidence - new_confidence

        if drop >= tracker.drop_threshold:
            # Wound detected
            wound_event = WoundEvent(
                wound_index=tracker.wound_count + 1,
                confidence_before=prev_confidence,
                confidence_after=new_confidence,
                drop_magnitude=drop,
                timestamp=time.time(),
                action_id=action_id
            )

            if FEATURE_WOUND_DETECTION_ENABLED:
                receipt = emit_receipt("wound", {
                    "wound_index": wound_event.wound_index,
                    "confidence_before": prev_confidence,
                    "confidence_after": new_confidence,
                    "drop_magnitude": drop,
                    "action_id": action_id,
                    "payload_hash": dual_hash(f"wound:{wound_event.wound_index}:{drop}")
                }, tenant_id=tenant_id)

    # Create updated tracker
    new_wound_events = tracker.wound_events + ([wound_event] if wound_event else [])
    new_wound_count = tracker.wound_count + (1 if wound_event else 0)

    updated_tracker = WoundTracker(
        window_size=tracker.window_size,
        drop_threshold=tracker.drop_threshold,
        spawn_threshold=tracker.spawn_threshold,
        confidence_history=new_history,
        wound_events=new_wound_events,
        wound_count=new_wound_count
    )

    # Check if wound threshold triggers spawn evaluation
    if wound_event and new_wound_count >= tracker.spawn_threshold:
        _evaluate_spawn(
            wound_count=new_wound_count,
            confidence=new_confidence,
            variance=variance,
            tenant_id=tenant_id,
        )

    return updated_tracker, wound_event, receipt


def _evaluate_spawn(
    wound_count: int,
    confidence: float,
    variance: float,
    tenant_id: str,
) -> None:
    """Evaluate whether to spawn helpers based on wounds."""
    if not FEATURE_AGENT_SPAWNING_ENABLED:
        # Log shadow mode
        emit_receipt("spawn_evaluation_shadow", {
            "tenant_id": tenant_id,
            "wound_count": wound_count,
            "confidence": confidence,
            "trigger": "WOUND_THRESHOLD",
            "would_spawn": True,
        })
        return

    try:
        from spawner.birth import spawn_for_gate

        # RED gate spawn triggered by wound threshold
        spawn_for_gate(
            gate_color="RED",
            confidence_score=confidence,
            wound_count=wound_count,
            variance=variance,
            tenant_id=tenant_id,
        )

    except ImportError:
        pass  # Spawner not available


def get_wound_summary(
    tracker: WoundTracker,
    tenant_id: str = "default"
) -> tuple[dict, dict]:
    """Get summary of wound status.

    Returns (summary_dict, receipt)
    """
    # Calculate wound density (wounds per confidence reading)
    total_readings = len(tracker.confidence_history)
    wound_density = tracker.wound_count / max(total_readings, 1)

    # Calculate average drop magnitude
    avg_drop = 0.0
    if tracker.wound_events:
        avg_drop = sum(w.drop_magnitude for w in tracker.wound_events) / len(tracker.wound_events)

    # Calculate recent wound rate (last 20 readings)
    recent_history = tracker.confidence_history[-20:]
    recent_wounds = 0
    for i in range(1, len(recent_history)):
        if recent_history[i-1] - recent_history[i] >= tracker.drop_threshold:
            recent_wounds += 1

    # Calculate spawn multiplier
    spawn_multiplier = calculate_spawn_multiplier(tracker.wound_count)

    summary = {
        "total_wounds": tracker.wound_count,
        "wound_density": wound_density,
        "average_drop_magnitude": avg_drop,
        "recent_wounds": recent_wounds,
        "history_length": total_readings,
        "spawn_threshold": tracker.spawn_threshold,
        "spawn_multiplier": spawn_multiplier,
        "would_trigger_spawn": tracker.wound_count >= tracker.spawn_threshold,
    }

    receipt = emit_receipt("wound_summary", {
        **summary,
        "payload_hash": dual_hash(str(summary))
    }, tenant_id=tenant_id)

    return summary, receipt


def calculate_spawn_multiplier(wound_count: int) -> int:
    """Calculate how many helpers would spawn for given wound count.

    Formula: (wound_count // 2) + 1
    """
    return (wound_count // 2) + 1


def get_current_multiplier(tracker: WoundTracker) -> int:
    """Get current spawn multiplier based on tracker state."""
    return calculate_spawn_multiplier(tracker.wound_count)


def stoprule_excessive_wounds(
    tracker: WoundTracker,
    critical_threshold: int = 10
):
    """Stoprule if wound count exceeds critical threshold."""
    if tracker.wound_count >= critical_threshold:
        emit_receipt("anomaly", {
            "metric": "wound_count",
            "baseline": critical_threshold,
            "delta": tracker.wound_count - critical_threshold,
            "classification": "degradation",
            "action": "escalate"
        })
