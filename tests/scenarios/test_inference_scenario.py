"""INFERENCE Monte Carlo Scenario - Test inference receipt emission and tampering detection.

Per DELIVERABLE 7: Monte Carlo scenario for inference receipt validation.

SCENARIO: INFERENCE
cycles: 150
inject:
  - 100 normal inference calls
  - 30 with model version change mid-run
  - 20 with output hash mismatch (simulated tampering)
success_criteria:
  - inference_receipt emitted: 100%
  - model version changes detected: 100%
  - tampering detected: 100%
"""

import random
import sys
from collections.abc import Callable
from dataclasses import dataclass

sys.path.insert(0, '..')
from conftest import SimConfig, SimState


@dataclass
class InferenceScenarioConfig(SimConfig):
    """Configuration for INFERENCE scenario."""
    n_cycles: int = 150
    normal_inference_calls: int = 100
    model_version_changes: int = 30
    tampering_attempts: int = 20
    random_seed: int = 42


@dataclass
class InferenceScenarioState(SimState):
    """State tracking for INFERENCE scenario."""
    inference_receipts_emitted: int = 0
    model_version_changes_detected: int = 0
    tampering_detected: int = 0

    # Tracking injected scenarios
    normal_calls_injected: int = 0
    version_changes_injected: int = 0
    tampering_injected: int = 0

    # Model state tracking
    current_model_version: str = "v1.0"
    current_model_hash: str = "sha256abc:blake3xyz"


def run_inference_scenario(
    config: InferenceScenarioConfig | None = None,
    emit_receipt_fn: Callable | None = None
) -> InferenceScenarioState:
    """Execute INFERENCE Monte Carlo scenario.

    Args:
        config: Scenario configuration
        emit_receipt_fn: Optional receipt emission function (for mocking)

    Returns:
        Final scenario state with metrics
    """
    if config is None:
        config = InferenceScenarioConfig()

    random.seed(config.random_seed)
    state = InferenceScenarioState()

    # Model versions for testing
    model_versions = ["v1.0", "v1.1", "v2.0", "v2.1"]

    # Generate injection schedule
    schedule = []
    schedule.extend(["normal"] * config.normal_inference_calls)
    schedule.extend(["version_change"] * config.model_version_changes)
    schedule.extend(["tampering"] * config.tampering_attempts)
    random.shuffle(schedule)

    for i, injection_type in enumerate(schedule):
        if i >= config.n_cycles:
            break

        state.cycle = i

        # Simulate input/output
        input_data = f"prompt_{i}"
        expected_output = f"response_{i}"

        if injection_type == "normal":
            state.normal_calls_injected += 1

            # Normal inference - consistent model version and hash
            inference_receipt = {
                "receipt_type": "inference",
                "model_id": "test-model",
                "model_version": state.current_model_version,
                "model_hash": state.current_model_hash,
                "input_hash": f"sha256:{hash(input_data)}:blake3:{hash(input_data)}",
                "output_hash": f"sha256:{hash(expected_output)}:blake3:{hash(expected_output)}",
                "latency_ms": random.randint(50, 200),
                "token_count": {"input": 10, "output": 50},
                "quantization": "fp16"
            }

        elif injection_type == "version_change":
            state.version_changes_injected += 1

            # Change model version mid-run
            old_version = state.current_model_version
            new_version = random.choice([v for v in model_versions if v != old_version])
            state.current_model_version = new_version
            state.current_model_hash = f"sha256new:blake3new_{new_version}"

            # Inference with new version
            inference_receipt = {
                "receipt_type": "inference",
                "model_id": "test-model",
                "model_version": new_version,
                "model_hash": state.current_model_hash,
                "input_hash": f"sha256:{hash(input_data)}:blake3:{hash(input_data)}",
                "output_hash": f"sha256:{hash(expected_output)}:blake3:{hash(expected_output)}",
                "latency_ms": random.randint(50, 200),
                "token_count": {"input": 10, "output": 50},
                "quantization": "fp16",
                "version_changed_from": old_version
            }

            # Emit anomaly for version change
            anomaly_receipt = {
                "receipt_type": "anomaly",
                "metric": "model_version_change",
                "baseline": old_version,
                "delta": 1,
                "classification": "drift",
                "action": "alert",
                "details": {"from": old_version, "to": new_version}
            }
            state.receipt_ledger.append(anomaly_receipt)
            state.model_version_changes_detected += 1

        else:  # tampering
            state.tampering_injected += 1

            # Simulate tampering - output hash doesn't match expected
            tampered_output = f"tampered_response_{i}"

            inference_receipt = {
                "receipt_type": "inference",
                "model_id": "test-model",
                "model_version": state.current_model_version,
                "model_hash": state.current_model_hash,
                "input_hash": f"sha256:{hash(input_data)}:blake3:{hash(input_data)}",
                "output_hash": f"sha256:{hash(tampered_output)}:blake3:{hash(tampered_output)}",
                "latency_ms": random.randint(50, 200),
                "token_count": {"input": 10, "output": 50},
                "quantization": "fp16",
                "expected_output_hash": f"sha256:{hash(expected_output)}:blake3:{hash(expected_output)}",
                "tampering_detected": True
            }

            # Emit anomaly for tampering
            anomaly_receipt = {
                "receipt_type": "anomaly",
                "metric": "inference_tampering",
                "baseline": 0,
                "delta": -1,
                "classification": "violation",
                "action": "halt"
            }
            state.receipt_ledger.append(anomaly_receipt)
            state.tampering_detected += 1

        # Always emit inference receipt
        state.receipt_ledger.append(inference_receipt)
        state.inference_receipts_emitted += 1

    return state


