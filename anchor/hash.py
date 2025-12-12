"""Dual-hash cryptographic primitive. Belt and suspenders."""
import hashlib

try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False


def dual_hash(data: bytes | str) -> str:
    """SHA256:BLAKE3 - ALWAYS use this, never single hash.

    Returns format: "{sha256}:{blake3}"
    If blake3 unavailable: "{sha256}:{sha256}" (still dual format)
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    sha = hashlib.sha256(data).hexdigest()
    b3 = blake3.blake3(data).hexdigest() if HAS_BLAKE3 else sha

    return f"{sha}:{b3}"
