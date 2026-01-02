"""Offline mode CLI commands."""
import click

from offline import queue, sync
from offline.merkle_local import build_local_merkle
from .output import print_json, print_error, print_success


@click.group()
def offline():
    """Offline mode commands."""
    pass


@offline.command()
def status():
    """Show offline queue status."""
    try:
        sync_status = queue.get_sync_status()
        sync_status["connected"] = sync.is_connected()
        print_json(sync_status)
    except Exception as e:
        print_error(f"Status check failed: {e}")


@offline.command('queue')
@click.option('--limit', '-n', default=10, help='Number of receipts to show')
def show_queue(limit: int):
    """List pending receipts in queue."""
    try:
        receipts = queue.peek_queue(limit)

        if not receipts:
            click.echo("Queue is empty")
            return

        click.echo(f"Showing {len(receipts)} of {queue.get_queue_size()} pending receipts:\n")

        for i, r in enumerate(receipts):
            seq = r.get("offline_metadata", {}).get("local_sequence_id", "?")
            rtype = r.get("receipt_type", "unknown")
            ts = r.get("ts", "unknown")
            click.echo(f"  [{seq}] {rtype} @ {ts}")

    except Exception as e:
        print_error(f"Queue list failed: {e}")


@offline.command('sync')
@click.option('--force', is_flag=True, help='Force sync attempt even if not connected')
def do_sync(force: bool):
    """Sync offline queue to main ledger."""
    try:
        if not sync.is_connected() and not force:
            print_error("Not connected. Use --force to attempt anyway.")
            return

        result = sync.full_sync()

        if result.get("success"):
            print_success(f"Synced {result.get('synced_count', 0)} receipts")
            print_json(result)
        else:
            print_error(f"Sync failed: {result.get('reason')}")
            print_json(result)

    except Exception as e:
        print_error(f"Sync failed: {e}")


@offline.command()
def merkle():
    """Show local Merkle root of queued receipts."""
    try:
        merkle_root = queue.get_local_merkle_root()

        if merkle_root:
            result = {
                "local_merkle_root": merkle_root,
                "queue_size": queue.get_queue_size(),
            }
            print_json(result)
        else:
            click.echo("Queue is empty, no Merkle root")

    except Exception as e:
        print_error(f"Merkle computation failed: {e}")


@offline.command()
def clear():
    """Clear offline queue (use after manual sync)."""
    try:
        size = queue.get_queue_size()
        if size == 0:
            click.echo("Queue already empty")
            return

        if click.confirm(f"Clear {size} pending receipts?"):
            queue.clear_queue()
            print_success("Queue cleared")

    except Exception as e:
        print_error(f"Clear failed: {e}")


@offline.command()
def connected():
    """Check if main ledger is reachable."""
    try:
        is_connected = sync.is_connected()
        result = {
            "connected": is_connected,
            "status": "online" if is_connected else "offline",
        }
        print_json(result)
    except Exception as e:
        print_error(f"Connection check failed: {e}")


@offline.command()
def tree():
    """Show full Merkle tree structure for queued receipts."""
    try:
        receipts = queue.get_all_queued()

        if not receipts:
            click.echo("Queue is empty")
            return

        tree = build_local_merkle(receipts)

        result = {
            "root": tree["root"],
            "leaf_count": tree["leaf_count"],
            "tree_levels": len(tree["tree"]),
        }
        print_json(result)

    except Exception as e:
        print_error(f"Tree build failed: {e}")
