"""Adaptive-k retrieval with budget constraints."""
import time
from core.receipt import emit_receipt, StopRule

RETRIEVAL_SCHEMA = {
    "receipt_type": "retrieval",
    "query_complexity": "atomic|focused|broad|comparative",
    "k": "int",
    "chunks": ["str"],
    "cost": {"tokens_used": "int", "ms_elapsed": "int"},
    "reason": "str"
}


def _classify_complexity(query: str) -> str:
    """Classify query complexity using rule-based heuristics."""
    words = query.lower().split()
    word_count = len(words)

    if "compare" in words or "vs" in words or "versus" in words:
        return "comparative"
    if word_count > 10 or "all" in words or "every" in words:
        return "broad"
    if word_count > 3:
        return "focused"
    return "atomic"


def retrieve(query: str, budget: dict, tenant_id: str = "default") -> dict:
    """Find relevant evidence within budget constraints."""
    t0 = time.time()

    complexity = _classify_complexity(query)
    k = min(budget["tokens"] // 100, 10)

    # Mock retrieval for v1 - actual vector search is future scope
    chunks = [f"chunk_{i}" for i in range(k)]

    ms_elapsed = int((time.time() - t0) * 1000)
    tokens_used = k * 100  # Mock token estimate

    # Stoprule: budget exceeded
    if ms_elapsed > budget["ms"]:
        emit_receipt("anomaly", {
            "metric": "budget",
            "baseline": budget["ms"],
            "delta": ms_elapsed - budget["ms"],
            "classification": "violation",
            "action": "reject"
        }, tenant_id)
        raise StopRule(f"Budget: {ms_elapsed}ms > {budget['ms']}ms")

    reason = f"{complexity}->k={k}, budget_capped" if k == 10 else f"{complexity}->k={k}"

    return emit_receipt("retrieval", {
        "query_complexity": complexity,
        "k": k,
        "chunks": chunks,
        "cost": {"tokens_used": tokens_used, "ms_elapsed": ms_elapsed},
        "reason": reason
    }, tenant_id)
