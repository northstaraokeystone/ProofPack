"""Economic integration CLI commands."""
import json

import click

from proofpack.economic import (
    calculate_payment,
    evaluate_slo,
    export_for_payment_system,
    generate_payment_receipt,
    get_pending_payments,
)

from .output import print_error, print_json, print_success


@click.group()
def economic():
    """Economic integration commands."""
    pass


@economic.command()
@click.argument('receipt_file', type=click.Path(exists=True))
@click.option('--config', '-c', type=click.Path(exists=True),
              help='SLO configuration JSON file')
def evaluate(receipt_file: str, config: str):
    """Evaluate SLO status for receipt.

    RECEIPT_FILE: Path to receipt JSON file
    """
    try:
        with open(receipt_file) as f:
            receipt = json.load(f)

        slo_config = None
        if config:
            with open(config) as f:
                slo_config = json.load(f)

        status = evaluate_slo(receipt, slo_config)
        payment = calculate_payment(receipt)

        result = {
            "file": receipt_file,
            "receipt_type": receipt.get("receipt_type"),
            "slo_status": status,
            "payment": payment,
        }
        print_json(result)

    except Exception as e:
        print_error(f"Evaluation failed: {e}")


@economic.command()
@click.argument('receipts_file', type=click.Path(exists=True))
@click.option('--format', 'file_format', default='jsonl',
              type=click.Choice(['json', 'jsonl']),
              help='Input file format')
@click.option('--output', '-o', type=click.Path(),
              help='Output file for payment batch')
def export(receipts_file: str, file_format: str, output: str):
    """Export payment-eligible receipts as batch.

    RECEIPTS_FILE: Path to file containing receipts
    """
    try:
        receipts = []
        with open(receipts_file) as f:
            if file_format == 'jsonl':
                for line in f:
                    if line.strip():
                        receipts.append(json.loads(line))
            else:
                receipts = json.load(f)

        batch = export_for_payment_system(receipts)

        if output:
            with open(output, 'w') as f:
                json.dump(batch, f, indent=2)
            print_success(f"Payment batch written to {output}")
            click.echo(f"  Total: ${batch['total_amount_usd']:.6f}")
            click.echo(f"  Eligible: {batch['eligible_count']}/{batch['receipt_count']}")
        else:
            print_json(batch)

    except Exception as e:
        print_error(f"Export failed: {e}")


@economic.command()
@click.argument('receipts_file', type=click.Path(exists=True))
@click.option('--format', 'file_format', default='jsonl',
              type=click.Choice(['json', 'jsonl']),
              help='Input file format')
def pending(receipts_file: str, file_format: str):
    """List payment-pending receipts.

    RECEIPTS_FILE: Path to file containing receipts
    """
    try:
        receipts = []
        with open(receipts_file) as f:
            if file_format == 'jsonl':
                for line in f:
                    if line.strip():
                        receipts.append(json.loads(line))
            else:
                receipts = json.load(f)

        pending_list = get_pending_payments(receipts)

        click.echo(f"Found {len(pending_list)} payment-eligible receipts:\n")

        total = 0.0
        for item in pending_list:
            receipt = item["receipt"]
            eval_result = item["evaluation"]
            amount = eval_result.get("payment_amount_usd", 0)
            total += amount

            rtype = receipt.get("receipt_type", "unknown")
            status = eval_result.get("slo_status", "unknown")
            click.echo(f"  {rtype}: ${amount:.6f} (SLO: {status})")

        click.echo(f"\nTotal pending: ${total:.6f}")

    except Exception as e:
        print_error(f"Pending check failed: {e}")


@economic.command()
@click.argument('receipts_file', type=click.Path(exists=True))
@click.option('--format', 'file_format', default='jsonl',
              type=click.Choice(['json', 'jsonl']),
              help='Input file format')
def summary(receipts_file: str, file_format: str):
    """Show economic summary for receipts.

    RECEIPTS_FILE: Path to file containing receipts
    """
    try:
        receipts = []
        with open(receipts_file) as f:
            if file_format == 'jsonl':
                for line in f:
                    if line.strip():
                        receipts.append(json.loads(line))
            else:
                receipts = json.load(f)

        stats = {
            "total_receipts": len(receipts),
            "met": 0,
            "failed": 0,
            "pending": 0,
            "exempt": 0,
            "total_eligible_usd": 0.0,
            "total_withheld_usd": 0.0,
        }

        for receipt in receipts:
            status = evaluate_slo(receipt)
            payment = calculate_payment(receipt)

            stats[status] += 1

            if payment.get("payment_eligible"):
                stats["total_eligible_usd"] += payment.get("payment_amount_usd", 0)
            else:
                stats["total_withheld_usd"] += payment.get("base_amount_usd", 0)

        stats["total_eligible_usd"] = round(stats["total_eligible_usd"], 6)
        stats["total_withheld_usd"] = round(stats["total_withheld_usd"], 6)

        print_json(stats)

    except Exception as e:
        print_error(f"Summary failed: {e}")


@economic.command()
@click.argument('receipt_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(),
              help='Output file for payment receipt')
def generate(receipt_file: str, output: str):
    """Generate payment eligibility receipt.

    RECEIPT_FILE: Path to receipt JSON file
    """
    try:
        with open(receipt_file) as f:
            receipt = json.load(f)

        evaluation = calculate_payment(receipt)
        payment_receipt = generate_payment_receipt(receipt, evaluation)

        if output:
            with open(output, 'w') as f:
                json.dump(payment_receipt, f, indent=2)
            print_success(f"Payment receipt written to {output}")
        else:
            print_json(payment_receipt)

    except Exception as e:
        print_error(f"Generate failed: {e}")
