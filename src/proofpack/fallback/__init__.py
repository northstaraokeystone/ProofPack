"""Confidence-Gated Web Fallback (CRAG).

When internal receipts yield low-confidence answers, automatically
augment with web sources using the Corrective RAG pattern.

Flow:
    1. Generate synthesis using proof(BRIEF, ...)
    2. Evaluate confidence (CORRECT/AMBIGUOUS/INCORRECT)
    3. If needed, fetch web sources and merge

Classifications:
    - CORRECT (>0.8): Return synthesis as-is
    - AMBIGUOUS (0.5-0.8): Augment with web search, merge results
    - INCORRECT (<0.5): Reformulate query, retry internal, then web

Usage:
    from fallback import evaluate, correct, merge

    # Evaluate synthesis confidence
    classification, confidence = evaluate.score(synthesis)

    # If needed, correct with web fallback
    if classification != "CORRECT":
        web_results = correct.with_web(query)
        merged = merge.combine(synthesis, web_results)
"""

from .correct import decompose, reformulate, with_web
from .evaluate import Classification, score
from .merge import MergeStrategy, combine

__all__ = [
    # Evaluation
    "score",
    "Classification",
    # Correction
    "with_web",
    "reformulate",
    "decompose",
    # Merge
    "combine",
    "MergeStrategy",
]
