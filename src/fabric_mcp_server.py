"""
Fabric MCP Server — exposes Microsoft Fabric workspace tools over the
Model Context Protocol so any MCP-compatible client (Claude Desktop,
Cursor, the GitHub Copilot SDK, etc.) can investigate Fabric pipelines.
"""
import os
import re
import base64
import requests
import pyodbc
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

TENANT_ID     = os.getenv("FABRIC_TENANT_ID")
CLIENT_ID     = os.getenv("FABRIC_CLIENT_ID")
CLIENT_SECRET = os.getenv("FABRIC_CLIENT_SECRET")
WORKSPACE_ID  = os.getenv("FABRIC_WORKSPACE_ID")
BASE          = "https://api.fabric.microsoft.com/v1"

mcp = FastMCP("Fabric Pipeline Investigator")

# -----------------------------------------------------------------------------
# Auth + discovery helpers (same as before, just shared between tools)
# -----------------------------------------------------------------------------
def get_token():
    resp = requests.post(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type":    "client_credentials",
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope":         "https://api.fabric.microsoft.com/.default",
        }
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def auth_headers():
    return {"Authorization": f"Bearer {get_token()}"}

def find_item_id(name, item_type=None):
    resp = requests.get(
        f"{BASE}/workspaces/{WORKSPACE_ID}/items",
        headers=auth_headers()
    )
    resp.raise_for_status()
    for item in resp.json().get("value", []):
        if item["displayName"].lower() == name.lower():
            if item_type is None or item["type"] == item_type:
                return item["id"]
    return None

# -----------------------------------------------------------------------------
# TOOL 1 — get_pipeline_run
# -----------------------------------------------------------------------------
@mcp.tool
def get_pipeline_run(pipeline_name: str) -> str:
    """Get the latest run of a Microsoft Fabric pipeline by name, including
    failure details and the name of the failed activity. Use this first when
    investigating a pipeline failure."""
    pipeline_id = find_item_id(pipeline_name, "DataPipeline")
    if not pipeline_id:
        return f"Pipeline '{pipeline_name}' not found in workspace."

    resp = requests.get(
        f"{BASE}/workspaces/{WORKSPACE_ID}/items/{pipeline_id}/jobs/instances",
        headers=auth_headers()
    )
    resp.raise_for_status()
    runs = resp.json().get("value", [])
    if not runs:
        return "No runs found for this pipeline."

    latest = runs[0]
    failure = latest.get("failureReason", {})
    error_msg = failure.get("message", "No error message")

    notebook_match = re.search(r"target (\w+) failed", error_msg)
    failed_activity = notebook_match.group(1) if notebook_match else "unknown"

    return (
        f"Pipeline: {pipeline_name}\n"
        f"Run ID: {latest['id']}\n"
        f"Status: {latest.get('status')}\n"
        f"Failed activity: {failed_activity}\n"
        f"Start: {latest.get('startTimeUtc')}\n"
        f"End:   {latest.get('endTimeUtc')}\n"
        f"Error message:\n{error_msg[:600]}"
    )

# -----------------------------------------------------------------------------
# TOOL 2 — get_notebook_source
# -----------------------------------------------------------------------------
@mcp.tool
def get_notebook_source(notebook_name: str) -> str:
    """Get the source code of a Fabric notebook by name. Use this after
    get_pipeline_run identifies which notebook failed."""
    notebook_id = find_item_id(notebook_name, "Notebook")
    if not notebook_id:
        return f"Notebook '{notebook_name}' not found in workspace."

    resp = requests.post(
        f"{BASE}/workspaces/{WORKSPACE_ID}/notebooks/{notebook_id}/getDefinition",
        headers=auth_headers()
    )
    resp.raise_for_status()

    source = ""
    parts = resp.json().get("definition", {}).get("parts", [])
    for part in parts:
        path = part.get("path", "")
        if path.endswith(".py") or "notebook-content" in path:
            try:
                source += base64.b64decode(part["payload"]).decode("utf-8") + "\n"
            except Exception:
                source += part.get("payload", "") + "\n"

    if not source:
        source = "Could not extract source — raw: " + str(resp.json())[:500]

    return f"Source code of notebook '{notebook_name}':\n\n{source[:2000]}"

# -----------------------------------------------------------------------------
# TOOL 3 — list_lakehouse_tables
# -----------------------------------------------------------------------------
@mcp.tool
def list_lakehouse_tables(lakehouse_name: str) -> str:
    """List all tables that exist in a Fabric lakehouse by name. Fallback for
    when query_sql_endpoint is not appropriate."""
    lakehouse_id = find_item_id(lakehouse_name, "Lakehouse")
    if not lakehouse_id:
        return f"Lakehouse '{lakehouse_name}' not found in workspace."

    resp = requests.get(
        f"{BASE}/workspaces/{WORKSPACE_ID}/lakehouses/{lakehouse_id}/tables",
        headers=auth_headers()
    )
    resp.raise_for_status()
    tables = [t["name"] for t in resp.json().get("data", [])]
    return f"Tables in '{lakehouse_name}': {tables}"

# -----------------------------------------------------------------------------
# TOOL 4 — query_sql_endpoint
# -----------------------------------------------------------------------------
@mcp.tool
def query_sql_endpoint(sql_query: str, lakehouse_name: str = "SalesLakehouse") -> str:
    """Run a T-SQL query against a Fabric lakehouse SQL endpoint. Use this to
    definitively verify whether a table exists or inspect its schema. Always
    use this when the error mentions a missing table or view. Discovers the
    connection string automatically. Only use T-SQL syntax — not Spark SQL."""
    lakehouse_id = find_item_id(lakehouse_name, "Lakehouse")
    if not lakehouse_id:
        return f"Lakehouse '{lakehouse_name}' not found."

    resp = requests.get(
        f"{BASE}/workspaces/{WORKSPACE_ID}/lakehouses/{lakehouse_id}",
        headers=auth_headers()
    )
    resp.raise_for_status()
    props = resp.json().get("properties", {})
    connection_string = props.get("sqlEndpointProperties", {}).get("connectionString")
    if not connection_string:
        return "SQL endpoint not provisioned yet."

    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={connection_string};"
        f"Database={lakehouse_name};"
        f"Authentication=ActiveDirectoryServicePrincipal;"
        f"UID={CLIENT_ID};"
        f"PWD={CLIENT_SECRET};"
        f"TrustServerCertificate=no;"
        f"Encrypt=yes;"
    )

    try:
        conn = pyodbc.connect(conn_str, timeout=30)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        conn.close()

        if not rows:
            return f"Query returned 0 rows.\nSQL: {sql_query}"

        result_lines = [" | ".join(columns)]
        result_lines += [" | ".join(str(v) for v in row) for row in rows[:20]]
        return f"Query results ({len(rows)} rows):\n" + "\n".join(result_lines)

    except Exception as e:
        return f"SQL query failed: {str(e)}"

# -----------------------------------------------------------------------------
# Run the server over stdio (the standard for local MCP servers)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()