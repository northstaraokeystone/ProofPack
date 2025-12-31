"""Economic primitive module for SLO-based payment integration.

Enables proof-to-payment workflows where receipt outcomes
can trigger automatic payment release or withholding.

"Pay for proof, not promises."

Usage:
    from proofpack.economic import evaluate_slo, calculate_payment

    # Evaluate SLO status
    slo_status = evaluate_slo(receipt, slo_config)

    # Calculate payment eligibility
    payment = calculate_payment(receipt, pricing_config)

SLO Status Values:
    - met: Receipt proves SLO was achieved
    - failed: Receipt proves SLO was missed
    - pending: SLO evaluation incomplete
    - exempt: SLO does not apply to this receipt
"""
import json
from datetime import datetime

from proofpack.core.receipt import dual_hash, emit_receipt


# Default SLO thresholds
DEFAULT_SLO_CONFIG = {
    "latency_p95_ms": 100,
    "recall_floor": 0.999,
    "bias_max": 0.005,
    "error_rate_max": 0.01,
}

# Default pricing
DEFAULT_PRICING = {
    "per_receipt_usd": 0.001,
    "slo_met_multiplier": 1.0,
    "slo_failed_penalty": 0.5,
}


def evaluate_slo(
    receipt: dict,
    slo_config: dict = None,
    tenant_id: str = "default"
) -> str:
    """Check if receipt meets configured SLO.

    Args:
        receipt: Receipt to evaluate
        slo_config: SLO thresholds (uses defaults if not provided)
        tenant_id: Tenant for receipt emission

    Returns:
        SLO status: "met", "failed", "pending", or "exempt"
    """
    slo_config = slo_config or DEFAULT_SLO_CONFIG
    receipt_type = receipt.get("receipt_type", "unknown")

    # Some receipt types are exempt from SLO
    exempt_types = {"anomaly", "redaction", "offline_sync", "conflict_resolution"}
    if receipt_type in exempt_types:
        return "exempt"

    # Check type-specific SLOs
    violations = []

    # Latency check (for receipts with timing data)
    if "latency_ms" in receipt or "elapsed_ms" in receipt:
        latency = receipt.get("latency_ms") or receipt.get("elapsed_ms", 0)
        threshold = slo_config.get("latency_p95_ms", 100)
        if latency > threshold:
            violations.append(f"latency {latency}ms > {threshold}ms")

    # Recall check (for retrieval/search receipts)
    if "recall" in receipt:
        recall = receipt.get("recall", 0)
        threshold = slo_config.get("recall_floor", 0.999)
        if recall < threshold:
            violations.append(f"recall {recall} < {threshold}")

    # Bias check
    if "disparity" in receipt:
        disparity = receipt.get("disparity", 0)
        threshold = slo_config.get("bias_max", 0.005)
        if disparity > threshold:
            violations.append(f"bias {disparity} > {threshold}")

    # Error rate check
    if "error_rate" in receipt:
        error_rate = receipt.get("error_rate", 0)
        threshold = slo_config.get("error_rate_max", 0.01)
        if error_rate > threshold:
            violations.append(f"error_rate {error_rate} > {threshold}")

    # If receipt has no measurable SLO fields, it's pending
    measurable_fields = {"latency_ms", "elapsed_ms", "recall", "disparity", "error_rate"}
    has_measurable = bool(measurable_fields & set(receipt.keys()))
    if not has_measurable:
        return "pending"

    status = "failed" if violations else "met"

    emit_receipt("slo_evaluation", {
        "tenant_id": tenant_id,
        "receipt_type": receipt_type,
        "receipt_hash": receipt.get("payload_hash", "unknown"),
        "slo_status": status,
        "violations": violations,
        "thresholds": slo_config,
    })

    return status


def calculate_payment(
    receipt: dict,
    pricing_config: dict = None,
    tenant_id: str = "default"
) -> dict:
    """Determine payment amount based on receipt and SLO status.

    Args:
        receipt: Receipt to calculate payment for
        pricing_config: Pricing configuration
        tenant_id: Tenant for receipt emission

    Returns:
        Payment calculation result
    """
    pricing = pricing_config or DEFAULT_PRICING
    base_amount = pricing.get("per_receipt_usd", 0.001)

    # Get SLO status from receipt or evaluate
    slo_status = receipt.get("economic_metadata", {}).get("slo_status")
    if not slo_status:
        slo_status = evaluate_slo(receipt, tenant_id=tenant_id)

    # Calculate amount based on SLO status
    if slo_status == "met":
        multiplier = pricing.get("slo_met_multiplier", 1.0)
        payment_eligible = True
    elif slo_status == "failed":
        multiplier = -pricing.get("slo_failed_penalty", 0.5)
        payment_eligible = False
    elif slo_status == "exempt":
        multiplier = 1.0
        payment_eligible = True
    else:  # pending
        multiplier = 0.0
        payment_eligible = False

    amount = base_amount * multiplier

    return {
        "slo_status": slo_status,
        "base_amount_usd": base_amount,
        "multiplier": multiplier,
        "payment_amount_usd": max(amount, 0),
        "payment_eligible": payment_eligible,
    }


