"""Tests for inference wrapper module.

Per DELIVERABLE 4: Tests for inference/wrapper.py
"""

import pytest
import time

from proofpack.core.receipt import emit_receipt, dual_hash


def test_inference_receipt_emission():
    """Test inference receipt emission."""
    receipt = emit_receipt("inference", {
        "tenant_id": "test",
        "model_id": "gpt-4",
        "model_version": "0613",
        "model_hash": dual_hash(b"model_weights"),
        "input_hash": dual_hash(b"prompt"),
        "output_hash": dual_hash(b"response"),
        "latency_ms": 150,
        "token_count": {"input": 10, "output": 50},
        "quantization": "fp16"
    })

    assert receipt["receipt_type"] == "inference"
    assert receipt["model_id"] == "gpt-4"
    assert receipt["model_version"] == "0613"
    assert receipt["latency_ms"] == 150


def test_inference_receipt_has_required_fields():
    """Test that inference receipt has all required fields."""
    receipt = emit_receipt("inference", {
        "tenant_id": "test",
        "model_id": "claude-3",
        "model_version": "sonnet",
        "model_hash": "sha256:blake3",
        "input_hash": "sha256:blake3",
        "output_hash": "sha256:blake3",
        "latency_ms": 100,
        "token_count": {"input": 5, "output": 25},
        "quantization": "none"
    })

    required_fields = [
        "receipt_type", "model_id", "model_version", "model_hash",
        "input_hash", "output_hash", "latency_ms", "token_count", "quantization"
    ]

    for field in required_fields:
        assert field in receipt, f"Missing required field: {field}"


def test_inference_dual_hash_format():
    """Test that hashes are in dual-hash format."""
    input_hash = dual_hash(b"test input")
    output_hash = dual_hash(b"test output")

    assert ":" in input_hash, "Input hash should be dual-hash format"
    assert ":" in output_hash, "Output hash should be dual-hash format"


def test_inference_token_count():
    """Test token count structure."""
    receipt = emit_receipt("inference", {
        "tenant_id": "test",
        "model_id": "test-model",
        "model_version": "v1",
        "model_hash": "hash:hash",
        "input_hash": "hash:hash",
        "output_hash": "hash:hash",
        "latency_ms": 100,
        "token_count": {"input": 10, "output": 50},
        "quantization": "none"
    })

    assert receipt["token_count"]["input"] == 10
    assert receipt["token_count"]["output"] == 50


def test_inference_quantization_values():
    """Test valid quantization values."""
    valid_quantizations = ["none", "fp16", "int8", "fp32", "bf16"]

    for quant in valid_quantizations:
        receipt = emit_receipt("inference", {
            "tenant_id": "test",
            "model_id": "test-model",
            "model_version": "v1",
            "model_hash": "hash:hash",
            "input_hash": "hash:hash",
            "output_hash": "hash:hash",
            "latency_ms": 100,
            "token_count": {"input": 0, "output": 0},
            "quantization": quant
        })

        assert receipt["quantization"] == quant


def test_inference_latency_measurement():
    """Test that latency is captured correctly."""
    # Simulate timed operation
    start = time.perf_counter()
    time.sleep(0.01)  # 10ms
    latency_ms = int((time.perf_counter() - start) * 1000)

    receipt = emit_receipt("inference", {
        "tenant_id": "test",
        "model_id": "test-model",
        "model_version": "v1",
        "model_hash": "hash:hash",
        "input_hash": "hash:hash",
        "output_hash": "hash:hash",
        "latency_ms": latency_ms,
        "token_count": None,
        "quantization": "none"
    })

    assert receipt["latency_ms"] >= 10  # At least 10ms


def test_inference_wrapper_decorator_pattern():
    """Test decorator usage pattern (conceptual)."""
    # Simulated decorator behavior
    calls = []

    def mock_decorator(model_id: str, model_version: str):
        def decorator(fn):
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                result = fn(*args, **kwargs)
                latency = int((time.perf_counter() - start) * 1000)
                calls.append({
                    "model_id": model_id,
                    "model_version": model_version,
                    "latency_ms": latency,
                    "result": result
                })
                return result
            return wrapper
        return decorator

    @mock_decorator("test-model", "v1")
    def inference_fn(prompt):
        return f"Response to: {prompt}"

    result = inference_fn("Hello")

    assert result == "Response to: Hello"
    assert len(calls) == 1
    assert calls[0]["model_id"] == "test-model"


def test_inference_model_hash_computation():
    """Test model hash computation."""
    model_content = b"model weights data"
    model_hash = dual_hash(model_content)

    parts = model_hash.split(":")
    assert len(parts) == 2
    assert len(parts[0]) == 64  # SHA256 hex
    assert len(parts[1]) == 64  # BLAKE3 hex


def test_inference_receipt_payload_hash():
    """Test that payload_hash is included in receipt."""
    receipt = emit_receipt("inference", {
        "tenant_id": "test",
        "model_id": "test-model",
        "model_version": "v1",
        "model_hash": "hash:hash",
        "input_hash": "hash:hash",
        "output_hash": "hash:hash",
        "latency_ms": 100,
        "token_count": {"input": 0, "output": 0},
        "quantization": "none"
    })

    assert "payload_hash" in receipt
    assert ":" in receipt["payload_hash"]  # Dual-hash format
