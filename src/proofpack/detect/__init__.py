"""Detect module: pattern finding with anomaly classification."""
from proofpack.core.receipt import StopRule, dual_hash, emit_receipt

from .anomaly import ACTIONS, CLASSIFICATIONS, classify, emit_anomaly
from .core import scan
from .drift import SEVERITIES, alert
from .resource import track_resources

# Schema definitions for all receipt types
SCAN_SCHEMA = {
    "receipt_type": "scan",
    "stream_size": "int",
    "patterns_found": [{"pattern_id": "str", "count": "int", "signature": "str"}],
    "confidence_scores": {"pattern_id": "float 0-1"},
    "baseline_metrics": "dict",
    "scan_duration_ms": "float"
}

ANOMALY_SCHEMA = {
    "receipt_type": "anomaly",
    "metric": "str",
    "baseline": "float",
    "delta": "float",
    "classification": "drift|degradation|violation|deviation|anti_pattern",
    "action": "alert|escalate|halt|auto_fix"
}

ALERT_SCHEMA = {
    "receipt_type": "alert",
    "anomaly_id": "str",
    "severity": "low|medium|high|critical",
    "blast_radius": ["str"],
    "recommended_action": "str",
    "escalation_required": "bool"
}

RESOURCE_SCHEMA = {
    "receipt_type": "resource",
    "compute_used": "float",
    "memory_used": "float",
    "io_operations": "int",
    "cost": "float",
    "cycle_duration_ms": "int",
    "timestamp": "ISO8601"
}

RECEIPT_SCHEMA = {
    "scan_receipt": SCAN_SCHEMA,
    "anomaly_receipt": ANOMALY_SCHEMA,
    "alert_receipt": ALERT_SCHEMA,
    "resource_receipt": RESOURCE_SCHEMA
}

__all__ = [
    # Core imports from ledger
    "emit_receipt",
    "dual_hash",
    "StopRule",
    # Functions
    "scan",
    "classify",
    "emit_anomaly",
    "alert",
    "track_resources",
    # Constants
    "CLASSIFICATIONS",
    "ACTIONS",
    "SEVERITIES",
    # Schemas
    "SCAN_SCHEMA",
    "ANOMALY_SCHEMA",
    "ALERT_SCHEMA",
    "RESOURCE_SCHEMA",
    "RECEIPT_SCHEMA"
]