def generate_payment_receipt(
    receipt: dict,
    evaluation: dict,
    tenant_id: str = "default"
) -> dict:
    """Create receipt documenting payment eligibility.

    Args:
        receipt: Source receipt being evaluated
        evaluation: Result from calculate_payment
        tenant_id: Tenant for receipt emission

    Returns:
        Payment eligibility receipt
    """
    return emit_receipt("payment_eligibility", {
        "tenant_id": tenant_id,
        "source_receipt_id": receipt.get("payload_hash", "unknown"),
        "source_receipt_type": receipt.get("receipt_type", "unknown"),
        "slo_evaluated": evaluation.get("slo_status"),
        "slo_result": "met" if evaluation.get("payment_eligible") else "failed",
        "payment_amount_usd": evaluation.get("payment_amount_usd", 0),
        "payment_status": "pending",
        "payment_system_ref": None,
    })


def export_for_payment_system(
    receipts: list[dict],
    tenant_id: str = "default",
    pricing_config: dict = None
) -> dict:
    """Format batch of receipts for external payment integration.

    Args:
        receipts: Receipts to process
        tenant_id: Tenant for batch
        pricing_config: Pricing configuration

    Returns:
        Payment batch for external system
    """
    batch_id = dual_hash(json.dumps([r.get("payload_hash") for r in receipts], sort_keys=True))[:32]

    payment_items = []
    total_amount = 0.0
    eligible_count = 0
    failed_count = 0

    for receipt in receipts:
        evaluation = calculate_payment(receipt, pricing_config, tenant_id)

        item = {
            "receipt_id": receipt.get("payload_hash", "unknown"),
            "receipt_type": receipt.get("receipt_type", "unknown"),
            "slo_status": evaluation["slo_status"],
            "payment_eligible": evaluation["payment_eligible"],
            "amount_usd": evaluation["payment_amount_usd"],
        }
        payment_items.append(item)

        if evaluation["payment_eligible"]:
            total_amount += evaluation["payment_amount_usd"]
            eligible_count += 1
        else:
            failed_count += 1

    batch = {
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "receipt_count": len(receipts),
        "eligible_count": eligible_count,
        "failed_count": failed_count,
        "total_amount_usd": round(total_amount, 6),
        "items": payment_items,
        "status": "pending",
    }

    emit_receipt("payment_batch", {
        "tenant_id": tenant_id,
        "batch_id": batch_id,
        "receipt_count": len(receipts),
        "eligible_count": eligible_count,
        "total_amount_usd": round(total_amount, 6),
    })

    return batch


def get_pending_payments(
    receipts: list[dict],
    tenant_id: str = "default"
) -> list[dict]:
    """Filter receipts to only payment-eligible ones.

    Args:
        receipts: Receipts to filter
        tenant_id: Tenant context

    Returns:
        List of payment-eligible receipts with amounts
    """
    pending = []

    for receipt in receipts:
        evaluation = calculate_payment(receipt, tenant_id=tenant_id)
        if evaluation["payment_eligible"]:
            pending.append({
                "receipt": receipt,
                "evaluation": evaluation,
            })

    return pending


def attach_economic_metadata(
    receipt: dict,
    slo_config: dict = None,
    pricing_config: dict = None,
    tenant_id: str = "default"
) -> dict:
    """Attach economic metadata to receipt.

    Args:
        receipt: Receipt to enhance
        slo_config: SLO configuration
        pricing_config: Pricing configuration
        tenant_id: Tenant context

    Returns:
        Receipt with economic_metadata attached
    """
    slo_status = evaluate_slo(receipt, slo_config, tenant_id)
    payment = calculate_payment(receipt, pricing_config, tenant_id)

    receipt["economic_metadata"] = {
        "slo_status": slo_status,
        "slo_threshold": slo_config or DEFAULT_SLO_CONFIG,
        "payment_eligible": payment["payment_eligible"],
        "payment_amount_usd": payment["payment_amount_usd"],
        "payment_trigger_id": None,
    }

    return receipt