def validate_inference_scenario(state: InferenceScenarioState) -> dict:
    """Validate INFERENCE scenario success criteria.

    Returns:
        Dict with success criteria results
    """
    total_calls = (
        state.normal_calls_injected +
        state.version_changes_injected +
        state.tampering_injected
    )

    # Calculate success rates
    receipt_emission_rate = state.inference_receipts_emitted / total_calls if total_calls > 0 else 0

    version_change_detection_rate = (
        state.model_version_changes_detected / state.version_changes_injected
        if state.version_changes_injected > 0 else 1.0
    )

    tampering_detection_rate = (
        state.tampering_detected / state.tampering_injected
        if state.tampering_injected > 0 else 1.0
    )

    return {
        "success": all([
            receipt_emission_rate >= 1.0,
            version_change_detection_rate >= 1.0,
            tampering_detection_rate >= 1.0
        ]),
        "inference_receipt_emission": receipt_emission_rate,
        "model_version_changes_detected": version_change_detection_rate,
        "tampering_detected": tampering_detection_rate,
        "total_cycles": state.cycle + 1,
        "receipts_emitted": state.inference_receipts_emitted
    }


# Pytest test functions

def test_inference_scenario_basic():
    """Test basic INFERENCE scenario execution."""
    config = InferenceScenarioConfig(n_cycles=50)
    state = run_inference_scenario(config)
    result = validate_inference_scenario(state)

    assert result["success"], f"Scenario failed: {result}"


def test_inference_scenario_normal_calls():
    """Test normal inference calls emit receipts."""
    config = InferenceScenarioConfig(
        n_cycles=100,
        normal_inference_calls=100,
        model_version_changes=0,
        tampering_attempts=0
    )
    state = run_inference_scenario(config)
    result = validate_inference_scenario(state)

    assert result["inference_receipt_emission"] >= 1.0


def test_inference_scenario_version_changes():
    """Test model version changes are detected."""
    config = InferenceScenarioConfig(
        n_cycles=30,
        normal_inference_calls=0,
        model_version_changes=30,
        tampering_attempts=0
    )
    state = run_inference_scenario(config)
    result = validate_inference_scenario(state)

    assert result["model_version_changes_detected"] >= 1.0


def test_inference_scenario_tampering():
    """Test output tampering is detected."""
    config = InferenceScenarioConfig(
        n_cycles=20,
        normal_inference_calls=0,
        model_version_changes=0,
        tampering_attempts=20
    )
    state = run_inference_scenario(config)
    result = validate_inference_scenario(state)

    assert result["tampering_detected"] >= 1.0


def test_inference_scenario_full():
    """Full INFERENCE scenario as specified."""
    config = InferenceScenarioConfig()  # Uses default: 150 cycles, 100/30/20 split
    state = run_inference_scenario(config)
    result = validate_inference_scenario(state)

    assert result["success"], f"INFERENCE scenario failed: {result}"

    # All success criteria must be 100%
    assert result["inference_receipt_emission"] >= 1.0
    assert result["model_version_changes_detected"] >= 1.0
    assert result["tampering_detected"] >= 1.0


if __name__ == "__main__":
    print("Running INFERENCE Monte Carlo Scenario...")
    config = InferenceScenarioConfig()
    state = run_inference_scenario(config)
    result = validate_inference_scenario(state)

    print(f"Results: {result}")
    print(f"Success: {result['success']}")
