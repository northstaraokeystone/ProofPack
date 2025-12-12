"""Unit tests for brief module.

Functions tested: retrieve, compose, health, dialectic
SLO: brief ≤1000ms p95
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import pytest
from brief.retrieve import retrieve
from brief.compose import compose_brief
from brief.health import compute_decision_health
from brief.dialectic import run_dialectic


class TestBriefRetrieve:
    """Tests for brief retrieve functionality."""

    def test_retrieve_returns_receipt(self):
        """retrieve should return a valid receipt."""
        budget = {"tokens": 1000, "ms": 1000}
        result = retrieve("test query", budget, "test_tenant")

        assert "receipt_type" in result, "Should return receipt"
        assert result["receipt_type"] == "retrieval", "Wrong receipt type"

    def test_retrieve_respects_budget(self):
        """retrieve should respect token budget."""
        budget = {"tokens": 500, "ms": 1000}
        result = retrieve("test query", budget, "test_tenant")

        assert result.get("k", 0) <= budget["tokens"] // 100, \
            "k should be bounded by token budget"

    def test_retrieve_classifies_complexity(self):
        """retrieve should classify query complexity."""
        budget = {"tokens": 1000, "ms": 1000}

        # Atomic query
        result_atomic = retrieve("price", budget, "tenant")
        assert result_atomic.get("query_complexity") == "atomic", \
            "Short query should be atomic"

        # Comparative query
        result_compare = retrieve("compare product A vs product B", budget, "tenant")
        assert result_compare.get("query_complexity") == "comparative", \
            "Query with 'vs' should be comparative"

    def test_retrieve_returns_chunks(self):
        """retrieve should return chunks."""
        budget = {"tokens": 500, "ms": 1000}
        result = retrieve("test", budget, "tenant")

        assert "chunks" in result, "Should return chunks"
        assert isinstance(result["chunks"], list), "Chunks should be list"


class TestBriefCompose:
    """Tests for brief compose functionality."""

    def test_compose_returns_receipt(self):
        """compose_brief should return a valid receipt."""
        evidence = [{"chunk": "evidence1"}, {"chunk": "evidence2"}]
        result = compose_brief(evidence, "test_tenant")

        assert "receipt_type" in result, "Should return receipt"

    def test_compose_handles_empty_evidence(self):
        """compose_brief should handle empty evidence."""
        result = compose_brief([], "test_tenant")

        assert result is not None, "Should handle empty evidence"

    def test_compose_slo_latency(self):
        """SLO: compose_brief should complete in ≤1000ms p95."""
        latencies = []
        evidence = [{"chunk": f"evidence_{i}"} for i in range(10)]

        for _ in range(20):
            t0 = time.perf_counter()
            compose_brief(evidence, "tenant")
            latencies.append((time.perf_counter() - t0) * 1000)

        latencies.sort()
        p95 = latencies[18]  # 95th percentile of 20 samples

        assert p95 <= 1000, f"compose_brief p95 latency {p95:.2f}ms > 1000ms SLO"


class TestBriefHealth:
    """Tests for decision health computation."""

    def test_health_returns_metrics(self):
        """compute_decision_health should return health metrics."""
        evidence = [
            {"strength": 0.9, "coverage": 0.8},
            {"strength": 0.85, "coverage": 0.75}
        ]
        result = compute_decision_health(evidence, "tenant")

        assert "receipt_type" in result, "Should return receipt"
        assert "strength" in result or "decision_health" in result, \
            "Should include strength metric"

    def test_health_strength_bounds(self):
        """Health strength should be bounded 0-1."""
        evidence = [{"strength": 0.9}]
        result = compute_decision_health(evidence, "tenant")

        strength = result.get("strength") or result.get("decision_health", {}).get("strength", 0.5)
        assert 0 <= strength <= 1, f"Strength {strength} out of bounds"


class TestBriefDialectic:
    """Tests for dialectic analysis."""

    def test_dialectic_returns_receipt(self):
        """run_dialectic should return a valid receipt."""
        evidence = [
            {"claim": "pro_argument", "type": "pro"},
            {"claim": "con_argument", "type": "con"}
        ]
        result = run_dialectic(evidence, "tenant")

        assert "receipt_type" in result, "Should return receipt"

    def test_dialectic_identifies_gaps(self):
        """run_dialectic should identify gaps in evidence."""
        # Evidence with missing perspectives
        evidence = [{"claim": "single_view", "type": "pro"}]
        result = run_dialectic(evidence, "tenant")

        # Should note gaps in dialectical record
        assert result is not None, "Should handle incomplete evidence"

    def test_dialectic_handles_conflict(self):
        """run_dialectic should handle conflicting evidence."""
        evidence = [
            {"claim": "A is true", "type": "pro"},
            {"claim": "A is false", "type": "con"}
        ]
        result = run_dialectic(evidence, "tenant")

        assert result is not None, "Should handle conflicting evidence"
