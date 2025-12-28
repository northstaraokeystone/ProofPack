"""Monte Carlo commands: status, simulate."""
import sys
import time
import click

from .output import success_box, error_box, table, progress_bar


@click.group()
def monte():
    """Monte Carlo simulation operations."""
    pass


@monte.command()
def status():
    """Show Monte Carlo simulation status and stats."""
    t0 = time.perf_counter()
    try:
        from config.features import FEATURE_MONTE_CARLO_ENABLED
        from constants import (
            MONTE_CARLO_DEFAULT_SIMS,
            MONTE_CARLO_VARIANCE_THRESHOLD,
            MONTE_CARLO_LATENCY_BUDGET_MS
        )

        # Mock stats (would load from ledger in production)
        stats = {
            "total_simulations": 15420,
            "avg_variance": 0.12,
            "stable_rate": 0.87,
            "avg_latency_ms": 145,
            "feature_enabled": FEATURE_MONTE_CARLO_ENABLED
        }

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        status_str = "ENABLED" if stats["feature_enabled"] else "DISABLED (shadow mode)"
        health = "HEALTHY" if stats["avg_variance"] < MONTE_CARLO_VARIANCE_THRESHOLD else "DEGRADED"

        success_box(f"Monte Carlo Status: {health}", [
            ("Feature", status_str),
            ("Total Simulations", str(stats["total_simulations"])),
            ("Default N", str(MONTE_CARLO_DEFAULT_SIMS)),
            ("Avg Variance", f"{stats['avg_variance']:.3f}"),
            ("Variance Threshold", str(MONTE_CARLO_VARIANCE_THRESHOLD)),
            ("Stable Rate", f"{stats['stable_rate']*100:.1f}%"),
            ("Avg Latency", f"{stats['avg_latency_ms']}ms / {MONTE_CARLO_LATENCY_BUDGET_MS}ms budget"),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof monte simulate <action_id>")

        exit_code = 0 if health == "HEALTHY" else 1
        sys.exit(exit_code)

    except Exception as e:
        error_box("Monte Status: ERROR", str(e))
        sys.exit(2)


@monte.command()
@click.argument('action_id')
@click.option('--sims', default=100, help='Number of simulations to run')
@click.option('--noise', default=0.05, help='Noise level (0-1)')
def simulate(action_id: str, sims: int, noise: float):
    """Run Monte Carlo simulation for an action."""
    t0 = time.perf_counter()
    try:
        from monte_carlo.simulate import simulate_action, Action
        from monte_carlo.variance import calculate_variance
        from monte_carlo.threshold import check_stability

        # Create action
        action = Action(
            action_id=action_id,
            action_type="test",
            parameters={},
            expected_outcome=0.8
        )

        # Run simulation
        batch, _ = simulate_action(action, n_sims=sims, noise=noise)

        # Calculate variance
        variance_result, _ = calculate_variance(batch.outcomes)

        # Check stability
        stability, _ = check_stability(variance_result.variance_score, action_id=action_id)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        status = "STABLE" if stability.is_stable else "UNSTABLE"

        success_box(f"Monte Carlo Result: {status}", [
            ("Action ID", action_id),
            ("Simulations", str(sims)),
            ("Noise Level", f"{noise:.3f}"),
            ("Mean Outcome", f"{variance_result.mean_outcome:.3f}"),
            ("Variance", f"{variance_result.variance_score:.3f}"),
            ("Std Dev", f"{variance_result.std_dev:.3f}"),
            ("Range", f"{variance_result.min_outcome:.3f} - {variance_result.max_outcome:.3f}"),
            ("Threshold", f"{stability.threshold:.3f}"),
            ("Margin", f"{stability.margin:+.3f}"),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof gate check " + action_id)

        exit_code = 0 if stability.is_stable else 1
        sys.exit(exit_code)

    except Exception as e:
        error_box("Monte Simulate: ERROR", str(e))
        sys.exit(2)
