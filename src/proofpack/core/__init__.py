"""Core subpackage for ProofPack receipt primitives.

Exports all from receipt.py, schemas.py, and constants.py.
"""
from .receipt import dual_hash, emit_receipt, merkle, StopRule
from .schemas import RECEIPT_SCHEMAS, REQUIRED_FIELDS, validate_receipt
from .constants import (
    GATE_GREEN_THRESHOLD,
    GATE_YELLOW_THRESHOLD,
    WOUND_DROP_THRESHOLD,
    WOUND_SPAWN_THRESHOLD,
    MONTE_CARLO_DEFAULT_SIMS,
    MONTE_CARLO_DEFAULT_NOISE,
    MONTE_CARLO_VARIANCE_THRESHOLD,
    SPAWN_BASE_FORMULA,
    SPAWN_CONVERGENCE_MULTIPLIER,
    SPAWN_CONVERGENCE_THRESHOLD,
    AGENT_MAX_DEPTH,
    AGENT_MAX_POPULATION,
    AGENT_DEFAULT_TTL,
)

__all__ = [
    # Receipt primitives
    "dual_hash",
    "emit_receipt",
    "merkle",
    "StopRule",
    # Schemas
    "RECEIPT_SCHEMAS",
    "REQUIRED_FIELDS",
    "validate_receipt",
    # Constants
    "GATE_GREEN_THRESHOLD",
    "GATE_YELLOW_THRESHOLD",
    "WOUND_DROP_THRESHOLD",
    "WOUND_SPAWN_THRESHOLD",
    "MONTE_CARLO_DEFAULT_SIMS",
    "MONTE_CARLO_DEFAULT_NOISE",
    "MONTE_CARLO_VARIANCE_THRESHOLD",
    "SPAWN_BASE_FORMULA",
    "SPAWN_CONVERGENCE_MULTIPLIER",
    "SPAWN_CONVERGENCE_THRESHOLD",
    "AGENT_MAX_DEPTH",
    "AGENT_MAX_POPULATION",
    "AGENT_DEFAULT_TTL",
]
