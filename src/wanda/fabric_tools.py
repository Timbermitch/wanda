"""
fabric_tools.py — Wanda's Microsoft Fabric tools as plain Python functions.

This is the single home of the 6 Fabric tools. Two front doors consume it:

  - wanda.core / wanda.cli import the functions directly and call them inline
    from the agent loop ("inline mode" — what a Fabric notebook can run, no subprocess).
  - wanda.mcp_server wraps the same functions with FastMCP so any
    MCP-compatible client (Claude Desktop, Cursor, VS Code) can use them too.

Configuration is resolved lazily on first use, so importing this module never
requires credentials (needed for tests and notebook packaging). Entry points
that want fail-fast behavior call ensure_configured() up front.
"""
from __future__ import annotations

import base64
import json
import re
import time

import requests

from .config import Config, load_config
from .log_setup import get_logger

logger = get_logger("fabric")

# How many times to retry a throttled (429) or transient (5xx) Fabric call.
MAX_RETRIES = 5

# Without a timeout, a half-open connection blocks a tool call forever and the
# retry logic never even runs. Fabric calls are interactive; keep these tight.
TOKEN_TIMEOUT = 30
REQUEST_TIMEOUT = 60

_cfg: Config | None = None


def _config() -> Config:
    """Resolve and validate Fabric credentials on first use."""
    global _cfg
    if _cfg is None:
        _cfg = load_config().require_fabric()
    return _cfg


def ensure_configured() -> None:
    """Fail fast with a clear message if Fabric credentials are missing."""
    _config()


# -----------------------------------------------------------------------------
# Auth + request plumbing
# -----------------------------------------------------------------------------
# Cached Service Principal token. Fabric tokens last ~1 hour; we cache until
# shortly before expiry and refresh transparently (including on a 401).
_token_cache: dict[str, object] = {"token": None, "expires_at": 0.0}


def get_token(force_refresh: bool = False) -> str:
    cfg = _config()
    now = time.time()
    cached = _token_cache["token"]
    if cached and not force_refresh and now < float(_token_cache["expires_at"]) - 60:
        return str(cached)
    resp = requests.post(
        f"https://login.microsoftonline.com/{cfg.tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type":    "client_credentials",
            "client_id":     cfg.client_id,
            "client_secret": cfg.client_secret,
            "scope":         "https://api.fabric.microsoft.com/.default",
        },
        timeout=TOKEN_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return str(_token_cache["token"])


def _retry_after_seconds(resp: requests.Response, attempt: int) -> float:
    """Seconds to wait before retrying. Honors Retry-After, else exponential
    backoff, capped at 60s."""
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), 60.0)
        except ValueError:
            pass
    return min(2.0 ** attempt, 60.0)


