"""Graph commands: status, query, backfill, episode, visualize."""
import sys
import time
import click
import json

from .output import success_box, error_box


@click.group()
def graph():
    """Temporal knowledge graph operations."""
    pass


@graph.command()
def status():
    """Show node/edge counts and last sync."""
    try:
        from proofpack.graph.backend import get_backend
        from proofpack.graph.sync import sync_status
        from proofpack.graph.index import get_index_stats

        backend = get_backend()
        sync = sync_status()
        index_stats = get_index_stats()

        success_box("Graph Status", [
            ("Nodes", str(backend.node_count())),
            ("Edges", str(backend.edge_count())),
            ("Initialized", str(sync.get("initialized", True))),
            ("Last Sync", f"{sync.get('last_sync_time', 0):.0f}"),
            ("Sync Position", str(sync.get("last_sync_position", 0))),
            ("Type Buckets", str(index_stats.get("type_count", 0))),
            ("Time Buckets", str(index_stats.get("time_bucket_count", 0))),
        ], "proof graph query \"what before X\"")

    except Exception as e:
        error_box("Graph Status: ERROR", str(e))
        sys.exit(2)


@graph.command()
@click.argument('query_text')
@click.option('--type', 'query_type', default='temporal',
              type=click.Choice(['lineage', 'temporal', 'match', 'causal']),
              help='Query type')
@click.option('--receipt-id', help='Receipt ID for lineage/causal queries')
@click.option('--start', 'start_time', help='Start time for temporal queries')
@click.option('--end', 'end_time', help='End time for temporal queries')
@click.option('--depth', default=10, help='Maximum depth for traversal')
def query(query_text: str, query_type: str, receipt_id: str,
          start_time: str, end_time: str, depth: int):
    """Run temporal query on the graph."""
    t0 = time.perf_counter()
    try:
        from proofpack.graph import query as graph_query

        if query_type == 'lineage':
            if not receipt_id:
                error_box("Query Error", "Receipt ID required for lineage query")
                sys.exit(1)
            result = graph_query.lineage(receipt_id, depth)

        elif query_type == 'causal':
            if not receipt_id:
                error_box("Query Error", "Receipt ID required for causal chain query")
                sys.exit(1)
            result = graph_query.causal_chain(receipt_id, depth)

        elif query_type == 'temporal':
            if not start_time or not end_time:
                error_box("Query Error", "Start and end times required for temporal query")
                sys.exit(1)
            result = graph_query.temporal(start_time, end_time)

        elif query_type == 'match':
            # Parse query_text as key=value pairs
            criteria = {}
            for pair in query_text.split():
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    criteria[k] = v
            result = graph_query.match(criteria)

        else:
            error_box("Query Error", f"Unknown query type: {query_type}")
            sys.exit(1)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        print(f"\n╭─ Graph Query Results ({query_type}) " + "─" * 30 + "╮")
        print(f"│ Query: {query_text[:50]:<52} │")
        print(f"│ Nodes found: {len(result.nodes):<48} │")
        print(f"│ Edges found: {len(result.edges):<48} │")
        print(f"│ Duration: {result.elapsed_ms:.1f}ms{' ' * 45}│")
        print("├" + "─" * 62 + "┤")

        for node in result.nodes[:10]:
            node_id = node.get('id', 'unknown')[:16]
            node_type = node.get('type', 'unknown')[:15]
            event_time = node.get('event_time', '')[:20]
            print(f"│ {node_id:<16} │ {node_type:<15} │ {event_time:<20} │")

        if len(result.nodes) > 10:
            print(f"│ ... and {len(result.nodes) - 10} more nodes{' ' * 40}│")

        print("╰" + "─" * 62 + "╯")
        print(f"Next: proof graph episode {receipt_id or '<receipt_id>'}")

    except Exception as e:
        error_box("Graph Query: ERROR", str(e))
        sys.exit(2)


