"""RNES compliance CLI commands."""
import json
import click

from proofpack.privacy import check_rnes_compliance, prepare_for_audit
from .output import print_json, print_table, print_error, print_success


@click.group()
def rnes():
    """RNES compliance commands."""
    pass


@rnes.command()
@click.argument('receipt_file', type=click.Path(exists=True))
def validate(receipt_file: str):
    """Validate receipt against RNES standard.

    RECEIPT_FILE: Path to receipt JSON file
    """
    try:
        with open(receipt_file, 'r') as f:
            receipt = json.load(f)

        level, violations = check_rnes_compliance(receipt)

        if violations:
            print_error(f"Non-compliant: {len(violations)} violation(s)")
            for v in violations:
                click.echo(f"  - {v}")
        else:
            print_success(f"Compliant at level: {level}")

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
    except Exception as e:
        print_error(f"Validation failed: {e}")


@rnes.command()
@click.argument('receipt_file', type=click.Path(exists=True))
def level(receipt_file: str):
    """Show RNES compliance level for receipt.

    RECEIPT_FILE: Path to receipt JSON file
    """
    try:
        with open(receipt_file, 'r') as f:
            receipt = json.load(f)

        compliance_level, _ = check_rnes_compliance(receipt)

        result = {
            "file": receipt_file,
            "compliance_level": compliance_level,
            "receipt_type": receipt.get("receipt_type", "unknown"),
        }

        print_json(result)

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
    except Exception as e:
        print_error(f"Check failed: {e}")


@rnes.command()
@click.argument('receipt_file', type=click.Path(exists=True))
@click.option('--level', 'audit_level', default='RNES-AUDIT',
              type=click.Choice(['RNES-CORE', 'RNES-AUDIT', 'RNES-FULL']),
              help='Audit level to format for')
def audit(receipt_file: str, audit_level: str):
    """Format receipt for audit at specified level.

    RECEIPT_FILE: Path to receipt JSON file
    """
    try:
        with open(receipt_file, 'r') as f:
            receipt = json.load(f)

        audit_receipt = prepare_for_audit(receipt, audit_level)
        print_json(audit_receipt)

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
    except Exception as e:
        print_error(f"Audit format failed: {e}")


@rnes.command()
@click.argument('receipts_file', type=click.Path(exists=True))
@click.option('--format', 'file_format', default='jsonl',
              type=click.Choice(['json', 'jsonl']),
              help='Input file format')
def batch_validate(receipts_file: str, file_format: str):
    """Validate batch of receipts.

    RECEIPTS_FILE: Path to file containing receipts
    """
    try:
        receipts = []
        with open(receipts_file, 'r') as f:
            if file_format == 'jsonl':
                for line in f:
                    if line.strip():
                        receipts.append(json.loads(line))
            else:
                receipts = json.load(f)

        results = {
            "total": len(receipts),
            "RNES-FULL": 0,
            "RNES-AUDIT": 0,
            "RNES-CORE": 0,
            "NON-COMPLIANT": 0,
            "violations": [],
        }

        for i, receipt in enumerate(receipts):
            level, violations = check_rnes_compliance(receipt)
            results[level] += 1
            if violations:
                results["violations"].append({
                    "index": i,
                    "receipt_type": receipt.get("receipt_type"),
                    "violations": violations
                })

        print_json(results)

    except Exception as e:
        print_error(f"Batch validation failed: {e}")
