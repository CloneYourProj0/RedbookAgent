from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from xhs_mcp.mcp_server import configure_defaults, create_server


app = typer.Typer(help="Run the Xiaohongshu MCP server.")


@app.callback()
def main() -> None:
    """Xiaohongshu MCP CLI."""


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", help="Host for streamable-http transport"),
    port: int = typer.Option(8000, help="Port for streamable-http transport"),
    transport: str = typer.Option(
        "streamable-http",
        "--transport",
        "-t",
        help="MCP transport to use (streamable-http or stdio).",
    ),
    profile: Optional[str] = typer.Option(None, help="Default profile name for cookies lookup."),
    cookies_path: Optional[str] = typer.Option(None, help="Default explicit cookies path."),
    chrome_bin: Optional[str] = typer.Option(None, help="Default Chromium/Chrome executable path."),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory for every call."),
    trace: bool = typer.Option(False, help="Capture Playwright tracing when debug_dir is set."),
) -> None:
    """Launch the MCP server."""

    configure_defaults(
        profile=profile,
        cookies_path=cookies_path,
        chrome_bin=chrome_bin,
        debug_dir=str(debug_dir) if debug_dir else None,
        trace=trace or False,
    )

    server = create_server()
    if transport == "streamable-http":
        server.settings.host = host
        server.settings.port = port

    server.run(transport=transport)


if __name__ == "__main__":
    app()
