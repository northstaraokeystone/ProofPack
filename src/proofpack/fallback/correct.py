"""Correction strategies for CRAG flow.

Strategies:
    - reformulate: Rephrase query for better results
    - decompose: Break complex query into sub-queries
    - web_search: Fetch external sources
"""
import time
from dataclasses import dataclass
from typing import List

from proofpack.core.receipt import emit_receipt

from .web import search, WebResult


@dataclass
class CorrectionResult:
    """Result of a correction attempt."""
    strategy: str
    original_query: str
    corrected_queries: List[str]
    web_results: List[WebResult]
    elapsed_ms: float


def reformulate(
    query: str,
    context: str = "",
    tenant_id: str = "default",
) -> List[str]:
    """Reformulate query for better retrieval.

    Strategies:
    - Remove ambiguous terms
    - Add specificity
    - Create alternative phrasings

    Args:
        query: Original query
        context: Optional context for better reformulation
        tenant_id: Tenant identifier

    Returns:
        List of reformulated queries
    """
    reformulations = []

    # Strategy 1: Simplify - remove question words
    simplified = query.lower()
    for word in ["what", "how", "why", "when", "where", "who", "which"]:
        simplified = simplified.replace(word, "").strip()
    if simplified and simplified != query.lower():
        reformulations.append(simplified)

    # Strategy 2: Add context keywords
    if context:
        context_words = [w for w in context.split()[:3] if len(w) > 3]
        if context_words:
            reformulations.append(f"{query} {' '.join(context_words)}")

    # Strategy 3: Synonym expansion (basic)
    synonyms = {
        "error": ["failure", "bug", "issue"],
        "fix": ["resolve", "repair", "correct"],
        "find": ["locate", "identify", "detect"],
        "cause": ["reason", "source", "origin"],
    }

    words = query.lower().split()
    for i, word in enumerate(words):
        if word in synonyms:
            for syn in synonyms[word][:1]:  # Take first synonym
                new_words = words.copy()
                new_words[i] = syn
                reformulations.append(" ".join(new_words))

    # Always include original
    if query not in reformulations:
        reformulations.insert(0, query)

    emit_receipt("fallback_reformulate", {
        "original_query": query,
        "reformulations": reformulations,
        "context_used": bool(context),
        "tenant_id": tenant_id,
    })

    return reformulations[:5]  # Max 5 reformulations


def decompose(
    query: str,
    tenant_id: str = "default",
) -> List[str]:
    """Decompose complex query into sub-queries.

    Breaks down compound questions into atomic parts.

    Args:
        query: Complex query
        tenant_id: Tenant identifier

    Returns:
        List of simpler sub-queries
    """
    sub_queries = []

    # Split on conjunctions
    conjunctions = [" and ", " or ", " but ", ", ", " also ", " as well as "]
    parts = [query]

    for conj in conjunctions:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(conj))
        parts = new_parts

    # Clean up parts
    for part in parts:
        cleaned = part.strip()
        if cleaned and len(cleaned) > 10:  # Minimum meaningful length
            sub_queries.append(cleaned)

    # If no decomposition happened, try question decomposition
    if len(sub_queries) <= 1:
        # Check for multi-part questions
        if "?" in query:
            questions = query.split("?")
            for q in questions:
                q = q.strip()
                if q:
                    sub_queries.append(q + "?")
        else:
            sub_queries = [query]

    emit_receipt("fallback_decompose", {
        "original_query": query,
        "sub_queries": sub_queries,
        "count": len(sub_queries),
        "tenant_id": tenant_id,
    })

    return sub_queries


def with_web(
    query: str,
    max_results: int = 5,
    timeout_ms: int = 2000,
    provider: str = "tavily",
    tenant_id: str = "default",
) -> CorrectionResult:
    """Correct with web search.

    Fetches external sources to augment internal results.

    Args:
        query: Search query
        max_results: Maximum results to fetch
        timeout_ms: Timeout in milliseconds
        provider: Web search provider
        tenant_id: Tenant identifier

    Returns:
        CorrectionResult with web search results
    """
    start_time = time.perf_counter()

    # Perform web search
    web_results = search(
        query=query,
        max_results=max_results,
        timeout_ms=timeout_ms,
        provider=provider,
        tenant_id=tenant_id,
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    result = CorrectionResult(
        strategy="web_search",
        original_query=query,
        corrected_queries=[query],
        web_results=web_results,
        elapsed_ms=elapsed_ms,
    )

    emit_receipt("fallback_correct", {
        "strategy": "web_search",
        "query": query,
        "results_count": len(web_results),
        "elapsed_ms": elapsed_ms,
        "tenant_id": tenant_id,
    })

    return result


def correct_with_reformulation(
    query: str,
    context: str = "",
    max_results: int = 5,
    timeout_ms: int = 2000,
    provider: str = "tavily",
    tenant_id: str = "default",
) -> CorrectionResult:
    """Correct with reformulation + web search.

    First reformulates the query, then searches for each variant.

    Args:
        query: Original query
        context: Optional context
        max_results: Maximum results per query
        timeout_ms: Timeout in milliseconds
        provider: Web search provider
        tenant_id: Tenant identifier

    Returns:
        CorrectionResult with combined web results
    """
    start_time = time.perf_counter()

    # Get reformulations
    reformulations = reformulate(query, context, tenant_id)

    # Search each reformulation
    all_results = []
    seen_urls = set()

    for reformulated in reformulations[:3]:  # Limit to 3 reformulations
        results = search(
            query=reformulated,
            max_results=max_results,
            timeout_ms=timeout_ms,
            provider=provider,
            tenant_id=tenant_id,
        )

        # Deduplicate by URL
        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                all_results.append(result)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return CorrectionResult(
        strategy="reformulate_and_search",
        original_query=query,
        corrected_queries=reformulations[:3],
        web_results=all_results[:max_results * 2],  # Limit total
        elapsed_ms=elapsed_ms,
    )


def correct_with_decomposition(
    query: str,
    max_results: int = 5,
    timeout_ms: int = 2000,
    provider: str = "tavily",
    tenant_id: str = "default",
) -> CorrectionResult:
    """Correct with query decomposition + web search.

    Decomposes complex query and searches each sub-query.

    Args:
        query: Complex query
        max_results: Maximum results per sub-query
        timeout_ms: Timeout in milliseconds
        provider: Web search provider
        tenant_id: Tenant identifier

    Returns:
        CorrectionResult with combined web results
    """
    start_time = time.perf_counter()

    # Decompose query
    sub_queries = decompose(query, tenant_id)

    # Search each sub-query
    all_results = []
    seen_urls = set()

    for sub_query in sub_queries[:5]:  # Limit to 5 sub-queries
        results = search(
            query=sub_query,
            max_results=max_results // len(sub_queries) or 2,
            timeout_ms=timeout_ms,
            provider=provider,
            tenant_id=tenant_id,
        )

        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                all_results.append(result)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return CorrectionResult(
        strategy="decompose_and_search",
        original_query=query,
        corrected_queries=sub_queries,
        web_results=all_results[:max_results * 2],
        elapsed_ms=elapsed_ms,
    )
