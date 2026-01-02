"""Receipt ingestion with tenant isolation."""
from .core import dual_hash, emit_receipt, StopRule

INGEST_SCHEMA = {
    "receipt_type": "ingest_receipt",
    "required": ["receipt_type", "ts", "tenant_id", "payload_hash", "redactions", "source_type"],
    "properties": {
        "receipt_type": {"type": "string", "const": "ingest_receipt"},
        "ts": {"type": "number"},
        "tenant_id": {"type": "string"},
        "payload_hash": {"type": "string"},
        "redactions": {"type": "array"},
        "source_type": {"type": "string"}
    }
}


def stoprule_ingest(e: Exception, tenant_id: str = "default") -> None:
    """Emit anomaly receipt then raise StopRule."""
    emit_receipt("anomaly_receipt", {
        "anomaly_type": "ingest_failure",
        "error": str(e),
        "stage": "ingest"
    }, tenant_id)
    raise StopRule(f"Ingest stoprule triggered: {e}")


def ingest(receipt: dict, tenant_id: str = "default", source_type: str = "api") -> dict:
    """Accept new receipt with tenant isolation. SLO: ≤50ms p95."""
    try:
        if not isinstance(receipt, dict):
            raise ValueError("Receipt must be a dict")

        payload_hash = dual_hash(receipt)

        return emit_receipt("ingest_receipt", {
            "payload_hash": payload_hash,
            "redactions": [],
            "source_type": source_type
        }, tenant_id)

    except StopRule:
        raise
    except Exception as e:
        stoprule_ingest(e, tenant_id)
