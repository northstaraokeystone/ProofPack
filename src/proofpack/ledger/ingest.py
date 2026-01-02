"""Receipt ingestion with tenant isolation."""
from .core import StopRule, dual_hash, emit_receipt

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


def ingest(payload: bytes | str | dict, tenant_id: str = "default", source_type: str = "api") -> dict:
    """Accept new payload with tenant isolation. SLO: ≤50ms p95.

    Args:
        payload: Data to ingest (bytes, str, or dict)
        tenant_id: Tenant isolation key
        source_type: Source of the payload (api, file, stream, etc.)
    """
    try:
        payload_hash = dual_hash(payload)

        return emit_receipt("ingest_receipt", {
            "payload_hash": payload_hash,
            "redactions": [],
            "source_type": source_type
        }, tenant_id)

    except StopRule:
        raise
    except Exception as e:
        stoprule_ingest(e, tenant_id)
