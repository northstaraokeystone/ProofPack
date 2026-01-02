"""Inference Wrapper Module - Receipt emission for ML model calls.

Per CLAUDEME §14: Every LLM/ML inference call MUST emit inference_receipt.
No exceptions.

Provides:
    - Decorator style: @receipts_inference(model_id, model_version)
    - Wrapper style: wrap_inference(model_id, version, fn)

Works with any inference function (local, API, Triton, etc.)
"""

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any

from proofpack.core.receipt import dual_hash, emit_receipt


@dataclass
class InferenceMetadata:
    """Metadata for an inference call."""
    model_id: str
    model_version: str
    model_hash: str
    quantization: str = "none"


# Cache for model hashes to avoid recomputing
_model_hash_cache: dict[str, str] = {}


def compute_model_hash(model_path: str | None = None, model_bytes: bytes | None = None) -> str:
    """Compute dual-hash of model weights or path.

    Args:
        model_path: Path to model file/directory
        model_bytes: Raw model bytes (alternative to path)

    Returns:
        Dual-hash string (SHA256:BLAKE3)

    If neither provided, returns placeholder hash.
    """
    if model_path:
        # Check cache first
        if model_path in _model_hash_cache:
            return _model_hash_cache[model_path]

        path = Path(model_path)
        if path.exists():
            if path.is_file():
                # Hash file contents
                with open(path, "rb") as f:
                    # Read in chunks for large files
                    hasher = hashlib.sha256()
                    while chunk := f.read(8192):
                        hasher.update(chunk)
                    model_hash = dual_hash(hasher.digest())
            else:
                # For directories, hash the listing
                files = sorted([str(f) for f in path.rglob("*") if f.is_file()])
                model_hash = dual_hash(json.dumps(files))
        else:
            # Path doesn't exist, use path string as identifier
            model_hash = dual_hash(model_path)

        _model_hash_cache[model_path] = model_hash
        return model_hash

    elif model_bytes:
        return dual_hash(model_bytes)

    else:
        # Placeholder for runtime-computed hash
        return dual_hash("RUNTIME_MODEL_HASH")


def emit_inference_receipt(
    model_id: str,
    model_version: str,
    model_hash: str,
    input_data: bytes | str,
    output_data: bytes | str,
    latency_ms: int,
    token_count: dict[str, int] | None = None,
    quantization: str = "none",
    tenant_id: str = "default"
) -> dict:
    """Emit inference receipt for ML model call.

    Per CLAUDEME §14: Every inference call emits receipt.

    Args:
        model_id: Model identifier (e.g., "gpt-4", "claude-3")
        model_version: Model version (e.g., "0613", "sonnet")
        model_hash: Dual-hash of model weights
        input_data: Input to model (prompt, features, etc.)
        output_data: Output from model (completion, predictions, etc.)
        latency_ms: Inference latency in milliseconds
        token_count: Optional dict with "input" and "output" token counts
        quantization: Quantization format (e.g., "fp16", "int8", "none")
        tenant_id: Tenant identifier

    Returns:
        Inference receipt dict
    """
    # Convert to bytes if needed
    if isinstance(input_data, str):
        input_data = input_data.encode("utf-8")
    if isinstance(output_data, str):
        output_data = output_data.encode("utf-8")

    return emit_receipt("inference", {
        "tenant_id": tenant_id,
        "model_id": model_id,
        "model_version": model_version,
        "model_hash": model_hash,
        "input_hash": dual_hash(input_data),
        "output_hash": dual_hash(output_data),
        "latency_ms": latency_ms,
        "token_count": token_count or {"input": 0, "output": 0},
        "quantization": quantization
    })


