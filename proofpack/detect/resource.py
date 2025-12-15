"""Resource consumption tracking (was token-cop).

Functions:
    track_resources: Track resource consumption and emit receipt
    aggregate_resources: Aggregate multiple resource receipts

Constants:
    TOKEN_WARNING_THRESHOLD: 0.8
    TOKEN_CRITICAL_THRESHOLD: 0.95
    COST_WARNING_THRESHOLD: 0.7
    COST_CRITICAL_THRESHOLD: 0.9
"""
from proofpack.core.receipt import emit_receipt, StopRule


# Threshold constants
TOKEN_WARNING_THRESHOLD = 0.8
TOKEN_CRITICAL_THRESHOLD = 0.95
COST_WARNING_THRESHOLD = 0.7
COST_CRITICAL_THRESHOLD = 0.9

# Valid resource types
VALID_RESOURCE_TYPES = {"tokens", "compute", "memory", "io", "cost"}


def track_resources(
    resource_type: str,
    consumed: float,
    limit: float,
    period: str,
    tenant_id: str = "default"
) -> dict:
    """Track resource consumption and emit receipt.

    Computes utilization and checks threshold. Emits anomaly_receipt
    if threshold exceeded for tokens or cost.

    Args:
        resource_type: Type of resource (tokens, compute, memory, io, cost)
        consumed: Amount consumed
        limit: Limit for the resource
        period: Time period (e.g., "1h", "24h")
        tenant_id: Tenant identifier

    Returns:
        resource_receipt dict
    """
    # Compute utilization
    if limit > 0:
        utilization = consumed / limit
    else:
        utilization = 0.0 if consumed == 0 else float('inf')

    # Check threshold (90% utilization)
    threshold_exceeded = utilization > 0.9

    # Emit resource receipt
    receipt = emit_receipt("resource", {
        "tenant_id": tenant_id,
        "resource_type": resource_type,
        "consumed": consumed,
        "limit": limit,
        "utilization": utilization,
        "period": period,
        "threshold_exceeded": threshold_exceeded,
    })

    # Emit anomaly receipt for tokens/cost over threshold
    if threshold_exceeded and resource_type in ("tokens", "cost"):
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": f"{resource_type}_utilization",
            "baseline": 0.9,
            "delta": utilization - 0.9,
            "classification": "violation",
            "action": "alert",
        })

    return receipt


def aggregate_resources(resource_receipts: list[dict]) -> dict:
    """Aggregate multiple resource receipts by type.

    Pure function. Groups by resource_type and computes totals.

    Args:
        resource_receipts: List of resource_receipt dicts

    Returns:
        Dict mapping resource_type to {total_consumed, avg_utilization, periods_exceeded}
    """
    aggregates = {}

    for receipt in resource_receipts:
        resource_type = receipt.get("resource_type")
        if not resource_type:
            continue

        if resource_type not in aggregates:
            aggregates[resource_type] = {
                "total_consumed": 0.0,
                "utilization_sum": 0.0,
                "count": 0,
                "periods_exceeded": 0,
            }

        agg = aggregates[resource_type]
        agg["total_consumed"] += receipt.get("consumed", 0.0)
        agg["utilization_sum"] += receipt.get("utilization", 0.0)
        agg["count"] += 1
        if receipt.get("threshold_exceeded", False):
            agg["periods_exceeded"] += 1

    # Compute final averages
    result = {}
    for resource_type, agg in aggregates.items():
        result[resource_type] = {
            "total_consumed": agg["total_consumed"],
            "avg_utilization": agg["utilization_sum"] / agg["count"] if agg["count"] > 0 else 0.0,
            "periods_exceeded": agg["periods_exceeded"],
        }

    return result
