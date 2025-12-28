"""Merge internal and external results for CRAG.

Merge strategies:
    - AUGMENT: Add web results to internal synthesis
    - REPLACE: Use web results instead of internal
    - INTERLEAVE: Mix internal and web results by relevance
"""
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from proofpack.core.receipt import emit_receipt, dual_hash

from .web import WebResult


class MergeStrategy(Enum):
    """Strategy for merging internal and web results."""
    AUGMENT = "AUGMENT"       # Add web to internal
    REPLACE = "REPLACE"       # Replace internal with web
    INTERLEAVE = "INTERLEAVE" # Mix by relevance


@dataclass
class MergeResult:
    """Result of merging internal and web content."""
    merged_content: str
    internal_receipt_ids: List[str]
    web_sources: List[str]
    strategy: MergeStrategy
    confidence_before: float
    confidence_after: float
    elapsed_ms: float


def combine(
    internal_synthesis: dict,
    web_results: List[WebResult],
    strategy: MergeStrategy = MergeStrategy.AUGMENT,
    confidence_before: float = 0.5,
    tenant_id: str = "default",
) -> MergeResult:
    """Combine internal synthesis with web results.

    Args:
        internal_synthesis: Brief or synthesis receipt
        web_results: List of web search results
        strategy: Merge strategy to use
        confidence_before: Confidence score before merge
        tenant_id: Tenant identifier

    Returns:
        MergeResult with combined content
    """
    start_time = time.perf_counter()

    if strategy == MergeStrategy.AUGMENT:
        result = _merge_augment(internal_synthesis, web_results)
    elif strategy == MergeStrategy.REPLACE:
        result = _merge_replace(internal_synthesis, web_results)
    else:  # INTERLEAVE
        result = _merge_interleave(internal_synthesis, web_results)

    # Calculate new confidence (heuristic)
    web_boost = min(len(web_results) * 0.05, 0.2)  # Up to 0.2 boost from web
    confidence_after = min(1.0, confidence_before + web_boost)

    # Collect IDs
    internal_ids = []
    if "payload_hash" in internal_synthesis:
        internal_ids.append(internal_synthesis["payload_hash"])

    for evidence in internal_synthesis.get("supporting_evidence", []):
        if "chunk_id" in evidence:
            internal_ids.append(evidence["chunk_id"])

    web_sources = [wr.url for wr in web_results]

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    merge_result = MergeResult(
        merged_content=result,
        internal_receipt_ids=internal_ids,
        web_sources=web_sources,
        strategy=strategy,
        confidence_before=confidence_before,
        confidence_after=confidence_after,
        elapsed_ms=elapsed_ms,
    )

    # Emit merge receipt
    emit_receipt("merge", {
        "internal_receipt_ids": internal_ids,
        "web_retrieval_id": dual_hash(str(web_sources)),
        "merge_strategy": strategy.value,
        "confidence_before": confidence_before,
        "confidence_after": confidence_after,
        "sources_count": len(web_sources),
        "content_length": len(result),
        "tenant_id": tenant_id,
    })

    return merge_result


def _merge_augment(
    internal: dict,
    web_results: List[WebResult],
) -> str:
    """Augment internal synthesis with web context.

    Adds web snippets as additional supporting evidence.
    """
    parts = []

    # Start with internal summary
    summary = internal.get("executive_summary", "")
    if summary:
        parts.append("## Internal Analysis")
        parts.append(summary)

    # Add internal evidence
    evidence = internal.get("supporting_evidence", [])
    if evidence:
        parts.append("")
        parts.append("### Supporting Evidence")
        for e in evidence[:5]:
            chunk_id = e.get("chunk_id", "unknown")
            confidence = e.get("confidence", 0.0)
            parts.append(f"- [{chunk_id}] (confidence: {confidence:.2f})")

    # Add web augmentation
    if web_results:
        parts.append("")
        parts.append("## Web Sources")
        for i, wr in enumerate(web_results[:5], 1):
            parts.append(f"### Source {i}: {wr.title}")
            parts.append(f"URL: {wr.url}")
            parts.append(f"Relevance: {wr.relevance_score:.2f}")
            parts.append("")
            parts.append(wr.snippet[:500] if len(wr.snippet) > 500 else wr.snippet)
            parts.append("")

    return "\n".join(parts)


