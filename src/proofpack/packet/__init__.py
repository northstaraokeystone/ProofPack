"""Packet module: decision packaging with consistency auditing."""
from proofpack.core.receipt import StopRule, dual_hash, emit_receipt, merkle

from .attach import ATTACH_SCHEMA, attach
from .audit import CONSISTENCY_SCHEMA, HALT_SCHEMA, audit
from .build import PACKET_SCHEMA, build

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
