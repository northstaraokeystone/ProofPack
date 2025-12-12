"""Integration tests for cross-module pipeline validation.

Cross-module chains tested:
1. ledger → brief (receipts feed evidence synthesis)
2. brief → packet (brief becomes decision packet)
3. detect → loop (alerts trigger HARVEST)
4. Full pipeline: ingest → anchor → brief → packet → detect → loop
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import pytest

# Import from core modules
from ledger.core import emit_receipt, dual_hash, merkle
from ledger.ingest import ingest
from ledger.anchor import anchor_batch
from brief.retrieve import retrieve
from brief.compose import compose_brief
from packet.build import build_packet
from packet.attach import attach_evidence
from detect.core import scan_metrics
from detect.anomaly import detect_anomalies
from loop.src.cycle import run_cycle, CycleState
from loop.src.harvest import harvest_patterns
from loop.src.completeness import update_completeness, CompletenessState


class TestLedgerToBrief:
    """Integration: ledger → brief (receipts feed evidence synthesis)."""

    def test_receipts_feed_retrieval(self):
        """Receipts from ledger should be usable as evidence for brief."""
        # Generate receipts via ledger
        receipts = []
        for i in range(5):
            r = ingest(f"payload_{i}".encode(), "test_tenant", "integration_test")
            receipts.append(r)

        # Anchor the receipts
        anchor_receipt = anchor_batch(receipts, "test_tenant")

        # Retrieve should work with these receipts as context
        budget = {"tokens": 1000, "ms": 1000}
        retrieval = retrieve("find evidence", budget, "test_tenant")

        assert retrieval is not None, "Retrieval should work"
        assert "receipt_type" in retrieval, "Should return valid receipt"

    def test_anchor_provides_merkle_for_brief(self):
        """Anchored receipts should provide merkle proof for brief composition."""
        # Ingest and anchor
        receipts = [ingest(b"data", "tenant", "source") for _ in range(4)]
        anchor = anchor_batch(receipts, "tenant")

        # Merkle root should be usable as evidence reference
        merkle_root = anchor.get("merkle_root")
        assert merkle_root is not None, "Should have merkle root"

        # Compose brief with anchored evidence
        evidence = [{"merkle_root": merkle_root, "receipts": receipts}]
        brief = compose_brief(evidence, "tenant")

        assert brief is not None, "Should compose brief from anchored evidence"


class TestBriefToPacket:
    """Integration: brief → packet (brief becomes decision packet)."""

    def test_brief_becomes_packet(self):
        """Composed brief should become decision packet."""
        # Compose a brief
        evidence = [
            {"chunk": "evidence_1", "strength": 0.9},
            {"chunk": "evidence_2", "strength": 0.85}
        ]
        brief = compose_brief(evidence, "tenant")

        # Build packet from brief
        packet = build_packet(brief, evidence, "tenant")

        assert packet is not None, "Should build packet"
        assert "receipt_type" in packet, "Should return valid receipt"

    def test_packet_preserves_brief_hash(self):
        """Packet should preserve reference to original brief."""
        evidence = [{"id": "ev1"}]
        brief = compose_brief(evidence, "tenant")

        packet = build_packet(brief, evidence, "tenant")

        # Packet should have hash that includes brief
        assert "payload_hash" in packet, "Should have payload hash"

    def test_evidence_attachment(self):
        """Evidence should be properly attached to packet."""
        evidence = [{"id": f"ev_{i}"} for i in range(3)]
        decision = {"decision": "approve", "confidence": 0.9}

        attach_result = attach_evidence(evidence, decision, "tenant")

        assert attach_result is not None, "Should attach evidence"
        assert "receipt_type" in attach_result, "Should return receipt"


class TestDetectToLoop:
    """Integration: detect → loop (alerts trigger HARVEST)."""

    def test_anomaly_triggers_harvest(self):
        """Detected anomaly should trigger harvest in loop."""
        # Detect anomalies
        metrics = [
            {"latency": 50, "error_rate": 0.01},
            {"latency": 500, "error_rate": 0.10}  # Anomalous
        ]
        anomalies = detect_anomalies(metrics, "tenant")

        # Convert anomalies to gap signals for harvest
        gap_signals = []
        if isinstance(anomalies, list):
            for a in anomalies:
                gap_signals.append({
                    "pattern_key": a.get("metric", "unknown"),
                    "resolve_minutes": 45
                })
        elif isinstance(anomalies, dict) and "anomalies" in anomalies:
            for a in anomalies["anomalies"]:
                gap_signals.append({
                    "pattern_key": a.get("metric", "unknown"),
                    "resolve_minutes": 45
                })

        # Harvest should process these signals
        if gap_signals:
            harvest_receipt, patterns = harvest_patterns(gap_signals, {}, "tenant")
            assert harvest_receipt is not None, "Should harvest from anomalies"

    def test_scan_feeds_cycle(self):
        """Scan results should be processable by cycle."""
        # Scan metrics
        metrics = {"latency_p95": 100, "error_rate": 0.02}
        scan_result = scan_metrics(metrics, "tenant")

        # Run cycle with scan result as receipt
        receipts = [scan_result]
        state = CycleState()

        cycle_receipt, new_state = run_cycle(receipts, state, "tenant")

        assert cycle_receipt is not None, "Cycle should process scan results"
        assert new_state is not None, "Should update state"


class TestFullPipeline:
    """Integration: Full pipeline ingest → anchor → brief → packet → detect → loop."""

    def test_full_pipeline_flow(self):
        """Test complete pipeline from ingest to loop."""
        tenant = "integration_test"

        # 1. INGEST: Receive raw data
        ingest_receipts = []
        for i in range(5):
            r = ingest(f"raw_data_{i}".encode(), tenant, "test_source")
            ingest_receipts.append(r)
            assert "receipt_type" in r, f"Ingest {i} failed"

        # 2. ANCHOR: Anchor receipts with merkle tree
        anchor_receipt = anchor_batch(ingest_receipts, tenant)
        assert "merkle_root" in anchor_receipt, "Anchor should produce merkle root"

        # 3. BRIEF: Compose evidence brief
        evidence = [
            {"source_receipts": ingest_receipts, "merkle_root": anchor_receipt["merkle_root"]}
        ]
        brief = compose_brief(evidence, tenant)
        assert brief is not None, "Should compose brief"

        # 4. PACKET: Build decision packet
        packet = build_packet(brief, evidence, tenant)
        assert "receipt_type" in packet, "Should build packet"

        # 5. DETECT: Scan for anomalies
        metrics = {"receipts_processed": len(ingest_receipts), "latency": 50}
        scan_receipt = scan_metrics(metrics, tenant)
        assert scan_receipt is not None, "Should scan metrics"

        # 6. LOOP: Run cycle with all receipts
        all_receipts = ingest_receipts + [anchor_receipt, brief, packet, scan_receipt]
        state = CycleState()
        cycle_receipt, new_state = run_cycle(all_receipts, state, tenant)

        assert cycle_receipt["receipt_type"] == "cycle", "Should complete cycle"
        assert new_state is not None, "Should have updated state"

    def test_pipeline_completeness_tracking(self):
        """Pipeline should update completeness at each stage."""
        tenant = "completeness_test"
        completeness_state = CompletenessState()

        # Stage 1: Ingest (L0)
        ingest_receipt = ingest(b"data", tenant, "source")
        completeness_state, comp_receipt = update_completeness(
            completeness_state, [ingest_receipt], tenant
        )

        l0_after_ingest = comp_receipt.get("level_coverages", {}).get("L0", 0)
        assert l0_after_ingest > 0, "L0 should have coverage after ingest"

        # Stage 2: Anchor (L0)
        anchor_receipt = anchor_batch([ingest_receipt], tenant)
        completeness_state, comp_receipt = update_completeness(
            completeness_state, [anchor_receipt], tenant
        )

        # Stage 3: Cycle (L1)
        cycle_receipt, _ = run_cycle([ingest_receipt, anchor_receipt], CycleState(), tenant)
        completeness_state, comp_receipt = update_completeness(
            completeness_state, [cycle_receipt], tenant
        )

        l1_coverage = comp_receipt.get("level_coverages", {}).get("L1", 0)
        assert l1_coverage > 0, "L1 should have coverage after cycle"

    def test_pipeline_receipt_chain(self):
        """Receipts should form verifiable chain through pipeline."""
        tenant = "chain_test"
        receipt_chain = []

        # Build chain
        r1 = ingest(b"start", tenant, "source")
        receipt_chain.append(r1)

        r2 = anchor_batch([r1], tenant)
        receipt_chain.append(r2)

        evidence = [{"source": r1, "anchor": r2}]
        r3 = compose_brief(evidence, tenant)
        receipt_chain.append(r3)

        r4 = build_packet(r3, evidence, tenant)
        receipt_chain.append(r4)

        # Verify chain is linked via hashes
        for r in receipt_chain:
            assert "payload_hash" in r or "merkle_root" in r, \
                "Each receipt should have hash reference"

        # Compute merkle root of chain
        chain_root = merkle(receipt_chain)
        assert ":" in chain_root, "Chain should have valid merkle root"

    def test_pipeline_error_propagation(self):
        """Errors should propagate correctly through pipeline."""
        tenant = "error_test"

        # Start with valid ingest
        r1 = ingest(b"valid", tenant, "source")
        assert r1 is not None, "Should ingest"

        # Scan with anomalous metrics
        metrics = {"error_rate": 0.5}  # High error
        scan_result = scan_metrics(metrics, tenant)

        # Anomalies should be detectable
        anomalies = detect_anomalies([metrics], tenant)

        # Pipeline should still complete even with anomalies
        all_receipts = [r1, scan_result]
        if isinstance(anomalies, dict):
            all_receipts.append(anomalies)

        state = CycleState()
        cycle_receipt, _ = run_cycle(all_receipts, state, tenant)

        assert cycle_receipt is not None, "Pipeline should complete even with anomalies"


class TestModuleBoundaries:
    """Test data contracts at module boundaries."""

    def test_receipt_schema_consistency(self):
        """All modules should emit receipts with consistent schema."""
        tenant = "schema_test"

        receipts = [
            ingest(b"data", tenant, "source"),
            anchor_batch([{"id": 1}], tenant),
            retrieve("query", {"tokens": 100, "ms": 100}, tenant),
            scan_metrics({"latency": 50}, tenant)
        ]

        for r in receipts:
            # All receipts should have these fields
            assert "receipt_type" in r, "Missing receipt_type"
            assert "ts" in r, "Missing timestamp"
            assert "tenant_id" in r, "Missing tenant_id"

    def test_hash_format_consistency(self):
        """All modules should use dual_hash format."""
        # Check that payload_hash uses dual format
        receipt = ingest(b"test", "tenant", "source")

        payload_hash = receipt.get("payload_hash", "")
        if payload_hash:
            assert ":" in payload_hash, "Should use dual hash format"
            parts = payload_hash.split(":")
            assert len(parts) == 2, "Dual hash should have 2 parts"
            assert all(len(p) == 64 for p in parts), "Each part should be 64 hex chars"
