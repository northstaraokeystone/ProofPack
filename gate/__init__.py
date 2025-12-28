"""Pre-execution confidence gating.

Blocks catastrophic actions BEFORE execution, not after.
"""
from .confidence import calculate_confidence
from .decision import gate_decision, GateDecision
from .drift import measure_drift

__all__ = [
    "calculate_confidence",
    "gate_decision",
    "GateDecision",
    "measure_drift",
]
