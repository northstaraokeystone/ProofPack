"""Privacy CLI commands."""
import json
import click

from privacy import (
    redact_receipt,
    verify_redaction,
    get_public_view,
    prepare_for_audit,
)
from .output import print_json, print_error, print_success


@click.group()
def privacy():
    """Privacy and redaction commands."""
    pass


@privacy.command()
@click.argument('receipt_file', type=click.Path(exists=True))
@click.option('--fields', '-f', required=True,
              help='Comma-separated list of fields to redact')
@click.option('--reason', '-r', default='proprietary',
              type=click.Choice(['proprietary', 'pii', 'classified', 'regulatory']),
              help='Reason for redaction')
@click.option('--output', '-o', type=click.Path(),
              help='Output file (defaults to stdout)')
def redact(receipt_file: str, fields: str, reason: str, output: str):
    """Redact specified fields from receipt.

    RECEIPT_FILE: Path to receipt JSON file
    """
    try:
        with open(receipt_file, 'r') as f:
            receipt = json.load(f)

        fields_list = [f.strip() for f in fields.split(',')]
        redacted = redact_receipt(receipt, fields_list, reason)

        if output:
            with open(output, 'w') as f:
                json.dump(redacted, f, indent=2)
            print_success(f"Redacted receipt written to {output}")
        else:
            print_json(redacted)

    except ValueError as e:
        print_error(f"Redaction failed: {e}")
    except Exception as e:
        print_error(f"Error: {e}")


@privacy.command()
@click.argument('original_hash')
@click.argument('redacted_file', type=click.Path(exists=True))
def verify(original_hash: str, redacted_file: str):
    """Verify redacted receipt structure.

    ORIGINAL_HASH: Original receipt's payload_hash
    REDACTED_FILE: Path to redacted receipt JSON file
    """
    try:
        with open(redacted_file, 'r') as f:
            redacted = json.load(f)

        is_valid = verify_redaction(original_hash, redacted)

        if is_valid:
            print_success("Redaction structure is valid")
        else:
            print_error("Redaction structure is invalid")

        result = {
            "original_hash": original_hash,
            "valid": is_valid,
            "privacy_level": redacted.get("privacy_level"),
            "redacted_fields": redacted.get("redacted_fields", []),
        }
        print_json(result)

    except Exception as e:
        print_error(f"Verification failed: {e}")


@privacy.command()
@click.argument('receipt_file', type=click.Path(exists=True))
@click.option('--level', 'audit_level', default='RNES-AUDIT',
              type=click.Choice(['RNES-CORE', 'RNES-AUDIT', 'RNES-FULL']),
              help='Audit level for output')
def audit(receipt_file: str, audit_level: str):
    """Show audit-safe view of receipt.

    RECEIPT_FILE: Path to receipt JSON file
    """
    try:
        with open(receipt_file, 'r') as f:
            receipt = json.load(f)

        audit_view = prepare_for_audit(receipt, audit_level)
        print_json(audit_view)

    except Exception as e:
        print_error(f"Audit view failed: {e}")


@privacy.command()
@click.argument('receipt_file', type=click.Path(exists=True))
def public(receipt_file: str):
    """Show public-only view of receipt.

    RECEIPT_FILE: Path to receipt JSON file
    """
    try:
        with open(receipt_file, 'r') as f:
            receipt = json.load(f)

        public_view = get_public_view(receipt)
        print_json(public_view)

    except Exception as e:
        print_error(f"Public view failed: {e}")


@privacy.command()
@click.argument('receipt_file', type=click.Path(exists=True))
def status(receipt_file: str):
    """Show privacy status of receipt.

    RECEIPT_FILE: Path to receipt JSON file
    """
    try:
        with open(receipt_file, 'r') as f:
            receipt = json.load(f)

        result = {
            "file": receipt_file,
            "privacy_level": receipt.get("privacy_level", "public"),
            "redacted_fields": receipt.get("redacted_fields", []),
            "public_fields": receipt.get("public_fields", []),
            "has_disclosure_proof": "disclosure_proof" in receipt,
        }
        print_json(result)

    except Exception as e:
        print_error(f"Status check failed: {e}")