@graph.command()
@click.option('--ledger', default='receipts.jsonl', help='Ledger file path')
def backfill(ledger: str):
    """Ingest historical receipts from ledger."""
    t0 = time.perf_counter()
    try:
        from proofpack.graph.sync import backfill as do_backfill

        click.echo(f"Backfilling from {ledger}...")

        result = do_backfill(ledger)

        if "error" in result:
            error_box("Backfill Error", result["error"])
            sys.exit(1)

        elapsed = (time.perf_counter() - t0) * 1000

        success_box("Graph Backfill Complete", [
            ("Receipts Processed", str(result.get("total", 0))),
            ("Nodes Added", str(result.get("added", 0))),
            ("Skipped", str(result.get("skipped", 0))),
            ("Errors", str(result.get("errors", 0))),
            ("Duration", f"{elapsed:.0f}ms"),
        ], "proof graph status")

    except Exception as e:
        error_box("Graph Backfill: ERROR", str(e))
        sys.exit(2)


@graph.command()
@click.argument('receipt_id')
@click.option('--no-ancestors', is_flag=True, help='Exclude ancestors')
@click.option('--no-descendants', is_flag=True, help='Exclude descendants')
@click.option('--no-siblings', is_flag=True, help='Exclude siblings')
def episode(receipt_id: str, no_ancestors: bool, no_descendants: bool, no_siblings: bool):
    """Extract episode subgraph containing a receipt."""
    try:
        from proofpack.graph.episodic import extract_episode, episode_to_dict

        ep = extract_episode(
            receipt_id,
            include_ancestors=not no_ancestors,
            include_descendants=not no_descendants,
            include_siblings=not no_siblings,
        )

        if not ep:
            error_box("Episode Error", f"Receipt not found: {receipt_id}")
            sys.exit(1)

        success_box(f"Episode: {ep.episode_id}", [
            ("Center Node", ep.center_node_id),
            ("Nodes", str(len(ep.nodes))),
            ("Edges", str(len(ep.edges))),
            ("Start Time", ep.start_time),
            ("End Time", ep.end_time),
            ("Receipt Types", ", ".join(ep.receipt_types[:5])),
        ], "proof graph visualize")

        # Print node summary
        print("\nNodes:")
        for node in ep.nodes[:10]:
            marker = "*" if node.get("is_center") else " "
            print(f"  {marker} {node['id'][:16]} ({node['type']})")

        if len(ep.nodes) > 10:
            print(f"  ... and {len(ep.nodes) - 10} more")

    except Exception as e:
        error_box("Episode: ERROR", str(e))
        sys.exit(2)


@graph.command()
@click.option('--format', 'output_format', default='dot',
              type=click.Choice(['dot', 'json']),
              help='Output format')
@click.option('--output', '-o', help='Output file path')
@click.argument('receipt_id', required=False)
def visualize(output_format: str, output: str, receipt_id: str):
    """Export graph or episode for visualization."""
    try:
        if receipt_id:
            # Export specific episode
            from proofpack.graph.episodic import extract_episode, episode_to_dot, episode_to_dict

            ep = extract_episode(receipt_id)
            if not ep:
                error_box("Visualize Error", f"Receipt not found: {receipt_id}")
                sys.exit(1)

            if output_format == 'dot':
                content = episode_to_dot(ep)
            else:
                content = json.dumps(episode_to_dict(ep), indent=2)

        else:
            # Export entire graph
            from proofpack.graph.backend import get_backend

            backend = get_backend()

            if hasattr(backend, 'to_dict'):
                graph_dict = backend.to_dict()
            else:
                graph_dict = {"nodes": [], "edges": []}

            if output_format == 'dot':
                # Convert to DOT format
                lines = ["digraph graph {"]
                lines.append('  rankdir="LR";')
                for node in graph_dict.get("nodes", []):
                    lines.append(f'  "{node["id"]}" [label="{node["type"]}"];')
                for edge in graph_dict.get("edges", []):
                    lines.append(f'  "{edge["source"]}" -> "{edge["target"]}";')
                lines.append("}")
                content = "\n".join(lines)
            else:
                content = json.dumps(graph_dict, indent=2)

        if output:
            with open(output, 'w') as f:
                f.write(content)
            click.echo(f"Written to {output}")
        else:
            click.echo(content)

    except Exception as e:
        error_box("Visualize: ERROR", str(e))
        sys.exit(2)
