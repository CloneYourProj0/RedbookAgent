# xiaohongshu-mcp-py

Python rewrite scaffold for xiaohongshu-mcp.

## Requirements

Install dependencies (Playwright needs an additional browser install step if not already set up):

```bash
pip install -r requirements.txt
playwright install chromium
```

## MCP server

Launch the Xiaohongshu MCP server over `streamable-http` (defaults: host `127.0.0.1`, port `8000`):

```bash
python -m xhs_mcp.cli.mcp_cli serve --host 0.0.0.0 --port 8000
```

Useful options:

- `--profile` / `--cookies-path` / `--chrome-bin` set global defaults for cookie storage and Chromium binary lookup.
- `--debug-dir` and `--trace` mirror the manual CLI behaviour and capture diagnostics for every call.
- `--transport stdio` switches to subprocess mode if you need local-only communication.

Once running, the service exposes all existing Playwright actions (feeds, search, note interactions, publishing, login helpers) as MCP tools. Clients such as LangGraph can connect via `MultiServerMCPClient` with a `streamable_http` entry pointing to `http://<host>:<port>/mcp`.
