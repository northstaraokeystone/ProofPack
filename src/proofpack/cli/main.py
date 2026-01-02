"""ProofPack CLI entry point - assembles all command groups."""
import click

from . import __version__
from .anchor_cmd import anchor
from .brief_cmd import brief
from .compose_cmd import compose
from .detect_cmd import detect
from .economic_cmd import economic
from .fallback_cmd import fallback
from .gate_cmd import gate
from .graph_cmd import graph
from .ledger_cmd import ledger
from .loop_cmd import loop
from .mcp_cmd import mcp
from .monte_cmd import monte
from .offline_cmd import offline
from .packet_cmd import packet
from .privacy_cmd import privacy
from .rnes_cmd import rnes
from .spawn_cmd import spawn


@click.group()
@click.version_option(version=__version__)
def cli():
    """ProofPack: RNES-compliant governance infrastructure."""
    pass


# v3.0 commands
cli.add_command(ledger)
cli.add_command(brief)
cli.add_command(packet)
cli.add_command(detect)
cli.add_command(anchor)
cli.add_command(loop)
cli.add_command(compose)
cli.add_command(gate)
cli.add_command(monte)
cli.add_command(spawn)

# v3.1 commands
cli.add_command(mcp)
cli.add_command(graph)
cli.add_command(fallback)

# v3.2 commands (Competitive Differentiation)
cli.add_command(rnes)
cli.add_command(privacy)
cli.add_command(offline)
cli.add_command(economic)


if __name__ == "__main__":
    cli()
