"""Brief module: evidence synthesis with decision health scoring."""
from core.receipt import emit_receipt, dual_hash, StopRule

from .retrieve import retrieve, RETRIEVAL_SCHEMA
from .compose import compose, BRIEF_SCHEMA
from .health import score_health, HEALTH_SCHEMA
from .dialectic import dialectic, DIALECTIC_SCHEMA

RECEIPT_SCHEMA = {
    "retrieval_receipt": RETRIEVAL_SCHEMA,
    "brief_receipt": BRIEF_SCHEMA,
    "health_receipt": HEALTH_SCHEMA,
    "dialectic_receipt": DIALECTIC_SCHEMA
}

__all__ = [
    "emit_receipt",
    "dual_hash",
    "StopRule",
    "retrieve",
    "compose",
    "score_health",
    "dialectic",
    "RETRIEVAL_SCHEMA",
    "BRIEF_SCHEMA",
    "HEALTH_SCHEMA",
    "DIALECTIC_SCHEMA",
    "RECEIPT_SCHEMA"
]
