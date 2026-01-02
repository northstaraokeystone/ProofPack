"""
ProofPack - Receipts-Native Accountability Infrastructure

A system that keeps cryptographic receipts for everything.
Every operation emits proof. Every decision is verifiable.

The Three Laws:
    LAW_1 = "No receipt → not real"
    LAW_2 = "No test → not shipped"
    LAW_3 = "No gate → not alive"
"""

__version__ = "0.3.2"
__author__ = "Northstar AO Keystone Research Lab"

# Public API - imported after submodules are available
# These imports are defined in a try block to allow the package
# to be imported even during installation before submodules exist

try:
    from proofpack.core.receipt import dual_hash, emit_receipt, merkle, StopRule
    from proofpack.core.schemas import validate_receipt, RECEIPT_SCHEMAS

    __all__ = [
        "dual_hash",
        "emit_receipt",
        "merkle",
        "StopRule",
        "validate_receipt",
        "RECEIPT_SCHEMAS",
        "__version__",
    ]
except ImportError:
    # During installation, submodules may not exist yet
    __all__ = ["__version__"]