def wrap_inference(
    model_id: str,
    model_version: str,
    inference_fn: Callable[..., Any],
    model_hash: str | None = None,
    quantization: str = "none",
    tenant_id: str = "default"
) -> Callable[..., Any]:
    """Wrap an inference function to emit receipts automatically.

    Args:
        model_id: Model identifier
        model_version: Model version
        inference_fn: The inference function to wrap
        model_hash: Optional pre-computed model hash
        quantization: Quantization format
        tenant_id: Tenant identifier

    Returns:
        Wrapped function that emits inference_receipt

    Example:
        raw_inference = lambda x: model.predict(x)
        wrapped = wrap_inference("my-model", "v1", raw_inference)
        result = wrapped(input_data)  # Receipt automatically emitted
    """
    # Compute hash if not provided
    hash_to_use = model_hash or compute_model_hash()

    @wraps(inference_fn)
    def wrapper(*args, **kwargs) -> Any:
        # Serialize input
        input_repr = json.dumps({
            "args": [str(a) for a in args],
            "kwargs": {k: str(v) for k, v in kwargs.items()}
        }, sort_keys=True)

        # Time the inference
        start_time = time.perf_counter()
        result = inference_fn(*args, **kwargs)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Serialize output
        output_repr = json.dumps(result, default=str, sort_keys=True) if result else ""

        # Emit receipt
        emit_inference_receipt(
            model_id=model_id,
            model_version=model_version,
            model_hash=hash_to_use,
            input_data=input_repr,
            output_data=output_repr,
            latency_ms=latency_ms,
            token_count=None,  # Could extract from result if available
            quantization=quantization,
            tenant_id=tenant_id
        )

        return result

    return wrapper


def receipts_inference(
    model_id: str,
    model_version: str,
    model_hash: str | None = None,
    quantization: str = "none",
    tenant_id: str = "default"
) -> Callable:
    """Decorator to wrap inference functions with receipt emission.

    Per CLAUDEME §14: Every inference call MUST emit receipt.

    Args:
        model_id: Model identifier
        model_version: Model version
        model_hash: Optional pre-computed model hash
        quantization: Quantization format
        tenant_id: Tenant identifier

    Returns:
        Decorator function

    Example:
        @receipts_inference(model_id="gpt-4", model_version="0613")
        def call_llm(prompt: str) -> str:
            return openai.complete(prompt)

        # When called, receipt is automatically emitted
        result = call_llm("Hello, world!")
    """
    # Compute hash if not provided
    hash_to_use = model_hash or compute_model_hash()

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            # Serialize input
            input_repr = json.dumps({
                "args": [str(a) for a in args],
                "kwargs": {k: str(v) for k, v in kwargs.items()}
            }, sort_keys=True)

            # Time the inference
            start_time = time.perf_counter()
            result = fn(*args, **kwargs)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Serialize output
            output_repr = json.dumps(result, default=str, sort_keys=True) if result else ""

            # Try to extract token count if result is a dict with usage info
            token_count = None
            if isinstance(result, dict):
                usage = result.get("usage", {})
                if "prompt_tokens" in usage or "completion_tokens" in usage:
                    token_count = {
                        "input": usage.get("prompt_tokens", 0),
                        "output": usage.get("completion_tokens", 0)
                    }

            # Emit receipt
            emit_inference_receipt(
                model_id=model_id,
                model_version=model_version,
                model_hash=hash_to_use,
                input_data=input_repr,
                output_data=output_repr,
                latency_ms=latency_ms,
                token_count=token_count,
                quantization=quantization,
                tenant_id=tenant_id
            )

            return result

        return wrapper

    return decorator


class InferenceWrapper:
    """Class-based wrapper for inference functions.

    Alternative to decorator/function wrapper for more control.

    Example:
        wrapper = InferenceWrapper("claude-3", "sonnet")
        result, receipt = wrapper.call(model.generate, prompt="Hello")
    """

    def __init__(
        self,
        model_id: str,
        model_version: str,
        model_hash: str | None = None,
        quantization: str = "none",
        tenant_id: str = "default"
    ):
        self.model_id = model_id
        self.model_version = model_version
        self.model_hash = model_hash or compute_model_hash()
        self.quantization = quantization
        self.tenant_id = tenant_id

    def call(
        self,
        inference_fn: Callable[..., Any],
        *args,
        **kwargs
    ) -> tuple[Any, dict]:
        """Call inference function and emit receipt.

        Args:
            inference_fn: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Tuple of (result, receipt)
        """
        # Serialize input
        input_repr = json.dumps({
            "args": [str(a) for a in args],
            "kwargs": {k: str(v) for k, v in kwargs.items()}
        }, sort_keys=True)

        # Time the inference
        start_time = time.perf_counter()
        result = inference_fn(*args, **kwargs)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Serialize output
        output_repr = json.dumps(result, default=str, sort_keys=True) if result else ""

        # Emit receipt
        receipt = emit_inference_receipt(
            model_id=self.model_id,
            model_version=self.model_version,
            model_hash=self.model_hash,
            input_data=input_repr,
            output_data=output_repr,
            latency_ms=latency_ms,
            token_count=None,
            quantization=self.quantization,
            tenant_id=self.tenant_id
        )

        return result, receipt
