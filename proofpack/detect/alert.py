"""Alert generation and escalation.

Functions:
    emit_alert: Generate alert with severity and escalation
    determine_severity: Pure function to determine alert severity
    should_escalate: Check if alert should be escalated
"""
import uuid

from proofpack.core.receipt import emit_receipt, StopRule


# Valid severity levels
SEVERITY_LEVELS = {"info", "warning", "error", "critical"}


def emit_alert(anomaly: dict, severity: str, tenant_id: str = "default") -> dict:
    """Generate alert from anomaly with severity.

    Validates severity, generates alert_id, determines blast_radius,
    sets escalation for critical alerts, and emits alert_receipt.

    Args:
        anomaly: Anomaly dict with classification information
        severity: Alert severity (info, warning, error, critical)
        tenant_id: Tenant identifier

    Returns:
        alert_receipt dict

    Raises:
        ValueError: If severity is not valid
    """
    if severity not in SEVERITY_LEVELS:
        raise ValueError(f"Invalid severity: {severity}. Valid: {SEVERITY_LEVELS}")

    alert_id = str(uuid.uuid4())

    # Determine blast radius from anomaly scope
    classification = anomaly.get("classification", "unknown")
    blast_radius = _determine_blast_radius(classification, anomaly)

    # Escalation for critical severity
    escalated = severity == "critical"
    escalation_target = "ops-team" if escalated else None

    # Build source reference
    source = {
        "receipt_hash": anomaly.get("receipt_hash", anomaly.get("payload_hash", "unknown")),
        "metric": anomaly.get("metric", classification),
    }

    receipt = emit_receipt("alert", {
        "tenant_id": tenant_id,
        "alert_id": alert_id,
        "anomaly_type": classification,
        "severity": severity,
        "source": source,
        "blast_radius": blast_radius,
        "escalated": escalated,
        "escalation_target": escalation_target,
    })

    # Critical alerts also emit anomaly_receipt with action=escalate
    if severity == "critical":
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": anomaly.get("metric", classification),
            "baseline": anomaly.get("baseline", 0.0),
            "delta": anomaly.get("delta", 0.0),
            "classification": classification,
            "action": "escalate",
        })

    return receipt


def _determine_blast_radius(classification: str, anomaly: dict) -> str:
    """Determine blast radius from classification and anomaly data.

    Args:
        classification: Anomaly classification
        anomaly: Full anomaly dict

    Returns:
        Blast radius string
    """
    # Check for explicit scope in anomaly
    if "scope" in anomaly:
        return anomaly["scope"]

    # Infer from classification
    if classification == "violation":
        return "system"
    elif classification == "degradation":
        return "service"
    elif classification == "drift":
        return "metric"
    elif classification == "anti_pattern":
        return "component"
    else:
        return "local"


def determine_severity(
    classification: str,
    confidence: float,
    drift_score: float | None = None
) -> str:
    """Determine alert severity from classification and metrics.

    Pure function. Logic:
    - violation with confidence >= 0.9 -> critical
    - violation with confidence < 0.9 -> error
    - degradation or drift with abs(drift_score) > 0.5 -> error
    - degradation or drift -> warning
    - deviation -> warning
    - anti_pattern -> info

    Args:
        classification: Anomaly classification
        confidence: Confidence score (0-1)
        drift_score: Optional drift score for drift/degradation

    Returns:
        Severity string (info, warning, error, critical)
    """
    if classification == "violation":
        if confidence >= 0.9:
            return "critical"
        return "error"

    if classification in ("degradation", "drift"):
        if drift_score is not None and abs(drift_score) > 0.5:
            return "error"
        return "warning"

    if classification == "deviation":
        return "warning"

    if classification == "anti_pattern":
        return "info"

    # Default for unknown classifications
    return "warning"


def should_escalate(alert: dict) -> bool:
    """Check if alert should be escalated.

    Pure function.

    Args:
        alert: Alert dict with severity field

    Returns:
        True if severity in [error, critical]
    """
    severity = alert.get("severity", "info")
    return severity in ("error", "critical")
