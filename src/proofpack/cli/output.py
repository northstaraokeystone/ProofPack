"""Shared output formatting with ASCII boxes. NO class - just functions."""

import json

import click

BOX_WIDTH = 60


def print_json(data: dict) -> None:
    """Print JSON data formatted."""
    click.echo(json.dumps(data, indent=2, sort_keys=True))


def print_error(message: str) -> None:
    """Print error message in red."""
    click.echo(click.style(f"Error: {message}", fg="red"))


def print_success(message: str) -> None:
    """Print success message in green."""
    click.echo(click.style(message, fg="green"))


def _truncate(text: str, max_len: int = 50) -> str:
    """Truncate text with ellipsis if too long."""
    return text[:max_len-3] + "..." if len(text) > max_len else text


def success_box(title: str, rows: list[tuple[str, str]], next_cmd: str) -> None:
    """Print green-bordered success box with Next: suggestion."""
    print(f"\u256d\u2500 {title} " + "\u2500" * (BOX_WIDTH - len(title) - 4) + "\u256e")
    for label, value in rows:
        line = f"\u2502 {label}: {_truncate(str(value), BOX_WIDTH - len(label) - 6)}"
        print(line + " " * (BOX_WIDTH - len(line)) + "\u2502")
    print("\u2570" + "\u2500" * (BOX_WIDTH - 1) + "\u256f")
    print(f"Next: {next_cmd}")


def error_box(title: str, message: str, fix_cmd: str | None = None) -> None:
    """Print red-bordered error box with optional --fix suggestion."""
    print(f"\u256d\u2500 {title} " + "\u2500" * (BOX_WIDTH - len(title) - 4) + "\u256e")
    print(f"\u2502 {_truncate(message, BOX_WIDTH - 4)}" + " " * (BOX_WIDTH - len(message) - 4) + "\u2502")
    print("\u2570" + "\u2500" * (BOX_WIDTH - 1) + "\u256f")
    if fix_cmd:
        print(f"Fix: {fix_cmd}")


def table(headers: list[str], rows: list[list[str]]) -> None:
    """Print simple table for list commands."""
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    # Header
    header_line = "\u2502 " + " \u2502 ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " \u2502"
    sep_line = "\u251c" + "\u2500" + "\u2500\u253c\u2500".join("\u2500" * w for w in widths) + "\u2500\u2524"

    print("\u256d" + "\u2500" * (len(header_line) - 2) + "\u256e")
    print(header_line)
    print(sep_line)
    for row in rows:
        cells = [str(cell).ljust(widths[i]) if i < len(row) else " " * widths[i]
                 for i, _ in enumerate(headers)]
        for i, cell in enumerate(row):
            if i < len(cells):
                cells[i] = str(cell).ljust(widths[i])
        print("\u2502 " + " \u2502 ".join(cells) + " \u2502")
    print("\u2570" + "\u2500" * (len(header_line) - 2) + "\u256f")


def progress_bar(value: float, width: int = 20) -> str:
    """Return ASCII progress bar."""
    filled = int(value * width)
    return "\u2588" * filled + "\u2591" * (width - filled)
