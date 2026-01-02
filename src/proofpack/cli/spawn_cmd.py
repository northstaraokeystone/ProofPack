"""Spawn commands: status, history, kill, patterns, simulate."""
import sys
import time

import click

from .output import error_box, success_box


@click.group()
def spawn():
    """Agent spawning and lifecycle operations."""
    pass


@spawn.command()
def status():
    """Show active agents, depth, TTL remaining."""
    t0 = time.perf_counter()
    try:
        from spawner.lifecycle import get_ttl_remaining
        from spawner.registry import (
            MAX_AGENTS,
            MAX_DEPTH,
            get_active_agents,
            get_population_count,
        )

        from proofpack.config.features import FEATURE_AGENT_SPAWNING_ENABLED

        active = get_active_agents()
        population = get_population_count()
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        status_str = "ENABLED" if FEATURE_AGENT_SPAWNING_ENABLED else "DISABLED (shadow mode)"
        health = "HEALTHY" if population < MAX_AGENTS * 0.8 else "NEAR_CAPACITY"

        success_box(f"Spawn Status: {health}", [
            ("Feature", status_str),
            ("Active Agents", f"{population} / {MAX_AGENTS}"),
            ("Max Depth", str(MAX_DEPTH)),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof spawn history")

        if active:
            print()
            print("Active Agents:")
            print("-" * 60)
            for agent in active[:10]:  # Limit to 10
                ttl = get_ttl_remaining(agent.agent_id)
                print(f"  {agent.agent_id[:8]}... | {agent.agent_type.value:16} | "
                      f"depth={agent.depth} | TTL={int(ttl)}s")
            if len(active) > 10:
                print(f"  ... and {len(active) - 10} more")

        sys.exit(0)

    except ImportError as e:
        error_box("Spawn Status: ERROR", f"Spawner module not available: {e}")
        sys.exit(2)
    except Exception as e:
        error_box("Spawn Status: ERROR", str(e))
        sys.exit(2)


@spawn.command()
@click.option('--limit', default=20, help='Number of events to show')
@click.option('--type', 'event_type', type=click.Choice(['spawn', 'prune', 'graduate']),
              help='Filter by event type')
def history(limit: int, event_type: str | None):
    """Show spawn/prune/graduate events."""
    t0 = time.perf_counter()
    try:
        # In production, would query ledger for spawn/prune/graduate receipts
        # For now, mock data
        events = [
            {"type": "spawn", "agent_id": "abc123", "trigger": "RED_GATE", "ts": "2024-01-15T10:30:00Z"},
            {"type": "prune", "agent_id": "def456", "reason": "TTL_EXPIRED", "ts": "2024-01-15T10:29:00Z"},
            {"type": "graduate", "agent_id": "ghi789", "pattern_id": "pat001", "ts": "2024-01-15T10:28:00Z"},
        ]

        if event_type:
            events = [e for e in events if e["type"] == event_type]

        events = events[:limit]
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        title = f"Spawn History (last {len(events)})"
        if event_type:
            title += f" - {event_type} only"

        print(f"\u256d\u2500 {title} " + "\u2500" * 40 + "\u256e")
        print(f"\u2502 {'Type':<10}\u2502 {'Agent ID':<10}\u2502 {'Details':<20}\u2502 {'Timestamp':<20}\u2502")
        print("\u251c" + "\u2500" * 10 + "\u253c" + "\u2500" * 10 + "\u253c" + "\u2500" * 20 + "\u253c" + "\u2500" * 20 + "\u2524")
        for e in events:
            details = e.get("trigger") or e.get("reason") or e.get("pattern_id", "")
            print(f"\u2502 {e['type']:<10}\u2502 {e['agent_id'][:8]:<10}\u2502 {details:<20}\u2502 {e['ts']:<20}\u2502")
        print("\u2570" + "\u2500" * 60 + "\u256f")
        print(f"Duration: {elapsed_ms}ms")
        print("Next: proof spawn status")
        sys.exit(0)

    except Exception as e:
        error_box("Spawn History: ERROR", str(e))
        sys.exit(2)


@spawn.command()
@click.argument('agent_id')
def kill(agent_id: str):
    """Manual termination of an agent."""
    t0 = time.perf_counter()
    try:
        from spawner.prune import PruneReason, prune_agent

        result, receipt = prune_agent(agent_id, PruneReason.MANUAL)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if result.success:
            success_box("Agent Terminated", [
                ("Agent ID", agent_id),
                ("Reason", "MANUAL"),
                ("Resources Freed", str(result.resources_freed)),
                ("Duration", f"{elapsed_ms}ms")
            ], "proof spawn status")
            sys.exit(0)
        else:
            error_box("Kill Failed", f"Agent {agent_id} could not be terminated")
            sys.exit(1)

    except ImportError as e:
        error_box("Kill: ERROR", f"Spawner module not available: {e}")
        sys.exit(2)
    except Exception as e:
        error_box("Kill: ERROR", str(e))
        sys.exit(2)


@spawn.command()
@click.option('--gate', 'gate_filter', type=click.Choice(['GREEN', 'YELLOW', 'RED']),
              help='Filter by gate color')
def patterns(gate_filter: str | None):
    """List graduated patterns."""
    t0 = time.perf_counter()
    try:
        from spawner.patterns import list_patterns

        pattern_list = list_patterns(gate_color=gate_filter)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        title = f"Graduated Patterns ({len(pattern_list)})"
        if gate_filter:
            title += f" - {gate_filter} gate"

        if not pattern_list:
            success_box(title, [
                ("Count", "0"),
                ("Duration", f"{elapsed_ms}ms")
            ], "proof spawn simulate")
            print("No patterns yet. Patterns are created when agents graduate.")
            sys.exit(0)

        print(f"\u256d\u2500 {title} " + "\u2500" * 40 + "\u256e")
        print(f"\u2502 {'Pattern ID':<10}\u2502 {'Gate':<6}\u2502 {'Angle':<12}\u2502 {'Eff.':<6}\u2502 {'Uses':<6}\u2502")
        print("\u251c" + "\u2500" * 10 + "\u253c" + "\u2500" * 6 + "\u253c" + "\u2500" * 12 + "\u253c" + "\u2500" * 6 + "\u253c" + "\u2500" * 6 + "\u2524")
        for p in pattern_list[:20]:
            angle = (p.get("decomposition_angle") or "")[:10]
            print(f"\u2502 {p['pattern_id'][:8]:<10}\u2502 {p['gate_color']:<6}\u2502 {angle:<12}\u2502 "
                  f"{p['effectiveness']:<6.2f}\u2502 {p['use_count']:<6}\u2502")
        print("\u2570" + "\u2500" * 45 + "\u256f")
        print(f"Duration: {elapsed_ms}ms")
        sys.exit(0)

    except ImportError as e:
        error_box("Patterns: ERROR", f"Spawner module not available: {e}")
        sys.exit(2)
    except Exception as e:
        error_box("Patterns: ERROR", str(e))
        sys.exit(2)


@spawn.command()
@click.option('--gate', 'gate_color', type=click.Choice(['GREEN', 'YELLOW', 'RED']),
              default='RED', help='Gate color to simulate')
@click.option('--confidence', type=float, default=0.5, help='Confidence score (0-1)')
@click.option('--wounds', type=int, default=5, help='Wound count')
@click.option('--variance', type=float, default=0.0, help='Monte Carlo variance')
def simulate(gate_color: str, confidence: float, wounds: int, variance: float):
    """Run spawning simulation without execution."""
    t0 = time.perf_counter()
    try:
        from spawner.birth import simulate_spawn

        result = simulate_spawn(gate_color, confidence, wounds, variance)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        success_box(f"Spawn Simulation: {gate_color}", [
            ("Gate Color", gate_color),
            ("Confidence", f"{confidence:.3f}"),
            ("Wound Count", str(wounds)),
            ("Variance", f"{variance:.3f}"),
            ("Would Spawn", str(result["would_spawn"])),
            ("Agent Types", ", ".join(result["agent_types"])),
            ("TTL", f"{result['ttl_seconds']}s"),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof gate check <action_id>")

        sys.exit(0)

    except ImportError as e:
        error_box("Simulate: ERROR", f"Spawner module not available: {e}")
        sys.exit(2)
    except Exception as e:
        error_box("Simulate: ERROR", str(e))
        sys.exit(2)
