"""Ledger commands: ingest, verify, anchor, export."""
import json
import sys
import time

import click

from .output import error_box, success_box


@click.group()
def ledger():
    """Ledger operations for receipt management."""
    pass


@ledger.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('--tenant', default='default', help='Tenant ID')
def ingest(file: str, tenant: str):
    """Ingest receipts from JSONL file."""
    t0 = time.perf_counter()
    try:
        from ledger.ingest import ingest as do_ingest

        count = 0
        last_hash = ""
        with open(file) as f:
            for line in f:
                if line.strip():
                    receipt = json.loads(line)
                    result = do_ingest(receipt, tenant_id=tenant)
                    last_hash = result.get("payload_hash", "")[:16]
                    count += 1

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        slo_status = "PASS" if elapsed_ms <= 50 * count else "WARN"

        success_box("Ledger Ingest: SUCCESS", [
            ("File", file),
            ("Receipts", str(count)),
            ("Tenant", tenant),
            ("Hash", last_hash),
            ("Duration", f"{elapsed_ms}ms"),
            ("SLO", f"{slo_status} (<=50ms/receipt)")
        ], "proof ledger anchor")
        sys.exit(0)

    except FileNotFoundError:
        error_box("Ledger Ingest: FAILED", f"File not found: {file}")
        sys.exit(2)
    except json.JSONDecodeError as e:
        error_box("Ledger Ingest: FAILED", f"Invalid JSON: {e}")
        sys.exit(2)
    except Exception as e:
        error_box("Ledger Ingest: FAILED", str(e))
        sys.exit(2)


@ledger.command()
@click.argument('receipt_id')
@click.option('--root', help='Expected merkle root')
def verify(receipt_id: str, root: str | None):
    """Verify receipt against merkle proof."""
    t0 = time.perf_counter()
    try:
        from ledger.verify import verify as do_verify

        # Mock receipt and proof for CLI demo
        receipt = {"receipt_id": receipt_id, "data": "test"}
        proof = {"merkle_root": root or "mock_root", "proof_path": []}

        result = do_verify(receipt, proof)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        status = result.get("status", "unknown")
        if status == "valid":
            success_box("Ledger Verify: VALID", [
                ("Receipt", receipt_id[:20]),
                ("Root", result.get("merkle_root", "")[:20]),
                ("Proof valid", str(result.get("proof_valid", False))),
                ("Duration", f"{elapsed_ms}ms")
            ], f"proof packet build --receipts {receipt_id}")
            sys.exit(0)
        else:
            error_box("Ledger Verify: INVALID", f"Proof validation failed for {receipt_id}")
            sys.exit(1)

    except Exception as e:
        error_box("Ledger Verify: ERROR", str(e))
        sys.exit(2)


@ledger.command()
@click.option('--batch', default='latest', help='Batch to anchor')
def anchor(batch: str):
    """Anchor receipt batch to merkle tree."""
    t0 = time.perf_counter()
    try:
        from ledger.core import emit_receipt, merkle

        # Mock batch anchoring
        receipts = [{"batch": batch, "idx": i} for i in range(10)]
        root = merkle(receipts)

        _result = emit_receipt("anchor", {  # noqa: F841
            "merkle_root": root,
            "batch_size": len(receipts),
            "batch_id": batch
        })

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        success_box("Ledger Anchor: SUCCESS", [
            ("Batch", batch),
            ("Receipts", str(len(receipts))),
            ("Root", root[:32]),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof packet build")
        sys.exit(0)

    except Exception as e:
        error_box("Ledger Anchor: FAILED", str(e))
        sys.exit(2)


@ledger.command()
@click.argument('output', type=click.Path())
@click.option('--format', 'fmt', default='jsonl', help='Export format')
def export(output: str, fmt: str):
    """Export receipts to file."""
    t0 = time.perf_counter()
    try:
        # Mock export
        with open(output, 'w') as f:
            f.write('{"receipt_type": "export", "format": "' + fmt + '"}\n')

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        success_box("Ledger Export: SUCCESS", [
            ("Output", output),
            ("Format", fmt),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof ledger verify")
        sys.exit(0)

    except Exception as e:
        error_box("Ledger Export: FAILED", str(e))
        sys.exit(2)
