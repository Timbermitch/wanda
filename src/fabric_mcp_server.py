"""
Fabric MCP Server — exposes Wanda's Microsoft Fabric tools over the
Model Context Protocol so any MCP-compatible client (Claude Desktop,
Cursor, VS Code Copilot, etc.) can investigate Fabric pipelines.

The tool implementations live in fabric_tools.py (shared with Wanda's
inline agent loop); this file is just the MCP front door. Logs go to
stderr — stdout is the JSON-RPC channel and must stay clean.
"""
from fastmcp import FastMCP

import fabric_tools as ft

mcp = FastMCP("Fabric Pipeline Investigator")

for _fn in (
    ft.get_pipeline_run,
    ft.get_notebook_source,
    ft.list_lakehouse_tables,
    ft.query_sql_endpoint,
    ft.get_pipeline_definition,
    ft.query_warehouse_endpoint,
):
    mcp.tool(_fn)

# -----------------------------------------------------------------------------
# Run the server over stdio (the standard for local MCP servers)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Validate Fabric credentials before serving — fail fast with a clear
    # message instead of erroring deep inside a client's first tool call.
    ft.ensure_configured()
    mcp.run()
