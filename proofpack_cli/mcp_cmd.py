"""MCP commands: start, stop, status, tools."""
import sys
import time
import click

from .output import success_box, error_box, table


@click.group()
def mcp():
    """MCP server operations."""
    pass


@mcp.command()
@click.option('--port', default=8765, help='Server port')
@click.option('--no-auth', is_flag=True, help='Disable authentication')
@click.option('--allow-spawn', is_flag=True, help='Allow external spawning')
def start(port: int, no_auth: bool, allow_spawn: bool):
    """Start the MCP server."""
    try:
        from proofpack.mcp.config import MCPConfig
        from proofpack.mcp.server import start_server

        config = MCPConfig.from_env()
        config.port = port

        if no_auth:
            config.auth_required = False
        if allow_spawn:
            config.spawn_allowed = True

        # Validate config
        errors = config.validate()
        if errors and config.auth_required:
            for error in errors:
                click.echo(f"Config error: {error}", err=True)
            sys.exit(1)

        click.echo(f"Starting MCP server on port {port}...")
        click.echo(f"  Auth required: {config.auth_required}")
        click.echo(f"  Spawn allowed: {config.spawn_allowed}")
        click.echo(f"  Tools: {len(config.allowed_tools)}")
        click.echo()

        # This blocks until server stops
        start_server(config)

    except KeyboardInterrupt:
        click.echo("\nServer stopped.")
        sys.exit(0)
    except Exception as e:
        error_box("MCP Start: ERROR", str(e))
        sys.exit(2)


@mcp.command()
def stop():
    """Stop the MCP server."""
    try:
        from proofpack.mcp.server import stop_server

        stop_server()
        success_box("MCP Server", [("Status", "Stopped")], "proof mcp status")

    except Exception as e:
        error_box("MCP Stop: ERROR", str(e))
        sys.exit(2)


@mcp.command()
def status():
    """Show server status and connected clients."""
    try:
        from proofpack.mcp.server import get_server_status

        status_data = get_server_status()

        if status_data is None:
            error_box("MCP Status", "Server not running")
            sys.exit(1)

        success_box("MCP Server Status", [
            ("Running", str(status_data.get("running", False))),
            ("Uptime", f"{status_data.get('uptime_seconds', 0)}s"),
            ("Requests", str(status_data.get("request_count", 0))),
            ("Connections", str(status_data.get("connections", 0))),
            ("Port", str(status_data.get("config", {}).get("port", "N/A"))),
            ("Auth Required", str(status_data.get("config", {}).get("auth_required", "N/A"))),
            ("Spawn Allowed", str(status_data.get("config", {}).get("spawn_allowed", "N/A"))),
        ], "proof mcp tools")

    except Exception as e:
        error_box("MCP Status: ERROR", str(e))
        sys.exit(2)


@mcp.command()
def tools():
    """List exposed MCP tools."""
    try:
        from proofpack.mcp.tools import list_tools

        tools_list = list_tools()

        print("\n╭─ MCP Tools " + "─" * 50 + "╮")
        for tool in tools_list:
            print(f"│ {tool['name']:<20} │ {tool['description'][:40]:<40} │")

            # Show parameters
            params = tool.get("inputSchema", {}).get("properties", {})
            required = tool.get("inputSchema", {}).get("required", [])
            for param_name, param_info in params.items():
                req = "*" if param_name in required else " "
                desc = param_info.get("description", "")[:30]
                print(f"│   {req}{param_name:<17} │ {desc:<40} │")

            print("│" + " " * 22 + "│" + " " * 42 + "│")

        print("╰" + "─" * 22 + "┴" + "─" * 42 + "╯")
        print("\nNext: proof mcp start")

    except Exception as e:
        error_box("MCP Tools: ERROR", str(e))
        sys.exit(2)


@mcp.command()
def test():
    """Test server configuration without starting."""
    try:
        from proofpack.mcp.server import test_server

        if test_server():
            success_box("MCP Config Test", [("Status", "Valid")], "proof mcp start")
            sys.exit(0)
        else:
            error_box("MCP Config Test", "Configuration invalid")
            sys.exit(1)

    except Exception as e:
        error_box("MCP Test: ERROR", str(e))
        sys.exit(2)
