"""Hash utilities extending core.receipt.

Provides hash_to_position for extracting bit positions from dual-hash
for tree placement and routing.
"""
from ..core.receipt import dual_hash  # noqa: F401 - re-exported


def hash_to_position(h: str, depth: int) -> str:
    """Extract first depth bits from SHA256 portion of dual-hash.

    Uses the SHA256 portion (before the colon) and converts leading
    bytes to binary to get a bit string.

    Args:
        h: Dual-hash string in format 'sha256hex:blake3hex'
        depth: Number of bits to extract

    Returns:
        Binary string of length depth (e.g., '10110101')
    """
    # Extract SHA256 portion (before colon)
    sha256_hex = h.split(":")[0]

    # Convert hex to binary
    # Each hex digit = 4 bits, so we need ceil(depth/4) hex digits
    hex_chars_needed = (depth + 3) // 4
    hex_subset = sha256_hex[:hex_chars_needed]

    # Convert to binary, stripping '0b' prefix
    binary = bin(int(hex_subset, 16))[2:]

    # Pad with leading zeros to get full bit string
    binary = binary.zfill(hex_chars_needed * 4)

    # Return first depth bits
    return binary[:depth]
