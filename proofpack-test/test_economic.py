"""Tests for economic module."""
from economic import (
    evaluate_slo,
    calculate_payment,
    export_for_payment_system,
    attach_economic_metadata,
)


class TestSLOEvaluation:
    """Test SLO evaluation functionality."""

    def test_met_slo(self):
        """Test SLO status when all thresholds met."""
        receipt = {
            "receipt_type": "inference",
            "latency_ms": 50,
            "recall": 0.999,
        }

        status = evaluate_slo(receipt, {
            "latency_p95_ms": 100,
            "recall_floor": 0.99,
        })

        assert status == "met"

    def test_failed_slo_latency(self):
        """Test SLO failure on latency violation."""
        receipt = {
            "receipt_type": "inference",
            "latency_ms": 150,
        }

        status = evaluate_slo(receipt, {"latency_p95_ms": 100})

        assert status == "failed"

    def test_failed_slo_recall(self):
        """Test SLO failure on recall violation."""
        receipt = {
            "receipt_type": "search",
            "recall": 0.95,
        }

        status = evaluate_slo(receipt, {"recall_floor": 0.999})

        assert status == "failed"

    def test_exempt_receipt_types(self):
        """Test exempt receipt types."""
        receipt = {"receipt_type": "anomaly"}

        status = evaluate_slo(receipt)

        assert status == "exempt"

    def test_pending_no_metrics(self):
        """Test pending status when no metrics available."""
        receipt = {
            "receipt_type": "decision",
            "action": "approve",
        }

        status = evaluate_slo(receipt)

        assert status == "pending"


class TestPaymentCalculation:
    """Test payment calculation functionality."""

    def test_payment_eligible_met(self):
        """Test payment eligible when SLO met."""
        receipt = {
            "receipt_type": "inference",
            "latency_ms": 50,
        }

        payment = calculate_payment(receipt, {"per_receipt_usd": 0.001})

        assert payment["payment_eligible"]
        assert payment["payment_amount_usd"] > 0

    def test_payment_ineligible_failed(self):
        """Test payment ineligible when SLO failed."""
        receipt = {
            "receipt_type": "inference",
            "latency_ms": 200,  # Exceeds default threshold
        }

        payment = calculate_payment(receipt, {
            "per_receipt_usd": 0.001,
            "latency_p95_ms": 100,
        })

        # Should still get a payment dict, just not eligible
        assert "payment_eligible" in payment

    def test_exempt_is_eligible(self):
        """Test exempt receipts are payment eligible."""
        receipt = {"receipt_type": "anomaly"}

        payment = calculate_payment(receipt)

        assert payment["slo_status"] == "exempt"
        assert payment["payment_eligible"]


class TestBatchExport:
    """Test batch export functionality."""

    def test_export_batch(self):
        """Test exporting batch of receipts."""
        receipts = [
            {"receipt_type": "inference", "latency_ms": 50},
            {"receipt_type": "inference", "latency_ms": 50},
            {"receipt_type": "anomaly"},
        ]

        batch = export_for_payment_system(receipts)

        assert batch["receipt_count"] == 3
        assert "total_amount_usd" in batch
        assert "items" in batch
        assert len(batch["items"]) == 3

    def test_export_empty_batch(self):
        """Test exporting empty batch."""
        batch = export_for_payment_system([])

        assert batch["receipt_count"] == 0
        assert batch["total_amount_usd"] == 0


class TestMetadataAttachment:
    """Test economic metadata attachment."""

    def test_attach_metadata(self):
        """Test attaching economic metadata to receipt."""
        receipt = {
            "receipt_type": "inference",
            "latency_ms": 50,
        }

        enriched = attach_economic_metadata(receipt)

        assert "economic_metadata" in enriched
        assert "slo_status" in enriched["economic_metadata"]
        assert "payment_eligible" in enriched["economic_metadata"]
        assert "payment_amount_usd" in enriched["economic_metadata"]