def _merge_replace(
    internal: dict,
    web_results: List[WebResult],
) -> str:
    """Replace internal with web results.

    Used when internal confidence is very low.
    """
    parts = []

    parts.append("## Web Search Results")
    parts.append("(Internal results replaced due to low confidence)")
    parts.append("")

    for i, wr in enumerate(web_results[:5], 1):
        parts.append(f"### [{i}] {wr.title}")
        parts.append(f"Source: {wr.url}")
        parts.append(f"Relevance: {wr.relevance_score:.2f}")
        parts.append("")
        parts.append(wr.snippet)
        if wr.content:
            parts.append("")
            parts.append("Full content excerpt:")
            parts.append(wr.content[:1000])
        parts.append("")

    return "\n".join(parts)


def _merge_interleave(
    internal: dict,
    web_results: List[WebResult],
) -> str:
    """Interleave internal and web by relevance.

    Alternates between internal evidence and web results,
    sorted by confidence/relevance.
    """
    parts = []
    parts.append("## Combined Analysis (Interleaved)")
    parts.append("")

    # Build ranked list
    items = []

    # Add internal evidence
    for e in internal.get("supporting_evidence", []):
        items.append({
            "type": "internal",
            "score": e.get("confidence", 0.5),
            "content": f"[Internal] {e.get('chunk_id', 'evidence')}",
        })

    # Add web results
    for wr in web_results:
        items.append({
            "type": "web",
            "score": wr.relevance_score,
            "content": f"[Web] {wr.title}\n{wr.snippet[:200]}",
            "url": wr.url,
        })

    # Sort by score descending
    items.sort(key=lambda x: x["score"], reverse=True)

    # Interleave
    for i, item in enumerate(items[:10], 1):
        score = item["score"]
        parts.append(f"### {i}. [{item['type'].upper()}] (score: {score:.2f})")
        parts.append(item["content"])
        if "url" in item:
            parts.append(f"Source: {item['url']}")
        parts.append("")

    return "\n".join(parts)


def select_strategy(
    classification: str,
    internal_confidence: float,
    web_result_count: int,
) -> MergeStrategy:
    """Select appropriate merge strategy based on context.

    Args:
        classification: CORRECT, AMBIGUOUS, or INCORRECT
        internal_confidence: Internal synthesis confidence
        web_result_count: Number of web results available

    Returns:
        Recommended MergeStrategy
    """
    if classification == "CORRECT":
        # High confidence - minimal augmentation
        return MergeStrategy.AUGMENT

    if classification == "INCORRECT" and internal_confidence < 0.3:
        # Very low confidence - replace with web
        return MergeStrategy.REPLACE

    if web_result_count >= 3:
        # Good web coverage - interleave
        return MergeStrategy.INTERLEAVE

    # Default to augment
    return MergeStrategy.AUGMENT


def combine_with_auto_strategy(
    internal_synthesis: dict,
    web_results: List[WebResult],
    classification: str,
    confidence_before: float,
    tenant_id: str = "default",
) -> MergeResult:
    """Combine with automatically selected strategy.

    Args:
        internal_synthesis: Brief or synthesis receipt
        web_results: List of web search results
        classification: Evaluation classification
        confidence_before: Confidence before merge
        tenant_id: Tenant identifier

    Returns:
        MergeResult with combined content
    """
    strategy = select_strategy(
        classification,
        confidence_before,
        len(web_results),
    )

    return combine(
        internal_synthesis,
        web_results,
        strategy,
        confidence_before,
        tenant_id,
    )
