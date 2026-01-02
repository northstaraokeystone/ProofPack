"""Anomaly classification per CLAUDEME.txt:344."""
from core.receipt import emit_receipt

# Classification types per CLAUDEME.txt:344
CLASSIFICATIONS = ("drift", "degradation", "violation", "deviation", "anti_pattern")

# Action types per CLAUDEME.txt:345
ACTIONS = ("alert", "escalate", "halt", "auto_fix")


def emit_anomaly(metric: str, baseline: float, delta: float,
                 classification: str, action: str, tenant_id: str = "default") -> dict:
    """Emit anomaly_receipt per CLAUDEME.txt:348-354. Used by all stoprules."""
    return emit_receipt("anomaly", {
        "metric": metric,
        "baseline": baseline,
        "delta": delta,
        "classification": classification,
        "action": action
    }, tenant_id=tenant_id)


def classify(event: dict, baseline: dict = None, tenant_id: str = "default") -> dict:
    """Classify detected events into anomaly types.

    Returns anomaly_receipt per CLAUDEME.txt:336.
    """
    baseline = baseline or {}
    metric = event.get("metric", "unknown")
    current = event.get("value", 0.0)
    base_value = baseline.get(metric, current)

    # Calculate delta from baseline
    delta = current - base_value if base_value else 0.0
    abs_delta = abs(delta)

    # Determine classification based on delta magnitude and direction
    if event.get("anti_pattern"):
        classification = "anti_pattern"
    elif event.get("rule_breach"):
        classification = "violation"
    elif abs_delta > 0.5:
        classification = "deviation"
    elif abs_delta > 0.1:
        classification = "degradation"
    else:
        classification = "drift"

    # Determine action based on severity
    if classification == "violation":
        action = "halt"
    elif classification in ("anti_pattern", "deviation"):
        action = "escalate"
    elif classification == "degradation":
        action = "alert"
    else:
        action = "auto_fix"

    return emit_anomaly(metric, base_value, delta, classification, action, tenant_id)
