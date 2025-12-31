"""Tests for detect module - pattern detection with anomaly classification.

Coverage target: 80% minimum.
"""
import pytest

from proofpack.detect import (
    scan,
    match_pattern,
    build_pattern,
    classify_anomaly,
    classify_with_receipt,
    batch_classify,
    detect_drift,
    compute_baseline,
    is_drifting,
    emit_alert,
    determine_severity,
    should_escalate,
    track_resources,
    aggregate_resources,
    DETECT_SCHEMAS,
)


# ============================================================================
# scan.py tests
# ============================================================================

class TestScan:
    """Tests for scan module functions."""

    def test_scan_returns_list(self, sample_receipts_for_scan, sample_patterns):
        """Result is list."""
        result = scan(sample_receipts_for_scan, sample_patterns)
        assert isinstance(result, list)

    def test_scan_emits_receipt(self, sample_receipts_for_scan, sample_patterns, capsys):
        """scan_receipt with receipts_scanned, matches_found."""
        scan(sample_receipts_for_scan, sample_patterns)
        captured = capsys.readouterr()
        assert '"receipt_type": "scan"' in captured.out
        assert '"receipts_scanned": 100' in captured.out
        assert '"matches_found"' in captured.out

    def test_scan_finds_matches(self, sample_receipts_for_scan, sample_patterns):
        """Known pattern matches expected receipts."""
        result = scan(sample_receipts_for_scan, sample_patterns)
        # threshold_breach_latency matches latency_ms > 100
        # In our test data: latency_ms = 50 + (i % 100), so values 101-149 match (i=51-99)
        latency_matches = [m for m in result if m["pattern_id"] == "threshold_breach_latency"]
        assert len(latency_matches) > 0

    def test_scan_no_matches(self):
        """No matches when conditions don't match."""
        receipts = [{"field": "value1"}, {"field": "value2"}]
        patterns = [{"id": "test", "type": "test", "conditions": [
            {"field": "field", "operator": "eq", "value": "nonexistent"}
        ]}]
        result = scan(receipts, patterns)
        assert result == []

    def test_scan_slo_latency(self, sample_receipts_for_scan, sample_patterns, capsys):
        """elapsed_ms <= 100 for 100 receipts."""
        scan(sample_receipts_for_scan, sample_patterns)
        captured = capsys.readouterr()
        # Parse elapsed_ms from output
        import json
        for line in captured.out.strip().split('\n'):
            receipt = json.loads(line)
            if receipt.get("receipt_type") == "scan":
                assert receipt["elapsed_ms"] <= 100, f"Scan latency {receipt['elapsed_ms']}ms exceeds 100ms SLO"


