"""Fallback commands: test, stats, sources."""
import sys
import time
import click

from .output import success_box, error_box


@click.group()
def fallback():
    """Web fallback (CRAG) operations."""
    pass


@fallback.command()
@click.argument('query')
@click.option('--provider', default='mock',
              type=click.Choice(['tavily', 'serpapi', 'brave', 'mock']),
              help='Web search provider')
@click.option('--max-results', default=5, help='Maximum web results')
def test(query: str, provider: str, max_results: int):
    """Test fallback without execution."""
    t0 = time.perf_counter()
    try:
        from proofpack.fallback.evaluate import score, Classification
        from proofpack.fallback.web import search, get_available_providers

        # Show available providers
        available = get_available_providers()
        click.echo(f"Available providers: {', '.join(available)}")

        if provider not in available and provider != 'mock':
            click.echo(f"Warning: {provider} not configured, using mock")
            provider = 'mock'

        # Create mock synthesis for testing
        mock_synthesis = {
            "executive_summary": f"Mock synthesis for query: {query}",
            "supporting_evidence": [
                {"chunk_id": "chunk_1", "confidence": 0.6},
                {"chunk_id": "chunk_2", "confidence": 0.5},
            ],
            "evidence_count": 2,
        }

        # Score the mock synthesis
        classification, confidence = score(mock_synthesis, query)

        # Search web
        click.echo(f"\nSearching with {provider}...")
        web_results = search(query, max_results, provider=provider)

        elapsed = (time.perf_counter() - t0) * 1000

        # Show results
        success_box(f"Fallback Test: {query[:30]}...", [
            ("Classification", classification.value),
            ("Confidence", f"{confidence:.3f}"),
            ("Would Fallback", str(classification != Classification.CORRECT)),
            ("Web Results", str(len(web_results))),
            ("Provider", provider),
            ("Duration", f"{elapsed:.0f}ms"),
        ], "proof fallback stats")

        if web_results:
            print("\nWeb Results:")
            for i, wr in enumerate(web_results[:5], 1):
                print(f"  {i}. {wr.title[:50]}")
                print(f"     URL: {wr.url[:60]}")
                print(f"     Relevance: {wr.relevance_score:.2f}")
                print()

    except Exception as e:
        error_box("Fallback Test: ERROR", str(e))
        sys.exit(2)


@fallback.command()
def stats():
    """Show fallback trigger frequency."""
    try:
        # In production, this would query the ledger for fallback receipts
        # For now, show configuration

        from config.features import (
            FEATURE_FALLBACK_ENABLED,
            FEATURE_FALLBACK_WEB_SEARCH,
            FEATURE_FALLBACK_AUTO_TRIGGER,
        )
        from config.fallback import (
            FALLBACK_CONFIDENCE_THRESHOLD,
            FALLBACK_WEB_PROVIDER,
            FALLBACK_MAX_WEB_RESULTS,
        )
        from proofpack.fallback.web import get_available_providers

        available = get_available_providers()

        success_box("Fallback Statistics", [
            ("Fallback Enabled", str(FEATURE_FALLBACK_ENABLED)),
            ("Web Search Enabled", str(FEATURE_FALLBACK_WEB_SEARCH)),
            ("Auto Trigger", str(FEATURE_FALLBACK_AUTO_TRIGGER)),
            ("Confidence Threshold", f"{FALLBACK_CONFIDENCE_THRESHOLD:.2f}"),
            ("Web Provider", FALLBACK_WEB_PROVIDER),
            ("Max Results", str(FALLBACK_MAX_WEB_RESULTS)),
            ("Available Providers", ", ".join(available)),
        ], "proof fallback test <query>")

    except Exception as e:
        error_box("Fallback Stats: ERROR", str(e))
        sys.exit(2)


@fallback.command()
@click.option('--limit', default=10, help='Number of sources to show')
def sources(limit: int):
    """List recent web sources used."""
    try:
        from proofpack.ledger import query_receipts

        # Query for web_retrieval receipts
        try:
            receipts = query_receipts(
                lambda r: r.get("receipt_type") == "web_retrieval"
            )
        except Exception:
            receipts = []

        if not receipts:
            click.echo("No web retrieval receipts found.")
            click.echo("Run 'proof fallback test <query>' to test web search.")
            return

        receipts = receipts[:limit]

        print(f"\n╭─ Recent Web Sources (last {len(receipts)}) " + "─" * 30 + "╮")

        for receipt in receipts:
            query = receipt.get("query", "unknown")[:30]
            provider = receipt.get("provider", "unknown")
            count = receipt.get("results_count", 0)
            latency = receipt.get("latency_ms", 0)

            print(f"│ Query: {query:<30} │")
            print(f"│   Provider: {provider:<10} Results: {count:<3} Latency: {latency:.0f}ms")

            sources_list = receipt.get("sources", [])
            for url in sources_list[:3]:
                print(f"│   - {url[:55]}")

            print("│" + " " * 60 + "│")

        print("╰" + "─" * 62 + "╯")

    except Exception as e:
        error_box("Fallback Sources: ERROR", str(e))
        sys.exit(2)


@fallback.command()
@click.argument('synthesis_file')
@click.option('--query', help='Original query for relevance check')
def evaluate(synthesis_file: str, query: str):
    """Evaluate confidence of a synthesis."""
    try:
        import json

        with open(synthesis_file) as f:
            synthesis = json.load(f)

        from proofpack.fallback.evaluate import evaluate_with_details

        result = evaluate_with_details(synthesis, query or "")

        success_box(f"Evaluation: {result.classification.value}", [
            ("Confidence", f"{result.confidence:.3f}"),
            ("Evidence Count", str(result.factors.get("evidence_count", 0))),
            ("Evidence Strength", f"{result.factors.get('evidence_strength', 0):.3f}"),
            ("Coverage", f"{result.factors.get('coverage', 0):.3f}"),
            ("Gaps", str(len(result.factors.get("gaps", [])))),
            ("Recommendation", result.recommendation),
        ], "proof fallback test <query>")

    except FileNotFoundError:
        error_box("Evaluate Error", f"File not found: {synthesis_file}")
        sys.exit(1)
    except Exception as e:
        error_box("Fallback Evaluate: ERROR", str(e))
        sys.exit(2)
