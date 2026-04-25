"""
Wanda — agentic Microsoft Fabric pipeline investigator.

This is the agent. It uses the GitHub Copilot SDK to drive an LLM that
investigates pipeline failures by calling tools exposed via a local MCP
server (fabric_mcp_server.py). The MCP server is launched automatically
as a subprocess by the SDK.
"""
import asyncio
import os
import sys
from pathlib import Path
from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.session import PermissionRequestResult

SYSTEM_MESSAGE = """You are Wanda, an expert data pipeline investigator for Microsoft Fabric.

When asked to investigate a pipeline failure, follow this exact evidence chain:

1. Call get_pipeline_run with the pipeline name to get the failure details and the name of the failed activity.

2. Call get_notebook_source using the exact failed activity name returned in step 1.

3. Based on the error type, decide your next step:
   - If the error is TABLE_OR_VIEW_NOT_FOUND or mentions a missing table/view:
     Call query_sql_endpoint with this exact query:
       SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_NAME
     This is T-SQL running against a Fabric SQL endpoint — do not use Spark SQL syntax like SHOW TABLES.
     Use the result to state definitively which tables exist and confirm the missing one.
   - If the error is clearly a code bug (AttributeError, wrong column name, syntax error, NameError):
     Do NOT call query_sql_endpoint or list_lakehouse_tables.
     The notebook source is sufficient evidence — stop and write the report.

4. Write the final report using only evidence from your tool calls. Never guess.

Strict output format — use exactly these headings:
ROOT CAUSE: one definitive sentence
EVIDENCE:
  - Pipeline run: (run ID, status, failed activity, error type)
  - Notebook source: (what the code is doing that causes the error)
  - SQL check: (only if run — exact tables found, confirm missing table)
RECOMMENDATION: one or two sentences on exactly what to change
"""

def log_and_approve(request, invocation):
    """Permission handler that logs each MCP tool call and approves it."""
    kind = request.kind.value if hasattr(request.kind, "value") else str(request.kind)
    tool_name = getattr(request, "tool_name", None) or "?"
    if kind == "mcp":
        # Strip the server prefix that MCP adds (e.g. "fabric.get_pipeline_run")
        clean_name = tool_name.split(".")[-1] if tool_name else "?"
        print(f"  >>> MCP TOOL: {clean_name}")
    return PermissionRequestResult(kind="approved")

async def main():
    pipeline_name = sys.argv[1] if len(sys.argv) > 1 else "LoadSalesPipeline"

    # Path to the MCP server file we built
    server_path = str(Path(__file__).parent / "fabric_mcp_server.py")

    # MCP server config — the SDK will launch this as a subprocess and
    # talk to it over stdio (the standard MCP transport for local servers)
    mcp_servers = {
        "fabric": {
            "type": "local",
            "command": "python",
            "args": [server_path],
            "tools": ["*"],  # Enable all tools from the Fabric MCP server
        }
    }

    config = SubprocessConfig(use_logged_in_user=True)

    async with CopilotClient(config) as client:
        async with await client.create_session(
            model="claude-sonnet-4.5",
            on_permission_request=log_and_approve,
            mcp_servers=mcp_servers,
            system_message={"text": SYSTEM_MESSAGE},
        ) as session:
            done = asyncio.Event()

            def on_event(event):
                t = event.type.value if hasattr(event.type, "value") else str(event.type)
                if t == "assistant.message":
                    print("\n========== WANDA REPORT ==========")
                    print(event.data.content)
                    print("===================================\n")
                elif t == "session.error":
                    print("ERROR:", event.data.message)
                elif t == "session.idle":
                    done.set()

            session.on(on_event)
            await session.send(
                f"The pipeline '{pipeline_name}' just failed. "
                f"Investigate using the Fabric MCP tools and give me a root-cause report."
            )
            await done.wait()


asyncio.run(main())