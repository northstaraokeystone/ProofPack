"""Packet module - claim-to-receipt fusion with consistency auditing.

Public API for assembling decision packets with cryptographic integrity.

Exports:
    From attach: attach, map_claims, find_supporting_receipts
    From audit: audit_consistency, compute_match_score
    From build: build_packet, DecisionPacket
    From schemas: PACKET_SCHEMAS
"""
from .attach import attach, map_claims, find_supporting_receipts
from .audit import audit_consistency, compute_match_score
from .build import build_packet, DecisionPacket
from .schemas import PACKET_SCHEMAS

__all__ = [
    # attach functions
    "attach",
    "map_claims",
    "find_supporting_receipts",
    # audit functions
    "audit_consistency",
    "compute_match_score",
    # build functions
    "build_packet",
    "DecisionPacket",
    # schemas
    "PACKET_SCHEMAS",
]
