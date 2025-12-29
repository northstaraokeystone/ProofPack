# Economic Integration Guide

ProofPack enables proof-to-payment workflows where receipt outcomes can trigger automatic payment release or withholding.

> "Pay for proof, not promises."

## Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Receipt   │───>│  Evaluate   │───>│  Calculate  │───>│   Payment   │
│   Created   │    │     SLO     │    │   Payment   │    │   Trigger   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## SLO Status

Every receipt can have an SLO status indicating whether it meets service level objectives:

| Status | Description | Payment Action |
|--------|-------------|----------------|
| `met` | SLO achieved | Release payment |
| `failed` | SLO missed | Withhold payment |
| `pending` | Evaluation incomplete | Hold payment |
| `exempt` | SLO not applicable | Default to release |

## Quick Start

```python
from proofpack.economic import evaluate_slo, calculate_payment

# Receipt with performance data
receipt = {
    "receipt_type": "inference",
    "latency_ms": 45,
    "recall": 0.995,
    "tenant_id": "customer-001"
}

# Evaluate against SLO
status = evaluate_slo(receipt, {
    "latency_p95_ms": 100,
    "recall_floor": 0.99
})
# Returns: "met"

# Calculate payment
payment = calculate_payment(receipt)
# Returns: {
#     "slo_status": "met",
#     "payment_eligible": True,
#     "payment_amount_usd": 0.001
# }
```

## SLO Configuration

Define SLO thresholds for different metrics:

```python
slo_config = {
    "latency_p95_ms": 100,    # Max acceptable latency
    "recall_floor": 0.999,     # Min acceptable recall
    "bias_max": 0.005,         # Max acceptable bias
    "error_rate_max": 0.01,    # Max acceptable error rate
}

status = evaluate_slo(receipt, slo_config)
```

## Pricing Configuration

Configure payment amounts and penalties:

```python
pricing_config = {
    "per_receipt_usd": 0.001,       # Base payment per receipt
    "slo_met_multiplier": 1.0,       # Multiplier when SLO met
    "slo_failed_penalty": 0.5,       # Penalty when SLO failed
}

payment = calculate_payment(receipt, pricing_config)
```

## Payment Eligibility Receipt

Document payment decisions with a receipt:

```python
from proofpack.economic import generate_payment_receipt

payment_receipt = generate_payment_receipt(
    receipt,
    evaluation=payment,
    tenant_id="customer-001"
)

# Creates receipt with:
# {
#     "receipt_type": "payment_eligibility",
#     "source_receipt_id": "...",
#     "slo_evaluated": "met",
#     "slo_result": "met",
#     "payment_amount_usd": 0.001,
#     "payment_status": "pending"
# }
```

## Batch Export

Export payment-eligible receipts for external payment systems:

```python
from proofpack.economic import export_for_payment_system

batch = export_for_payment_system(
    receipts=receipts_list,
    tenant_id="customer-001"
)

# Returns:
# {
#     "batch_id": "abc123...",
#     "tenant_id": "customer-001",
#     "receipt_count": 100,
#     "eligible_count": 95,
#     "failed_count": 5,
#     "total_amount_usd": 0.095,
#     "items": [...]
# }
```

## Attaching Economic Metadata

Add economic metadata to any receipt:

```python
from proofpack.economic import attach_economic_metadata

receipt = attach_economic_metadata(
    receipt,
    slo_config=slo_config,
    pricing_config=pricing_config
)

# Adds:
# "economic_metadata": {
#     "slo_status": "met",
#     "slo_threshold": {...},
#     "payment_eligible": True,
#     "payment_amount_usd": 0.001,
#     "payment_trigger_id": None
# }
```

## Integration Patterns

### Escrow Pattern

```
1. Customer deposits funds to escrow
2. Service performs work, generates receipts
3. Receipts evaluated against SLO
4. Payment released or withheld based on status
```

### Pay-Per-Receipt Pattern

```
1. Define SLO and pricing per receipt type
2. Generate receipts during operation
3. Batch receipts periodically
4. Calculate total payment
5. Settle with customer
```

### Penalty Pattern

```
1. Baseline payment assumed
2. SLO failures result in penalties
3. Net payment = base - penalties
4. Incentivizes meeting SLOs
```

## External Payment Systems

ProofPack generates payment metadata but does not process payments directly. Integration points:

| System | Integration Method |
|--------|-------------------|
| Stripe | Export batch, use payment_trigger_id |
| Ethereum | Use payment_trigger_id as transaction memo |
| Bank Transfer | Include batch_id in transfer reference |
| Internal Ledger | Use batch as journal entry source |

## Exempt Receipt Types

These receipt types are automatically exempt from SLO evaluation:
- `anomaly`
- `redaction`
- `offline_sync`
- `conflict_resolution`

## Best Practices

1. **Define SLOs upfront** - Agree on thresholds before starting
2. **Include SLO in contracts** - Make thresholds legally binding
3. **Audit payment receipts** - Keep trail of all payment decisions
4. **Handle disputes** - Use receipt chain for resolution
5. **Set reasonable thresholds** - Achievable but meaningful

## Future: Smart Contract Integration

The `payment_trigger_id` field is reserved for future smart contract integration:

```python
# Future usage (not yet implemented)
receipt["economic_metadata"]["payment_trigger_id"] = "0xabc123..."
# Smart contract would automatically release payment when receipt is anchored
```

## See Also

- [RNES Standard](../standards/RNES_v1.md)
- [Extreme Environments](extreme-environments.md)
- [Privacy Levels](privacy-levels.md)
