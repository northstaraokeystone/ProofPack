"""Confidence evaluation for CRAG flow.

Scores synthesis confidence and classifies as:
    - CORRECT: High confidence, use as-is
    - AMBIGUOUS: Medium confidence, augment with web
    - INCORRECT: Low confidence, reformulate and retry

Based on the Corrective RAG paper (arXiv:2401.15884v2).
"""
from enum import Enum
from dataclasses import dataclass
from typing import Tuple

from core.receipt import emit_receipt


class Classification(Enum):
    """Confidence classification for CRAG."""
    CORRECT = "CORRECT"       # >0.8 - Use synthesis as-is
    AMBIGUOUS = "AMBIGUOUS"   # 0.5-0.8 - Augment with web
    INCORRECT = "INCORRECT"   # <0.5 - Reformulate query


# Thresholds for classification
CORRECT_THRESHOLD = 0.8
AMBIGUOUS_THRESHOLD = 0.5


@dataclass
class EvaluationResult:
    """Result of confidence evaluation."""
    classification: Classification
    confidence: float
    factors: dict
    recommendation: str


def score(
    synthesis: dict,
    query: str = "",
    tenant_id: str = "default",
) -> Tuple[Classification, float]:
    """Score synthesis confidence.

    Evaluates multiple factors:
    - Evidence count and coverage
    - Source diversity
    - Internal consistency
    - Query relevance (if query provided)

    Args:
        synthesis: Brief or synthesis receipt
        query: Original query (optional, for relevance check)
        tenant_id: Tenant identifier

    Returns:
        Tuple of (Classification, confidence_score)
    """
    factors = {}

    # Factor 1: Evidence strength
    evidence = synthesis.get("supporting_evidence", [])
    if evidence:
        avg_confidence = sum(e.get("confidence", 0.5) for e in evidence) / len(evidence)
        factors["evidence_strength"] = avg_confidence
    else:
        factors["evidence_strength"] = 0.0

    # Factor 2: Evidence coverage
    evidence_count = synthesis.get("evidence_count", len(evidence))
    coverage = min(evidence_count / 10.0, 1.0)  # Normalize to [0, 1]
    factors["coverage"] = coverage

    # Factor 3: Health metrics (if available)
    strength = synthesis.get("strength", factors["evidence_strength"])
    health_coverage = synthesis.get("coverage", coverage)
    efficiency = synthesis.get("efficiency", 0.7)
    factors["health_strength"] = strength
    factors["health_coverage"] = health_coverage
    factors["health_efficiency"] = efficiency

    # Factor 4: Resolution status (from dialectic)
    resolution = synthesis.get("resolution_status", "open")
    if resolution == "resolved":
        factors["resolution"] = 0.9
    elif resolution == "one_sided":
        factors["resolution"] = 0.7
    else:
        factors["resolution"] = 0.5

    # Factor 5: Gap penalty
    gaps = synthesis.get("gaps", [])
    gap_penalty = len(gaps) * 0.1
    factors["gap_penalty"] = gap_penalty

    # Factor 6: Query relevance (basic check)
    if query:
        summary = synthesis.get("executive_summary", "")
        if summary:
            query_words = set(query.lower().split())
            summary_words = set(summary.lower().split())
            overlap = len(query_words & summary_words) / max(len(query_words), 1)
            factors["query_relevance"] = max(overlap, 0.5)  # Minimum 0.5 if summary exists
        else:
            factors["query_relevance"] = 0.7  # Default if no summary
    else:
        factors["query_relevance"] = 0.7  # Default if no query

    # Compute weighted confidence
    weights = {
        "evidence_strength": 0.25,
        "coverage": 0.15,
        "health_strength": 0.20,
        "health_coverage": 0.10,
        "resolution": 0.15,
        "query_relevance": 0.15,
    }

    confidence = 0.0
    for factor, weight in weights.items():
        confidence += factors.get(factor, 0.5) * weight

    # Apply gap penalty
    confidence = max(0.0, confidence - factors["gap_penalty"])

    # Classify
    if confidence >= CORRECT_THRESHOLD:
        classification = Classification.CORRECT
        recommendation = "Use synthesis as-is"
    elif confidence >= AMBIGUOUS_THRESHOLD:
        classification = Classification.AMBIGUOUS
        recommendation = "Augment with web search"
    else:
        classification = Classification.INCORRECT
        recommendation = "Reformulate query and retry"

    # Emit evaluation receipt
    emit_receipt("fallback_evaluate", {
        "classification": classification.value,
        "confidence": round(confidence, 3),
        "factors": factors,
        "recommendation": recommendation,
        "tenant_id": tenant_id,
    })

    return classification, confidence


def evaluate_with_details(
    synthesis: dict,
    query: str = "",
    tenant_id: str = "default",
) -> EvaluationResult:
    """Evaluate with full details.

    Args:
        synthesis: Brief or synthesis receipt
        query: Original query (optional)
        tenant_id: Tenant identifier

    Returns:
        EvaluationResult with all factors
    """
    classification, confidence = score(synthesis, query, tenant_id)

    # Recompute factors for detailed result
    factors = {}
    evidence = synthesis.get("supporting_evidence", [])

    if evidence:
        factors["evidence_count"] = len(evidence)
        factors["evidence_strength"] = sum(e.get("confidence", 0.5) for e in evidence) / len(evidence)
    else:
        factors["evidence_count"] = 0
        factors["evidence_strength"] = 0.0

    factors["coverage"] = synthesis.get("coverage", 0.0)
    factors["strength"] = synthesis.get("strength", 0.0)
    factors["gaps"] = synthesis.get("gaps", [])
    factors["resolution_status"] = synthesis.get("resolution_status", "unknown")

    if classification == Classification.CORRECT:
        recommendation = "Synthesis is high-confidence. Use as-is."
    elif classification == Classification.AMBIGUOUS:
        recommendation = "Medium confidence. Augment with web search for additional context."
    else:
        recommendation = "Low confidence. Reformulate query, retry internal search, then web fallback."

    return EvaluationResult(
        classification=classification,
        confidence=confidence,
        factors=factors,
        recommendation=recommendation,
    )


def should_fallback(
    synthesis: dict,
    query: str = "",
    tenant_id: str = "default",
) -> bool:
    """Quick check if fallback is needed.

    Args:
        synthesis: Brief or synthesis receipt
        query: Original query (optional)
        tenant_id: Tenant identifier

    Returns:
        True if web fallback should be triggered
    """
    classification, _ = score(synthesis, query, tenant_id)
    return classification != Classification.CORRECT


def get_correction_action(classification: Classification) -> str:
    """Get the recommended correction action.

    Args:
        classification: Evaluation classification

    Returns:
        Action string: "none", "augment", or "reformulate"
    """
    if classification == Classification.CORRECT:
        return "none"
    elif classification == Classification.AMBIGUOUS:
        return "augment"
    else:
        return "reformulate"
