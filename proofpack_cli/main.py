"""ProofPack CLI entry point - assembles all command groups."""
import click

from . import __version__
from .ledger_cmd import ledger
from .brief_cmd import brief
from .packet_cmd import packet
from .detect_cmd import detect
from .anchor_cmd import anchor
from .loop_cmd import loop
from .compose_cmd import compose


@click.group()
@click.version_option(version=__version__)
def cli():
    """ProofPack: Receipts all the way down."""
    pass


cli.add_command(ledger)
cli.add_command(brief)
cli.add_command(packet)
cli.add_command(detect)
cli.add_command(anchor)
cli.add_command(loop)
cli.add_command(compose)


if __name__ == "__main__":
    cli()
