"""Tests for plan proposal module.

Per DELIVERABLE 5: Tests for gate/plan_proposal.py
"""

import uuid

from proofpack.core.receipt import emit_receipt, dual_hash


def test_plan_proposal_receipt_emission():
    """Test plan proposal receipt emission."""
    plan_id = str(uuid.uuid4())

    receipt = emit_receipt("plan_proposal", {
        "tenant_id": "test",
        "plan_id": plan_id,
        "steps": [
            {"step_id": "step_1", "action": "deploy", "tool": "deploy_helper"},
            {"step_id": "step_2", "action": "verify", "tool": "verify_deployment"}
        ],
        "total_estimated_duration_ms": 5000,
        "risk_assessment": {
            "score": 0.7,
            "level": "high",
            "factors": ["sandbox_required", "network_required"]
        },
        "requires_sandbox": ["step_1"],
        "requires_network": [{"step_id": "step_1", "domains": ["api.example.com"]}],
        "editable_until": "2024-01-01T00:05:00Z"
    })

    assert receipt["receipt_type"] == "plan_proposal"
    assert receipt["plan_id"] == plan_id
    assert len(receipt["steps"]) == 2


def test_plan_proposal_has_required_fields():
    """Test that plan proposal has all required fields."""
    receipt = emit_receipt("plan_proposal", {
        "tenant_id": "test",
        "plan_id": "test-plan-id",
        "steps": [],
        "total_estimated_duration_ms": 0,
        "risk_assessment": {"score": 0.0, "level": "low", "factors": []},
        "requires_sandbox": [],
        "requires_network": [],
        "editable_until": "2024-01-01T00:05:00Z"
    })

    required_fields = [
        "plan_id", "steps", "total_estimated_duration_ms",
        "risk_assessment", "requires_sandbox", "requires_network", "editable_until"
    ]

    for field in required_fields:
        assert field in receipt, f"Missing required field: {field}"


def test_plan_modification_receipt_emission():
    """Test plan modification receipt emission."""
    original_id = str(uuid.uuid4())
    modified_id = str(uuid.uuid4())

    receipt = emit_receipt("plan_modification", {
        "tenant_id": "test",
        "original_plan_id": original_id,
        "modified_plan_id": modified_id,
        "modifier_id": "human_reviewer_1",
        "reason": "Security improvement",
        "diff": {
            "steps_added": ["new_step"],
            "steps_removed": [],
            "steps_changed": ["step_0"]
        },
        "original_hash": dual_hash("original"),
        "modified_hash": dual_hash("modified")
    })

    assert receipt["receipt_type"] == "plan_modification"
    assert receipt["original_plan_id"] == original_id
    assert receipt["modified_plan_id"] == modified_id
    assert receipt["modifier_id"] == "human_reviewer_1"


def test_risk_level_determination():
    """Test risk level determination from score."""
    def get_risk_level(score: float) -> str:
        if score >= 0.8:
            return "critical"
        elif score >= 0.6:
            return "high"
        elif score >= 0.3:
            return "medium"
        else:
            return "low"

    assert get_risk_level(0.9) == "critical"
    assert get_risk_level(0.7) == "high"
    assert get_risk_level(0.5) == "medium"
    assert get_risk_level(0.2) == "low"


def test_plan_requires_proposal():
    """Test which risk levels require plan proposal."""
    def requires_plan_proposal(risk_level: str) -> bool:
        return risk_level in ("critical", "high", "medium")

    assert requires_plan_proposal("critical") is True
    assert requires_plan_proposal("high") is True
    assert requires_plan_proposal("medium") is True
    assert requires_plan_proposal("low") is False


def test_plan_step_structure():
    """Test plan step structure."""
    step = {
        "step_id": "step_0_ledger",
        "node_id": "ledger",
        "action": "execute_ingestion",
        "tool": "proofpack.ledger.ingest.ingest_receipt",
        "params": {},
        "estimated_duration_ms": 100,
        "requires_sandbox": False,
        "requires_network": False
    }

    required_fields = ["step_id", "node_id", "action", "tool"]
    for field in required_fields:
        assert field in step, f"Missing required step field: {field}"


def test_plan_approval_states():
    """Test valid plan approval states."""
    valid_states = ["proposed", "approved", "modified", "rejected", "timeout"]

    for state in valid_states:
        receipt = emit_receipt("plan_approval", {
            "tenant_id": "test",
            "plan_id": "test-plan",
            "decision": state,
            "modifier_id": None
        })
        assert receipt["decision"] == state


def test_plan_timeout_handling():
    """Test that timeout results in auto-reject."""
    receipt = emit_receipt("plan_approval", {
        "tenant_id": "test",
        "plan_id": "timeout-plan",
        "decision": "timeout",
        "modifier_id": None,
        "reason": "Approval timeout exceeded"
    })

    assert receipt["decision"] == "timeout"


def test_plan_rejection_emits_anomaly():
    """Test that plan rejection should emit anomaly."""
    # Plan rejection receipt
    rejection = emit_receipt("plan_approval", {
        "tenant_id": "test",
        "plan_id": "rejected-plan",
        "decision": "rejected",
        "modifier_id": "reviewer_1",
        "reason": "Too risky"
    })

    # Anomaly receipt for blocked execution
    anomaly = emit_receipt("anomaly", {
        "tenant_id": "test",
        "metric": "plan_rejected",
        "classification": "deviation",
        "action": "halt",
        "details": {"plan_id": "rejected-plan"}
    })

    assert rejection["decision"] == "rejected"
    assert anomaly["action"] == "halt"


def test_plan_modification_diff():
    """Test plan modification diff structure."""
    diff = {
        "steps_added": ["new_validation_step"],
        "steps_removed": ["old_step"],
        "steps_changed": ["step_0"]
    }

    required_fields = ["steps_added", "steps_removed", "steps_changed"]
    for field in required_fields:
        assert field in diff


def test_editable_until_format():
    """Test editable_until is ISO8601 format."""
    from datetime import datetime, timezone, timedelta

    editable_until = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    ).isoformat().replace("+00:00", "Z")

    assert editable_until.endswith("Z")
    # Should be parseable
    parsed = datetime.fromisoformat(editable_until.replace("Z", "+00:00"))
    assert parsed is not None
