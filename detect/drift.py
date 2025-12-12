"""Alert generation from classified anomalies per QED v7:289-290."""
from ledger.core import emit_receipt, dual_hash

# Severity levels per QED v7:289-290
SEVERITIES = ("low", "medium", "high", "critical")

# Component dependencies for blast radius calculation
COMPONENT_DEPS = {
    "ingest": ["anchor", "verify"],
    "anchor": ["compact", "verify"],
    "routing": ["retrieval", "brief"],
    "brief": ["packet", "decision"],
    "packet": ["audit", "output"]
}


def alert(anomaly: dict, tenant_id: str = "default") -> dict:
    """Generate alert from classified anomaly.

    SLO per QED v7:321: Alert latency < 60s median
    """
    classification = anomaly.get("classification", "drift")
    delta = abs(anomaly.get("delta", 0.0))
    metric = anomaly.get("metric", "unknown")

    # Determine severity from classification and delta magnitude
    if classification == "violation" or delta > 1.0:
        severity = "critical"
    elif classification in ("anti_pattern", "deviation") or delta > 0.5:
        severity = "high"
    elif classification == "degradation" or delta > 0.2:
        severity = "medium"
    else:
        severity = "low"

    # Calculate blast_radius: affected components
    blast_radius = COMPONENT_DEPS.get(metric, [metric])

    # Generate recommended action
    actions = {
        "critical": "Halt processing immediately. Page on-call. Investigate root cause.",
        "high": "Escalate to team lead. Pause non-critical operations.",
        "medium": "Monitor closely. Schedule investigation within 24h.",
        "low": "Log for analysis. Review in next sprint."
    }
    recommended_action = actions.get(severity, actions["low"])

    # Generate anomaly reference ID
    anomaly_id = dual_hash(f"{metric}:{classification}:{delta}")[:16]

    return emit_receipt("alert", {
        "anomaly_id": anomaly_id,
        "severity": severity,
        "blast_radius": blast_radius,
        "recommended_action": recommended_action,
        "escalation_required": severity in ("high", "critical")
    }, tenant_id=tenant_id)
