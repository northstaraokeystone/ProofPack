"""Packet module: decision packaging with consistency auditing."""
from ledger.core import emit_receipt, dual_hash, merkle, StopRule

from .attach import attach, ATTACH_SCHEMA
from .audit import audit, CONSISTENCY_SCHEMA, HALT_SCHEMA
from .build import build, PACKET_SCHEMA

RECEIPT_SCHEMA = {
    "attach_receipt": ATTACH_SCHEMA,
    "consistency_receipt": CONSISTENCY_SCHEMA,
    "halt_receipt": HALT_SCHEMA,
    "packet_receipt": PACKET_SCHEMA
}

__all__ = [
    "emit_receipt",
    "dual_hash",
    "merkle",
    "StopRule",
    "attach",
    "audit",
    "build",
    "ATTACH_SCHEMA",
    "CONSISTENCY_SCHEMA",
    "HALT_SCHEMA",
    "PACKET_SCHEMA",
    "RECEIPT_SCHEMA"
]
