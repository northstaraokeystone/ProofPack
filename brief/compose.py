"""Brief composition with executive summary."""
import time
from ledger.core import emit_receipt, StopRule

BRIEF_SCHEMA = {
    "receipt_type": "brief",
    "executive_summary": "str",
    "supporting_evidence": [{"chunk_id": "str", "confidence": "float 0-1"}],
    "evidence_count": "int"
}


def compose(evidence: list, tenant_id: str = "default") -> dict:
    """Synthesize evidence into executive summary."""
    t0 = time.time()

    # Stoprule: empty evidence
    if not evidence:
        emit_receipt("anomaly", {
            "metric": "coverage",
            "baseline": 1,
            "delta": -1,
            "classification": "violation",
            "action": "escalate"
        }, tenant_id)
        raise StopRule("Coverage: no evidence provided")

    # v1: concatenate/dedupe evidence chunks
    unique_chunks = list(dict.fromkeys(evidence))
    executive_summary = f"Brief synthesizing {len(unique_chunks)} evidence chunks: " + \
                        ", ".join(str(c) for c in unique_chunks[:5])
    if len(unique_chunks) > 5:
        executive_summary += f" (+{len(unique_chunks) - 5} more)"

    # Assign confidence based on position (mock heuristic for v1)
    supporting_evidence = [
        {"chunk_id": str(chunk), "confidence": round(1.0 - (i * 0.05), 2)}
        for i, chunk in enumerate(unique_chunks)
    ]

    ms_elapsed = int((time.time() - t0) * 1000)
    if ms_elapsed > 500:
        emit_receipt("anomaly", {
            "metric": "latency",
            "baseline": 500,
            "delta": ms_elapsed - 500,
            "classification": "degradation",
            "action": "alert"
        }, tenant_id)

    return emit_receipt("brief", {
        "executive_summary": executive_summary,
        "supporting_evidence": supporting_evidence,
        "evidence_count": len(unique_chunks)
    }, tenant_id)
