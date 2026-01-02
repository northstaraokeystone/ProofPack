"""
Entry point for running ProofPack as a module.

Usage:
    python -m proofpack [command] [options]

Example:
    python -m proofpack ledger ingest data.json
    python -m proofpack anchor prove --tenant my_tenant
    python -m proofpack gate check --confidence 0.85
"""

from proofpack.cli.main import cli

if __name__ == "__main__":
    cli()
