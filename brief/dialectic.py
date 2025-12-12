"""PRO/CON synthesis with resolution status classification."""
from ledger.core import emit_receipt

DIALECTIC_SCHEMA = {
    "receipt_type": "dialectic",
    "pro": [{"chunk_id": "str", "claim": "str", "strength": "float 0-1"}],
    "con": [{"chunk_id": "str", "claim": "str", "strength": "float 0-1"}],
    "gaps": ["str"],
    "resolution_status": "one_sided|open|resolved",
    "margin": "float 0-1"
}


def _classify_stance(chunk_id: str, index: int) -> str:
    """Classify evidence as PRO or CON using rule-based heuristic."""
    # v1: alternate classification based on index (mock for real NLP)
    return "pro" if index % 2 == 0 else "con"


def _compute_resolution(pro_count: int, con_count: int, total: int) -> tuple:
    """Determine resolution status and margin."""
    if total == 0:
        return "open", 0.0

    pro_ratio = pro_count / total
    con_ratio = con_count / total
    margin = abs(pro_ratio - con_ratio)

    if margin > 0.6:  # >80% on one side
        return "one_sided", round(margin, 3)
    if margin > 0.2:  # Clear majority with counterarguments
        return "resolved", round(margin, 3)
    return "open", round(margin, 3)


def dialectic(evidence: list, tenant_id: str = "default") -> dict:
    """Generate balanced PRO/CON analysis from evidence."""
    pro = []
    con = []
    gaps = []

    for i, chunk in enumerate(evidence):
        chunk_id = str(chunk) if not isinstance(chunk, dict) else chunk.get("chunk_id", str(i))
        stance = _classify_stance(chunk_id, i)
        strength = round(0.9 - (i * 0.05), 2) if i < 18 else 0.1
        claim = f"Evidence from {chunk_id}"

        entry = {"chunk_id": chunk_id, "claim": claim, "strength": max(strength, 0.1)}
        if stance == "pro":
            pro.append(entry)
        else:
            con.append(entry)

    # Coverage penalty per SDD:212-213: sparse corpora need different treatment
    evidence_count = len(evidence)
    if evidence_count < 50:
        gaps.append("sparse_corpus: evidence_count < 50, coverage penalty halved")

    # Identify structural gaps
    if not pro:
        gaps.append("no_supporting_evidence")
    if not con:
        gaps.append("no_opposing_evidence")

    resolution_status, margin = _compute_resolution(len(pro), len(con), len(evidence))

    return emit_receipt("dialectic", {
        "pro": pro,
        "con": con,
        "gaps": gaps,
        "resolution_status": resolution_status,
        "margin": margin
    }, tenant_id)
