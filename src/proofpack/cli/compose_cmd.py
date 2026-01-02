"""Compose commands: run, validate."""
import sys
import time
import json
import click

from .output import success_box, error_box


@click.group()
def compose():
    """Module composition and validation."""
    pass


@compose.command('run')
@click.argument('config', type=click.Path(exists=True))
def run(config: str):
    """Run composition from config file."""
    t0 = time.perf_counter()
    try:
        # Load config
        with open(config, 'r') as f:
            cfg = json.load(f)

        modules = cfg.get("modules", ["ledger", "brief", "packet", "detect", "loop"])
        version = cfg.get("version", "3.0.0")

        # Check module health (mock)
        healthy = []
        failed = []
        for mod in modules:
            try:
                __import__(mod)
                healthy.append(mod)
            except ImportError:
                failed.append(mod)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if failed:
            status = "PARTIAL"
            exit_code = 1
        else:
            status = "ALL HEALTHY"
            exit_code = 0

        success_box(f"Compose: {config}", [
            ("Modules enabled", ", ".join(modules)),
            ("Healthy", str(len(healthy))),
            ("Failed", str(len(failed)) if failed else "0"),
            ("Status", status),
            ("Version", version),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof loop status")
        sys.exit(exit_code)

    except json.JSONDecodeError as e:
        error_box("Compose Run: INVALID CONFIG", f"JSON parse error: {e}")
        sys.exit(2)
    except FileNotFoundError:
        error_box("Compose Run: NOT FOUND", f"Config file not found: {config}")
        sys.exit(2)
    except Exception as e:
        error_box("Compose Run: ERROR", str(e))
        sys.exit(2)


@compose.command()
@click.argument('config', type=click.Path(exists=True))
def validate(config: str):
    """Validate config file."""
    t0 = time.perf_counter()
    try:
        # Load and validate config
        with open(config, 'r') as f:
            cfg = json.load(f)

        warnings = []
        errors = []

        # Required fields
        if "version" not in cfg:
            warnings.append("Missing 'version' field")
        if "modules" not in cfg:
            errors.append("Missing 'modules' field")
        elif not isinstance(cfg["modules"], list):
            errors.append("'modules' must be a list")

        # Module validation
        valid_modules = {"ledger", "brief", "packet", "detect", "anchor", "loop"}
        if "modules" in cfg:
            for mod in cfg["modules"]:
                if mod not in valid_modules:
                    warnings.append(f"Unknown module: {mod}")

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if errors:
            error_box("Compose Validate: INVALID", "\n".join(errors))
            sys.exit(2)
        elif warnings:
            print("\u256d\u2500 Compose Validate: WARNINGS " + "\u2500" * 30 + "\u256e")
            print(f"\u2502 Config: {config}")
            for w in warnings:
                print(f"\u2502 WARN: {w}")
            print(f"\u2502 Duration: {elapsed_ms}ms")
            print("\u2570" + "\u2500" * 59 + "\u256f")
            print("Next: proof compose run " + config)
            sys.exit(1)
        else:
            success_box("Compose Validate: VALID", [
                ("Config", config),
                ("Modules", str(len(cfg.get("modules", [])))),
                ("Version", cfg.get("version", "unspecified")),
                ("Duration", f"{elapsed_ms}ms")
            ], f"proof compose run {config}")
            sys.exit(0)

    except json.JSONDecodeError as e:
        error_box("Compose Validate: INVALID JSON", str(e))
        sys.exit(2)
    except FileNotFoundError:
        error_box("Compose Validate: NOT FOUND", f"Config file not found: {config}")
        sys.exit(2)
    except Exception as e:
        error_box("Compose Validate: ERROR", str(e))
        sys.exit(2)