class TestMatchPattern:
    """Tests for match_pattern function."""

    def test_match_pattern_eq(self):
        """Equality operator works."""
        receipt = {"status": "success", "value": 42}
        pattern = {"id": "test_eq", "type": "test", "conditions": [
            {"field": "status", "operator": "eq", "value": "success"}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is not None
        assert result["pattern_id"] == "test_eq"

    def test_match_pattern_gt(self):
        """Greater-than operator works."""
        receipt = {"latency": 150}
        pattern = {"id": "test_gt", "type": "test", "conditions": [
            {"field": "latency", "operator": "gt", "value": 100}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is not None

    def test_match_pattern_lt(self):
        """Less-than operator works."""
        receipt = {"latency": 50}
        pattern = {"id": "test_lt", "type": "test", "conditions": [
            {"field": "latency", "operator": "lt", "value": 100}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is not None

    def test_match_pattern_gte(self):
        """Greater-than-or-equal operator works."""
        receipt = {"latency": 100}
        pattern = {"id": "test_gte", "type": "test", "conditions": [
            {"field": "latency", "operator": "gte", "value": 100}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is not None

    def test_match_pattern_lte(self):
        """Less-than-or-equal operator works."""
        receipt = {"latency": 100}
        pattern = {"id": "test_lte", "type": "test", "conditions": [
            {"field": "latency", "operator": "lte", "value": 100}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is not None

    def test_match_pattern_ne(self):
        """Not-equal operator works."""
        receipt = {"status": "failure"}
        pattern = {"id": "test_ne", "type": "test", "conditions": [
            {"field": "status", "operator": "ne", "value": "success"}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is not None

    def test_match_pattern_contains(self):
        """Contains operator works."""
        receipt = {"message": "Error: connection failed"}
        pattern = {"id": "test_contains", "type": "test", "conditions": [
            {"field": "message", "operator": "contains", "value": "Error"}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is not None

    def test_match_pattern_regex(self):
        """Regex operator works."""
        receipt = {"code": "ERR-12345"}
        pattern = {"id": "test_regex", "type": "test", "conditions": [
            {"field": "code", "operator": "regex", "value": r"ERR-\d+"}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is not None

    def test_match_pattern_returns_none(self):
        """Non-matching returns None."""
        receipt = {"status": "success"}
        pattern = {"id": "test_none", "type": "test", "conditions": [
            {"field": "status", "operator": "eq", "value": "failure"}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is None

    def test_match_pattern_multiple_conditions(self):
        """Multiple conditions all must match."""
        receipt = {"status": "success", "latency": 150}
        pattern = {"id": "test_multi", "type": "test", "conditions": [
            {"field": "status", "operator": "eq", "value": "success"},
            {"field": "latency", "operator": "gt", "value": 100}
        ]}
        result = match_pattern(receipt, pattern)
        assert result is not None
        assert len(result["matched_conditions"]) == 2


class TestBuildPattern:
    """Tests for build_pattern function."""

    def test_build_pattern_valid(self):
        """Creates valid pattern dict."""
        pattern = build_pattern(
            "test_pattern",
            "threshold_breach",
            [{"field": "latency", "operator": "gt", "value": 100}]
        )
        assert pattern["id"] == "test_pattern"
        assert pattern["type"] == "threshold_breach"
        assert len(pattern["conditions"]) == 1

    def test_build_pattern_invalid_operator(self):
        """Invalid operator raises ValueError."""
        with pytest.raises(ValueError, match="Invalid operator"):
            build_pattern(
                "test_pattern",
                "test",
                [{"field": "latency", "operator": "invalid", "value": 100}]
            )


# ============================================================================
# classify.py tests
# ============================================================================

class TestClassify:
    """Tests for classify module functions."""

    def test_classify_drift(self):
        """trend_change pattern -> drift."""
        match = {"pattern_id": "trend_change_test", "pattern_type": "trend_change"}
        result = classify_anomaly(match)
        assert result == "drift"

    def test_classify_degradation(self):
        """performance_drop pattern -> degradation."""
        match = {"pattern_id": "performance_drop_test", "pattern_type": "performance_drop"}
        result = classify_anomaly(match)
        assert result == "degradation"

    def test_classify_violation(self):
        """threshold_breach pattern -> violation."""
        match = {"pattern_id": "threshold_breach_test", "pattern_type": "threshold_breach"}
        result = classify_anomaly(match)
        assert result == "violation"

    def test_classify_deviation(self):
        """unexpected_value pattern -> deviation."""
        match = {"pattern_id": "unexpected_value_test", "pattern_type": "unexpected_value"}
        result = classify_anomaly(match)
        assert result == "deviation"

    def test_classify_anti_pattern(self):
        """code_smell pattern -> anti_pattern."""
        match = {"pattern_id": "code_smell_test", "pattern_type": "code_smell"}
        result = classify_anomaly(match)
        assert result == "anti_pattern"

    def test_classify_with_receipt(self, capsys):
        """Emits classify_receipt."""
        match = {
            "pattern_id": "threshold_breach_test",
            "pattern_type": "threshold_breach",
            "receipt_hash": "abc123",
            "confidence": 0.95
        }
        result = classify_with_receipt(match)
        assert result["receipt_type"] == "classify"
        assert result["classification"] == "violation"
        captured = capsys.readouterr()
        assert '"receipt_type": "classify"' in captured.out

    def test_batch_classify(self):
        """Returns list of classifications."""
        matches = [
            {"pattern_id": "threshold_breach_1", "pattern_type": "threshold_breach"},
            {"pattern_id": "trend_change_1", "pattern_type": "trend_change"},
            {"pattern_id": "code_smell_1", "pattern_type": "code_smell"},
        ]
        result = batch_classify(matches)
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == "violation"
        assert result[1] == "drift"
        assert result[2] == "anti_pattern"


# ============================================================================
# drift.py tests
# ============================================================================

class TestDrift:
    """Tests for drift module functions."""

    def test_detect_drift_increasing(self, drifting_receipts, sample_baseline, capsys):
        """Values above baseline -> direction=increasing."""
        result = detect_drift(drifting_receipts, sample_baseline, "latency_ms")
        assert result["direction"] == "increasing"
        assert result["drift_score"] > 0

    def test_detect_drift_decreasing(self, sample_baseline, capsys):
        """Values below baseline -> direction=decreasing."""
        receipts = [{"latency_ms": 50} for _ in range(10)]  # Well below 75.0 baseline
        result = detect_drift(receipts, sample_baseline, "latency_ms")
        assert result["direction"] == "decreasing"
        assert result["drift_score"] < 0

    def test_detect_drift_stable(self, sample_baseline, capsys):
        """Values near baseline -> direction=stable."""
        receipts = [{"latency_ms": 75} for _ in range(10)]  # Exactly at baseline
        result = detect_drift(receipts, sample_baseline, "latency_ms")
        assert result["direction"] == "stable"
        assert abs(result["drift_score"]) <= 0.05

    def test_detect_drift_emits_receipt(self, drifting_receipts, sample_baseline, capsys):
        """drift_receipt has all required fields."""
        result = detect_drift(drifting_receipts, sample_baseline, "latency_ms")
        assert "receipt_type" in result
        assert result["receipt_type"] == "drift"
        assert "metric" in result
        assert "baseline_value" in result
        assert "current_value" in result
        assert "drift_score" in result
        assert "direction" in result
        assert "window_size" in result

    def test_compute_baseline(self, sample_receipts_for_scan):
        """Returns valid baseline dict."""
        result = compute_baseline(sample_receipts_for_scan, "latency_ms")
        assert "metric" in result
        assert result["metric"] == "latency_ms"
        assert "baseline_value" in result
        assert "sample_size" in result
        assert result["sample_size"] == 100
        assert "computed_at" in result

    def test_is_drifting_true(self):
        """drift_score > threshold -> True."""
        drift_receipt = {"drift_score": 0.15}
        assert is_drifting(drift_receipt, threshold=0.1) is True

    def test_is_drifting_false(self):
        """drift_score < threshold -> False."""
        drift_receipt = {"drift_score": 0.05}
        assert is_drifting(drift_receipt, threshold=0.1) is False

    def test_is_drifting_negative(self):
        """Negative drift_score also triggers if abs > threshold."""
        drift_receipt = {"drift_score": -0.15}
        assert is_drifting(drift_receipt, threshold=0.1) is True


# ============================================================================
# alert.py tests
# ============================================================================

class TestAlert:
    """Tests for alert module functions."""

    def test_emit_alert_returns_receipt(self, capsys):
        """alert_receipt with alert_id."""
        anomaly = {"classification": "violation", "metric": "latency"}
        result = emit_alert(anomaly, "warning")
        assert result["receipt_type"] == "alert"
        assert "alert_id" in result
        assert len(result["alert_id"]) == 36  # UUID format

    def test_emit_alert_critical_escalates(self, capsys):
        """severity=critical -> escalated=True."""
        anomaly = {"classification": "violation", "metric": "latency"}
        result = emit_alert(anomaly, "critical")
        assert result["escalated"] is True
        assert result["escalation_target"] == "ops-team"

    def test_emit_alert_warning_no_escalate(self, capsys):
        """severity=warning -> escalated=False."""
        anomaly = {"classification": "drift", "metric": "latency"}
        result = emit_alert(anomaly, "warning")
        assert result["escalated"] is False
        assert result["escalation_target"] is None

    def test_emit_alert_invalid_severity(self):
        """Invalid severity raises ValueError."""
        anomaly = {"classification": "violation"}
        with pytest.raises(ValueError, match="Invalid severity"):
            emit_alert(anomaly, "invalid_severity")

    def test_emit_alert_slo(self, capsys):
        """Completes within 60s (mock time)."""
        import time
        start = time.time()
        anomaly = {"classification": "violation", "metric": "latency"}
        emit_alert(anomaly, "warning")
        elapsed = time.time() - start
        assert elapsed < 60  # Should be nearly instantaneous

    def test_emit_alert_critical_emits_anomaly_receipt(self, capsys):
        """Critical alert emits anomaly_receipt with action=escalate."""
        anomaly = {"classification": "violation", "metric": "latency"}
        emit_alert(anomaly, "critical")
        captured = capsys.readouterr()
        assert '"action": "escalate"' in captured.out

    def test_determine_severity_violation_high_confidence(self):
        """violation + high confidence -> critical."""
        result = determine_severity("violation", 0.95)
        assert result == "critical"

    def test_determine_severity_violation_low_confidence(self):
        """violation + low confidence -> error."""
        result = determine_severity("violation", 0.7)
        assert result == "error"

    def test_determine_severity_drift_high_score(self):
        """drift with high score -> error."""
        result = determine_severity("drift", 0.8, drift_score=0.6)
        assert result == "error"

    def test_determine_severity_drift_low_score(self):
        """drift with low score -> warning."""
        result = determine_severity("drift", 0.8, drift_score=0.2)
        assert result == "warning"

    def test_determine_severity_degradation(self):
        """degradation -> warning (without high drift_score)."""
        result = determine_severity("degradation", 0.8)
        assert result == "warning"

    def test_determine_severity_deviation(self):
        """deviation -> warning."""
        result = determine_severity("deviation", 0.8)
        assert result == "warning"

    def test_determine_severity_anti_pattern(self):
        """anti_pattern -> info."""
        result = determine_severity("anti_pattern", 0.8)
        assert result == "info"

    def test_should_escalate_critical(self):
        """Returns True for critical."""
        alert = {"severity": "critical"}
        assert should_escalate(alert) is True

    def test_should_escalate_error(self):
        """Returns True for error."""
        alert = {"severity": "error"}
        assert should_escalate(alert) is True

    def test_should_escalate_warning(self):
        """Returns False for warning."""
        alert = {"severity": "warning"}
        assert should_escalate(alert) is False

    def test_should_escalate_info(self):
        """Returns False for info."""
        alert = {"severity": "info"}
        assert should_escalate(alert) is False


# ============================================================================
# resource.py tests
# ============================================================================

class TestResource:
    """Tests for resource module functions."""

    def test_track_resources_under_limit(self, capsys):
        """utilization < 0.9 -> threshold_exceeded=False."""
        result = track_resources("tokens", 800, 1000, "1h")
        assert result["utilization"] == 0.8
        assert result["threshold_exceeded"] is False

    def test_track_resources_over_limit(self, capsys):
        """utilization > 0.9 -> threshold_exceeded=True."""
        result = track_resources("tokens", 950, 1000, "1h")
        assert result["utilization"] == 0.95
        assert result["threshold_exceeded"] is True

    def test_track_resources_emits_receipt(self, capsys):
        """resource_receipt has all fields."""
        result = track_resources("compute", 75, 100, "24h")
        assert result["receipt_type"] == "resource"
        assert "resource_type" in result
        assert "consumed" in result
        assert "limit" in result
        assert "utilization" in result
        assert "period" in result
        assert "threshold_exceeded" in result

    def test_track_resources_tokens_alert(self, capsys):
        """Tokens over threshold emits anomaly_receipt."""
        track_resources("tokens", 950, 1000, "1h")
        captured = capsys.readouterr()
        assert '"receipt_type": "anomaly"' in captured.out
        assert '"action": "alert"' in captured.out

    def test_track_resources_cost_alert(self, capsys):
        """Cost over threshold emits anomaly_receipt."""
        track_resources("cost", 95, 100, "24h")
        captured = capsys.readouterr()
        assert '"receipt_type": "anomaly"' in captured.out

    def test_track_resources_memory_no_alert(self, capsys):
        """Memory over threshold does NOT emit anomaly_receipt (only tokens/cost)."""
        track_resources("memory", 95, 100, "1h")
        captured = capsys.readouterr()
        # Should only have resource receipt, not anomaly
        lines = [line for line in captured.out.strip().split('\n') if line]
        assert len(lines) == 1
        assert '"receipt_type": "resource"' in lines[0]

    def test_aggregate_resources(self):
        """Groups and sums correctly."""
        receipts = [
            {"resource_type": "tokens", "consumed": 100, "utilization": 0.5, "threshold_exceeded": False},
            {"resource_type": "tokens", "consumed": 200, "utilization": 0.7, "threshold_exceeded": False},
            {"resource_type": "tokens", "consumed": 300, "utilization": 0.95, "threshold_exceeded": True},
            {"resource_type": "compute", "consumed": 50, "utilization": 0.25, "threshold_exceeded": False},
        ]
        result = aggregate_resources(receipts)

        assert "tokens" in result
        assert result["tokens"]["total_consumed"] == 600
        assert abs(result["tokens"]["avg_utilization"] - 0.7166666666666667) < 0.01
        assert result["tokens"]["periods_exceeded"] == 1

        assert "compute" in result
        assert result["compute"]["total_consumed"] == 50
        assert result["compute"]["avg_utilization"] == 0.25
        assert result["compute"]["periods_exceeded"] == 0


# ============================================================================
# schemas.py tests
# ============================================================================

class TestSchemas:
    """Tests for schema definitions."""

    def test_detect_schemas_has_all_types(self):
        """DETECT_SCHEMAS has all required receipt types."""
        expected = {"scan", "classify", "drift", "alert", "resource"}
        assert set(DETECT_SCHEMAS.keys()) == expected

    def test_scan_schema_fields(self):
        """scan schema has required fields."""
        schema = DETECT_SCHEMAS["scan"]
        required = ["receipt_type", "ts", "tenant_id", "payload_hash",
                   "receipts_scanned", "patterns_checked", "matches_found",
                   "matches", "elapsed_ms"]
        for field in required:
            assert field in schema

    def test_classify_schema_fields(self):
        """classify schema has required fields."""
        schema = DETECT_SCHEMAS["classify"]
        required = ["receipt_type", "ts", "tenant_id", "payload_hash",
                   "match_id", "classification", "confidence", "evidence"]
        for field in required:
            assert field in schema

    def test_drift_schema_fields(self):
        """drift schema has required fields."""
        schema = DETECT_SCHEMAS["drift"]
        required = ["receipt_type", "ts", "tenant_id", "payload_hash",
                   "metric", "baseline_value", "current_value", "drift_score",
                   "direction", "window_size"]
        for field in required:
            assert field in schema

    def test_alert_schema_fields(self):
        """alert schema has required fields."""
        schema = DETECT_SCHEMAS["alert"]
        required = ["receipt_type", "ts", "tenant_id", "payload_hash",
                   "alert_id", "anomaly_type", "severity", "source",
                   "blast_radius", "escalated", "escalation_target"]
        for field in required:
            assert field in schema

    def test_resource_schema_fields(self):
        """resource schema has required fields."""
        schema = DETECT_SCHEMAS["resource"]
        required = ["receipt_type", "ts", "tenant_id", "payload_hash",
                   "resource_type", "consumed", "limit", "utilization",
                   "period", "threshold_exceeded"]
        for field in required:
            assert field in schema


# ============================================================================
# Integration tests
# ============================================================================

class TestIntegration:
    """Integration tests for detect module."""

    def test_scan_to_classify_pipeline(self, sample_receipts_for_scan, sample_patterns, capsys):
        """Full pipeline from scan to classification."""
        # Scan for matches
        matches = scan(sample_receipts_for_scan, sample_patterns)

        # Classify each match
        if matches:
            classifications = batch_classify(matches)
            assert len(classifications) == len(matches)

            # Classify first match with receipt
            result = classify_with_receipt(matches[0])
            assert result["receipt_type"] == "classify"

    def test_drift_to_alert_pipeline(self, drifting_receipts, sample_baseline, capsys):
        """Full pipeline from drift detection to alert."""
        # Detect drift
        drift_result = detect_drift(drifting_receipts, sample_baseline, "latency_ms")

        # Check if drifting
        if is_drifting(drift_result):
            # Determine severity
            severity = determine_severity(
                "drift",
                confidence=0.9,
                drift_score=drift_result["drift_score"]
            )

            # Create anomaly dict for alert (enrich drift result with classification)
            anomaly = {
                **drift_result,
                "classification": "drift",
            }

            # Emit alert
            alert = emit_alert(anomaly, severity)
            assert alert["receipt_type"] == "alert"
            assert alert["anomaly_type"] == "drift"

    def test_resource_tracking_with_alert(self, capsys):
        """Resource tracking triggers alert when over threshold."""
        # Track resources near limit
        result = track_resources("tokens", 9500, 10000, "1h")

        # Check for alert condition
        if result["threshold_exceeded"]:
            severity = determine_severity("violation", confidence=1.0)
            alert = emit_alert(result, severity)
            assert should_escalate(alert)
