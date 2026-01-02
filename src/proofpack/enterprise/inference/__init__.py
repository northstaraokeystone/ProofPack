"""Inference wrapper module for ML model call receipts.

Provides:
    - wrap_inference: Wrap inference function with receipt emission
    - compute_model_hash: Compute dual-hash of model
    - emit_inference_receipt: Emit inference receipt
    - receipts_inference: Decorator for inference functions
"""

from .wrapper import (
    compute_model_hash,
    emit_inference_receipt,
    receipts_inference,
    wrap_inference,
)

__all__ = [
    "wrap_inference",
    "compute_model_hash",
    "emit_inference_receipt",
    "receipts_inference",
]
