"""Detect subpackage for pattern detection with anomaly classification.

Implements HUNTER agent pattern from QED v10.
Provides scanning, classification, drift detection, alerting, and resource tracking.
"""
from .scan import scan, match_pattern, build_pattern
from .classify import classify_anomaly, classify_with_receipt, batch_classify
from .drift import detect_drift, compute_baseline, is_drifting
from .alert import emit_alert, determine_severity, should_escalate
from .resource import track_resources, aggregate_resources
from .schemas import DETECT_SCHEMAS

__all__ = [
    # scan
    "scan",
    "match_pattern",
    "build_pattern",
    # classify
    "classify_anomaly",
    "classify_with_receipt",
    "batch_classify",
    # drift
    "detect_drift",
    "compute_baseline",
    "is_drifting",
    # alert
    "emit_alert",
    "determine_severity",
    "should_escalate",
    # resource
    "track_resources",
    "aggregate_resources",
    # schemas
    "DETECT_SCHEMAS",
]
