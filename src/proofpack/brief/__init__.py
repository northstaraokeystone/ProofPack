"""Brief module: evidence synthesis with decision health scoring."""
from proofpack.core.receipt import StopRule, dual_hash, emit_receipt

from .compose import BRIEF_SCHEMA, compose
from .dialectic import DIALECTIC_SCHEMA, dialectic
from .health import HEALTH_SCHEMA, score_health
from .retrieve import RETRIEVAL_SCHEMA, retrieve

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