def fabric_request(method: str, url: str, **kwargs) -> requests.Response:
    """Issue an authenticated Fabric request with transparent token refresh and
    retry. Refreshes the token and retries once on a 401; honors Retry-After and
    backs off exponentially on 429 / 5xx. Returns the final response so callers
    can inspect status (see _http_error)."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    resp = None
    for attempt in range(MAX_RETRIES):
        headers = {**kwargs.get("headers", {}), "Authorization": f"Bearer {get_token()}"}
        try:
            resp = requests.request(method, url, **{**kwargs, "headers": headers})
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait = min(2.0 ** attempt, 60.0)
                logger.warning(
                    "Fabric request to %s failed (%s) — backing off %.1fs (attempt %d/%d)",
                    url, e.__class__.__name__, wait, attempt + 1, MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            raise

        if resp.status_code == 401 and attempt == 0:
            logger.warning("401 from Fabric while calling %s — refreshing token", url)
            get_token(force_refresh=True)
            continue

        if (resp.status_code == 429 or resp.status_code >= 500) and attempt < MAX_RETRIES - 1:
            wait = _retry_after_seconds(resp, attempt)
            logger.warning(
                "Fabric returned %s for %s — backing off %.1fs (attempt %d/%d)",
                resp.status_code, url, wait, attempt + 1, MAX_RETRIES,
            )
            time.sleep(wait)
            continue

        return resp
    return resp  # exhausted retries; return the last response for the caller to handle


def _http_error(resp: requests.Response, context: str) -> str | None:
    """Return a clear, user-facing message for a failed Fabric response, or None
    if it succeeded. Translates the common auth/permission cases."""
    if resp.ok:
        return None
    code = resp.status_code
    if code == 401:
        return (f"Authentication failed (401) while {context}. "
                f"Check the Service Principal client id and secret.")
    if code == 403:
        return (f"Permission denied (403) while {context}. The Service Principal lacks the "
                f"required role on this workspace or item (e.g. Workspace Contributor, or "
                f"item-level read access). Grant it and retry.")
    if code == 404:
        return f"Not found (404) while {context}."
    if code == 429:
        return f"Rate limited (429) while {context}, and retries were exhausted. Try again shortly."
    return f"Fabric API error {code} while {context}: {resp.text[:300]}"


def _list_workspace_items() -> list[dict]:
    """Fetch all items in the workspace. Raises with a clear message on a hard
    auth/permission failure so the agent sees why discovery failed."""
    cfg = _config()
    resp = fabric_request("GET", f"{cfg.base_url}/workspaces/{cfg.workspace_id}/items")
    err = _http_error(resp, "listing items in the workspace")
    if err:
        raise RuntimeError(err)
    return resp.json().get("value", [])


def find_item_id(name: str, item_type: str | None = None) -> str | None:
    for item in _list_workspace_items():
        if item.get("displayName", "").lower() == name.lower():
            if item_type is None or item.get("type") == item_type:
                return item.get("id")
    return None


def _resolve_lro(initial_resp: requests.Response) -> dict:
    """Handle Fabric's long-running operation pattern. If the initial response
    is 200 sync, return its JSON. If it is 202 async, poll the Location header
    until the operation completes and return the final result payload."""
    if initial_resp.status_code == 200:
        return initial_resp.json()
    if initial_resp.status_code != 202:
        initial_resp.raise_for_status()
        return initial_resp.json()

    op_url = initial_resp.headers.get("Location")
    if not op_url:
        return {"error": "202 response had no Location header", "body": initial_resp.text[:500]}
    retry_after = int(initial_resp.headers.get("Retry-After", "3") or "3")

    # Poll the operation status. Most Fabric getDefinition LROs finish in <30s.
    for _ in range(40):
        time.sleep(retry_after)
        op_resp = fabric_request("GET", op_url)
        op_resp.raise_for_status()
        op_data = op_resp.json()
        status = op_data.get("status", "Unknown")
        if status == "Succeeded":
            result_resp = fabric_request("GET", op_url.rstrip("/") + "/result")
            result_resp.raise_for_status()
            return result_resp.json()
        if status == "Failed":
            return {"error": "LRO failed", "details": op_data.get("error")}
    return {"error": "LRO timed out after polling"}


def get_item_names_by_id() -> dict[str, dict]:
    """Return a dict mapping every workspace item id -> {name, type}.
    Used to resolve notebookIds and lakehouse/warehouse artifactIds that
    pipeline definitions reference by ID only."""
    return {
        item["id"]: {"name": item["displayName"], "type": item["type"]}
        for item in _list_workspace_items()
    }


def _sql_connection_string(server: str, database: str) -> str:
    cfg = _config()
    return (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={server};"
        f"Database={database};"
        f"Authentication=ActiveDirectoryServicePrincipal;"
        f"UID={cfg.client_id};"
        f"PWD={cfg.client_secret};"
        f"TrustServerCertificate=no;"
        f"Encrypt=yes;"
    )


def _run_sql(server: str, database: str, sql_query: str, label: str) -> str:
    """Run a T-SQL query over ODBC and format the result for the agent."""
    try:
        import pyodbc
    except ImportError:
        return (
            f"pyodbc is not installed in this environment, so {label} queries are "
            f"unavailable. Use list_lakehouse_tables for table existence checks instead."
        )

    try:
        conn = pyodbc.connect(_sql_connection_string(server, database), timeout=30)
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
        return f"{label} query failed: {str(e)}"


# -----------------------------------------------------------------------------
# TOOL 1 — get_pipeline_run
# -----------------------------------------------------------------------------
def get_pipeline_run(pipeline_name: str) -> str:
    """Get the latest run of a Microsoft Fabric pipeline by name, including
    status, activity details, and failure information if applicable."""
    cfg = _config()
    pipeline_id = find_item_id(pipeline_name, "DataPipeline")
    if not pipeline_id:
        return f"Pipeline '{pipeline_name}' not found in workspace."

    resp = fabric_request(
        "GET", f"{cfg.base_url}/workspaces/{cfg.workspace_id}/items/{pipeline_id}/jobs/instances"
    )
    err = _http_error(resp, f"reading runs for pipeline '{pipeline_name}'")
    if err:
        return err
    runs = resp.json().get("value", [])
    if not runs:
        return "No runs found for this pipeline."

    latest = runs[0] or {}
    status = latest.get("status", "Unknown")
    failure = latest.get("failureReason") or {}
    error_msg = failure.get("message") or "No error message"

    # Try to extract failed activity name from error message
    failed_activity = "unknown"
    patterns = [
        r"Activity '([^']+)' failed",
        r"activity '([^']+)' failed",
        r"target (\w+) failed",
        r"'([^']+)' activity failed",
    ]
    for pattern in patterns:
        match = re.search(pattern, error_msg, re.IGNORECASE)
        if match:
            failed_activity = match.group(1)
            break

    result = (
        f"Pipeline: {pipeline_name}\n"
        f"Run ID: {latest.get('id', 'unknown')}\n"
        f"Status: {status}\n"
        f"Start: {latest.get('startTimeUtc')}\n"
        f"End:   {latest.get('endTimeUtc')}\n"
    )

    if status == "Failed":
        result += (
            f"Failed activity: {failed_activity}\n"
            f"Error message:\n{error_msg[:800]}"
        )
    else:
        result += "Pipeline completed successfully. No failures detected."

    return result


# -----------------------------------------------------------------------------
# TOOL 2 — get_notebook_source
# -----------------------------------------------------------------------------
def get_notebook_source(notebook_name: str) -> str:
    """Get the source code of a Fabric notebook by name. Use this after
    get_pipeline_run identifies which notebook failed."""
    cfg = _config()
    notebook_id = find_item_id(notebook_name, "Notebook")
    if not notebook_id:
        return f"Notebook '{notebook_name}' not found in workspace."

    resp = fabric_request(
        "POST", f"{cfg.base_url}/workspaces/{cfg.workspace_id}/notebooks/{notebook_id}/getDefinition"
    )
    payload = _resolve_lro(resp)
    if "error" in payload and "definition" not in payload:
        return f"Could not fetch notebook '{notebook_name}': {payload}"

    source = ""
    parts = (payload.get("definition") or {}).get("parts") or []
    for part in parts:
        path = part.get("path", "")
        if path.endswith(".py") or "notebook-content" in path:
            encoded = part.get("payload", "")
            try:
                source += base64.b64decode(encoded).decode("utf-8") + "\n"
            except Exception:
                source += encoded + "\n"

    if not source.strip():
        return (
            f"Notebook '{notebook_name}' has no extractable Python source — it may be a "
            f"Spark SQL/T-SQL notebook, contain only binary cells, or have never been "
            f"saved with code."
        )

    truncated = len(source) > 2000
    body = source[:2000] + ("\n\n…(source truncated at 2000 chars)…" if truncated else "")
    return f"Source code of notebook '{notebook_name}':\n\n{body}"


# -----------------------------------------------------------------------------
# TOOL 3 — list_lakehouse_tables
# -----------------------------------------------------------------------------
def list_lakehouse_tables(lakehouse_name: str) -> str:
    """List all tables that exist in a Fabric lakehouse by name. Fallback for
    when query_sql_endpoint is not appropriate."""
    cfg = _config()
    lakehouse_id = find_item_id(lakehouse_name, "Lakehouse")
    if not lakehouse_id:
        return f"Lakehouse '{lakehouse_name}' not found in workspace."

    resp = fabric_request(
        "GET", f"{cfg.base_url}/workspaces/{cfg.workspace_id}/lakehouses/{lakehouse_id}/tables"
    )
    err = _http_error(resp, f"listing tables in lakehouse '{lakehouse_name}'")
    if err:
        return err
    tables = [t.get("name") for t in resp.json().get("data", []) if t.get("name")]
    return f"Tables in '{lakehouse_name}': {tables}"


# -----------------------------------------------------------------------------
# TOOL 4 — query_sql_endpoint
# -----------------------------------------------------------------------------
def query_sql_endpoint(sql_query: str, lakehouse_name: str = "SalesLakehouse") -> str:
    """Run a T-SQL query against a Fabric lakehouse SQL endpoint. Use this to
    definitively verify whether a table exists or inspect its schema. Always
    use this when the error mentions a missing table or view. Discovers the
    connection string automatically. Only use T-SQL syntax — not Spark SQL."""
    cfg = _config()
    lakehouse_id = find_item_id(lakehouse_name, "Lakehouse")
    if not lakehouse_id:
        return f"Lakehouse '{lakehouse_name}' not found."

    resp = fabric_request("GET", f"{cfg.base_url}/workspaces/{cfg.workspace_id}/lakehouses/{lakehouse_id}")
    err = _http_error(resp, f"reading SQL endpoint for lakehouse '{lakehouse_name}'")
    if err:
        return err
    props = resp.json().get("properties") or {}
    connection_string = (props.get("sqlEndpointProperties") or {}).get("connectionString")
    if not connection_string:
        return (
            f"SQL endpoint for lakehouse '{lakehouse_name}' is not provisioned yet. "
            f"Fabric SQL endpoints can take 1-2 minutes to come up after a lakehouse is "
            f"created — wait and retry, or use list_lakehouse_tables instead."
        )

    return _run_sql(connection_string, lakehouse_name, sql_query, "SQL")


# -----------------------------------------------------------------------------
# TOOL 5 — get_pipeline_definition
# -----------------------------------------------------------------------------
def get_pipeline_definition(pipeline_name: str) -> str:
    """Get the full definition of a Microsoft Fabric pipeline by name,
    including all its activities, their types, and dependencies. Use this
    for pre-run scans to understand pipeline structure before execution."""
    cfg = _config()
    pipeline_id = find_item_id(pipeline_name, "DataPipeline")
    if not pipeline_id:
        return f"Pipeline '{pipeline_name}' not found in workspace."

    resp = fabric_request(
        "POST", f"{cfg.base_url}/workspaces/{cfg.workspace_id}/dataPipelines/{pipeline_id}/getDefinition"
    )
    payload = _resolve_lro(resp)
    if "error" in payload and "definition" not in payload:
        return f"Could not fetch pipeline definition: {payload}"

    parts = (payload.get("definition") or {}).get("parts") or []
    pipeline_json = ""
    for part in parts:
        if "pipeline-content" in part.get("path", ""):
            encoded = part.get("payload", "")
            try:
                pipeline_json = base64.b64decode(encoded).decode("utf-8")
            except Exception:
                pipeline_json = encoded
            break

    if not pipeline_json:
        return f"Could not extract pipeline definition. Raw response: {str(payload)[:500]}"

    # Parse and summarize the activities for the agent
    try:
        pipeline_data = json.loads(pipeline_json)
        activities = (pipeline_data.get("properties") or {}).get("activities") or []

        if not activities:
            return (
                f"Pipeline '{pipeline_name}' has no activities — it is an empty/draft "
                f"pipeline. There is nothing to audit until activities are added."
            )

        # Resolve all referenced artifactIds / notebookIds to display names
        id_to_item = get_item_names_by_id()

        def name_of(item_id: str | None) -> str:
            return id_to_item.get(item_id, {}).get("name", f"<unresolved:{item_id}>")

        summary = f"Pipeline: {pipeline_name}\nActivities ({len(activities)}):\n\n"
        for act in activities:
            name = act.get("name", "unknown")
            act_type = act.get("type", "unknown")
            deps = [d.get("activity") for d in act.get("dependsOn", [])]
            type_props = act.get("typeProperties", {})

            summary += f"- {name} ({act_type})\n"
            if deps:
                summary += f"    depends on: {deps}\n"

            # Surface relevant info based on activity type
            if act_type == "TridentNotebook":
                nb_id = type_props.get("notebookId", "?")
                nb_name = name_of(nb_id)
                summary += f"    notebook: '{nb_name}' (id: {nb_id})\n"
            elif act_type == "Copy":
                source_type = type_props.get("source", {}).get("type", "?")
                sink = type_props.get("sink", {})
                sink_type = sink.get("type", "?")
                sink_action = sink.get("tableActionOption", "?")
                sink_settings = sink.get("datasetSettings", {})
                sink_table = sink_settings.get("typeProperties", {}).get("table", "?")
                sink_artifact_id = sink_settings.get("linkedService", {}).get("properties", {}).get("typeProperties", {}).get("artifactId")
                sink_target = name_of(sink_artifact_id) if sink_artifact_id else "?"
                summary += (
                    f"    copy: {source_type} -> {sink_type}\n"
                    f"    sink target: '{sink_target}' (table: {sink_table}, action: {sink_action})\n"
                )
            elif act_type == "SqlServerStoredProcedure":
                sp_name = type_props.get("storedProcedureName", "?")
                wh_artifact_id = act.get("linkedService", {}).get("properties", {}).get("typeProperties", {}).get("artifactId")
                wh_name = name_of(wh_artifact_id) if wh_artifact_id else "?"
                summary += f"    stored procedure: {sp_name} (warehouse: '{wh_name}')\n"

        return summary
    except Exception as e:
        return f"Pipeline definition (raw):\n{pipeline_json[:2000]}\n\nParse error: {e}"


# -----------------------------------------------------------------------------
# TOOL 6 — query_warehouse_endpoint
# -----------------------------------------------------------------------------
def query_warehouse_endpoint(sql_query: str, warehouse_name: str) -> str:
    """Run a T-SQL query against a Fabric Warehouse SQL endpoint. Use this
    for stored procedures, tables, and views that live in a Warehouse (not
    a Lakehouse). SqlServerStoredProcedure activities run against a
    Warehouse — use this tool, not query_sql_endpoint, to verify their
    procedures exist (e.g. SELECT name FROM sys.procedures WHERE ...)."""
    cfg = _config()
    warehouse_id = find_item_id(warehouse_name, "Warehouse")
    if not warehouse_id:
        return f"Warehouse '{warehouse_name}' not found."

    resp = fabric_request("GET", f"{cfg.base_url}/workspaces/{cfg.workspace_id}/warehouses/{warehouse_id}")
    err = _http_error(resp, f"reading SQL endpoint for warehouse '{warehouse_name}'")
    if err:
        return err
    props = resp.json().get("properties") or {}
    connection_string = props.get("connectionString")
    if not connection_string:
        return f"Warehouse '{warehouse_name}' SQL endpoint is not provisioned yet."

    return _run_sql(connection_string, warehouse_name, sql_query, "Warehouse SQL")


# -----------------------------------------------------------------------------
# Tool registry — what the agent loop (and any provider) sees
# -----------------------------------------------------------------------------
def _spec(fn, input_schema: dict) -> dict:
    return {
        "name": fn.__name__,
        "description": " ".join((fn.__doc__ or "").split()),
        "input_schema": input_schema,
    }


TOOL_SPECS: list[dict] = [
    _spec(get_pipeline_run, {
        "type": "object",
        "properties": {
            "pipeline_name": {"type": "string", "description": "Display name of the Fabric pipeline"},
        },
        "required": ["pipeline_name"],
    }),
    _spec(get_notebook_source, {
        "type": "object",
        "properties": {
            "notebook_name": {"type": "string", "description": "Display name of the Fabric notebook"},
        },
        "required": ["notebook_name"],
    }),
    _spec(list_lakehouse_tables, {
        "type": "object",
        "properties": {
            "lakehouse_name": {"type": "string", "description": "Display name of the Fabric lakehouse"},
        },
        "required": ["lakehouse_name"],
    }),
    _spec(query_sql_endpoint, {
        "type": "object",
        "properties": {
            "sql_query": {"type": "string", "description": "T-SQL query to run (not Spark SQL)"},
            "lakehouse_name": {"type": "string", "description": "Lakehouse display name (defaults to SalesLakehouse)"},
        },
        "required": ["sql_query"],
    }),
    _spec(get_pipeline_definition, {
        "type": "object",
        "properties": {
            "pipeline_name": {"type": "string", "description": "Display name of the Fabric pipeline"},
        },
        "required": ["pipeline_name"],
    }),
    _spec(query_warehouse_endpoint, {
        "type": "object",
        "properties": {
            "sql_query": {"type": "string", "description": "T-SQL query to run against the warehouse"},
            "warehouse_name": {"type": "string", "description": "Display name of the Fabric warehouse"},
        },
        "required": ["sql_query", "warehouse_name"],
    }),
]

TOOL_FUNCTIONS = {
    "get_pipeline_run": get_pipeline_run,
    "get_notebook_source": get_notebook_source,
    "list_lakehouse_tables": list_lakehouse_tables,
    "query_sql_endpoint": query_sql_endpoint,
    "get_pipeline_definition": get_pipeline_definition,
    "query_warehouse_endpoint": query_warehouse_endpoint,
}


def execute_tool(name: str, arguments: dict | None) -> str:
    """Dispatch a tool call from the agent loop. Always returns a string —
    errors come back as readable messages the model can react to."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"Unknown tool '{name}'. Available tools: {sorted(TOOL_FUNCTIONS)}"
    try:
        return str(fn(**(arguments or {})))
    except TypeError as e:
        return f"Invalid arguments for {name}: {e}"
