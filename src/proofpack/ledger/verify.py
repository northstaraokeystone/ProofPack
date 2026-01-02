"""Proof verification against Merkle proof path."""
from .core import StopRule, dual_hash, emit_receipt

VERIFY_SCHEMA = {
    "receipt_type": "verify_receipt",
    "required": ["receipt_type", "ts", "tenant_id", "payload_hash", "receipt_hash", "merkle_root", "proof_valid", "status"],
    "properties": {
        "receipt_type": {"type": "string", "const": "verify_receipt"},
        "ts": {"type": "number"},
        "tenant_id": {"type": "string"},
        "payload_hash": {"type": "string"},
        "receipt_hash": {"type": "string"},
        "merkle_root": {"type": "string"},
        "proof_valid": {"type": "boolean"},
        "status": {"type": "string", "enum": ["valid", "invalid", "error"]}
    }
}


def verify(receipt: dict, proof: dict, tenant_id: str = "default") -> dict:
    """Verify receipt authenticity against Merkle proof path. SLO: ≤2s p95."""
    try:
        receipt_hash = dual_hash(receipt)
        merkle_root = proof.get("merkle_root", "")
        proof_path = proof.get("proof_path", [])

        current_hash = receipt_hash
        for step in proof_path:
            sibling_hash = step.get("hash", "")
            position = step.get("position", "")

            if position == "left":
                combined = sibling_hash + current_hash
            else:
                combined = current_hash + sibling_hash

            current_hash = dual_hash(combined)

        proof_valid = current_hash == merkle_root
        status = "valid" if proof_valid else "invalid"

        return emit_receipt("verify_receipt", {
            "receipt_hash": receipt_hash,
            "merkle_root": merkle_root,
            "proof_valid": proof_valid,
            "status": status
        }, tenant_id)

    except StopRule:
        raise
    except Exception as e:
        emit_receipt("anomaly_receipt", {
            "anomaly_type": "verify_failure",
            "error": str(e),
            "stage": "verify"
        }, tenant_id)
        raise StopRule(f"Verify stoprule triggered: {e}")
