# Wanda

> An AI Data Engineer for Microsoft Fabric. Hours → minutes for pipeline root-cause analysis.

Wanda is an AI Data Engineer that investigates failed Microsoft Fabric pipelines
and produces evidence-backed root-cause reports. It drives an LLM (Claude by
default) through an agentic tool-use loop, reaching Fabric directly through the
Fabric REST API and SQL endpoint.

A CM Labs product — born at the **GitHub Copilot SDK Hackathon (Web Summit
Vancouver 2026)** and since rebuilt for real-world use.

## Problem

When a Fabric pipeline fails, a data engineer typically spends 1–2 hours on:
- Reading raw failure logs
- Opening each failed notebook to read the source
- Querying the lakehouse to verify what tables/columns actually exist
- Cross-referencing all of the above to find the root cause

Most of that work is mechanical evidence-gathering, not analysis. Wanda
takes ownership of the routine investigation so the human data engineer
can focus on the fix.

## Solution

Wanda automates the evidence chain a senior data engineer would walk:

1. Pulls the failed pipeline run from the Fabric REST API
2. Reads the source of the failing notebook
3. Decides whether to query the SQL endpoint based on the error type
4. Writes a definitive root-cause report — no guessing

The agent makes those decisions itself. Different failures lead to different
investigation paths.

## Architecture

The model talks to its provider **directly**, and the Fabric tools are plain
Python functions called **inline** — no subprocess — which is what lets Wanda
run anywhere from a CLI to a Fabric notebook.

```
   Wanda class / CLI  (wanda.core / wanda.cli)
        │   .investigate() · .scan() → WandaReport
        ▼
   Agent loop  (wanda.agent)         bounded tool-use loop
        ├──────────────► LLM provider  (wanda.llm_provider)
        │                Claude (Anthropic / Azure) · GPT (Azure OpenAI)
        └──────────────► 6 Fabric tools (wanda.fabric_tools)  ──► Microsoft
                         inline — no subprocess                   Fabric
                                                                 REST + SQL
```

- `wanda.core` — the `Wanda` class and `WandaReport`. Imports the tools and runs the loop inline.
- `wanda.cli` — the `wanda` command-line entry point.
- `wanda.agent` — provider-agnostic tool-use loop (bounded steps, result truncation, token accounting).
- `wanda.llm_provider` — swappable LLM backend. `WANDA_PROVIDER` selects `anthropic`, `azure-openai`, or `azure-anthropic`. The Anthropic path uses prompt caching.
- `wanda.fabric_tools` — the 6 Fabric tools as plain functions (REST + SQL), with retry/backoff and token refresh.
- `wanda.mcp_server` — a thin **MCP** wrapper over the *same* 6 tools, so any MCP-compatible client (Claude Desktop, Cursor, VS Code) can use them too — see `mcp.json`.

## Use it as a library (notebook or script)

```python
from wanda import Wanda

wanda = Wanda(anthropic_api_key="sk-ant-...")   # or rely on .env
report = wanda.investigate("LoadSalesPipeline")
report.display()                                 # inline HTML in a notebook
print(report.text)                               # or the raw text
```

## Demo scenarios

Demo pipelines in the Fabric workspace, each failing in a different way. The
agent takes a different investigation path for each.

**Scenario 1 — `LoadSalesPipeline`** (missing table — *verified live run*)
1. `get_pipeline_run` / `get_pipeline_definition` → identifies the failing activity `Write_Gold_Orders`
2. `get_notebook_source` (×3) → reads the notebooks and finds `Write_Gold_Orders` reads `order_enriched` (missing the **s**) instead of `orders_enriched`
3. `query_sql_endpoint` → confirms `orders_enriched` exists in the lakehouse but `order_enriched` does not → `TABLE_OR_VIEW_NOT_FOUND`
4. Reports the exact line to fix

**Scenario 2 — `TransformSalesPipeline`** (code bug)
1. `get_pipeline_run` → finds an `AttributeError` (e.g. a wrong DataFrame column reference)
2. `get_notebook_source` → reads the offending line
3. Skips the SQL check — code bug, not a missing table

**Scenario 3 — `DailySalesETL`** (multi-activity ETL chain)
A multi-activity pipeline: Copy → cleanup notebook → parallel branches (aggregate notebook + stored procedure) → summarize notebook.
1. `get_pipeline_definition` → walks the activity graph
2. `get_pipeline_run` → identifies the single failed activity in the chain
3. Reports which activities succeeded and which one failed, with the root cause

The divergent tool paths are the proof that the agent is genuinely agentic.

## Prerequisites

- Windows or macOS, Python 3.11+
- An Azure tenant with a Microsoft Fabric trial or capacity
- A Fabric workspace with a Lakehouse, demo pipelines, and notebooks
- An Entra ID App Registration (Service Principal) with access to the workspace
- ODBC Driver 18 for SQL Server (for the SQL endpoint tool)
- An **Anthropic API key** (default), *or* an Azure OpenAI / Azure-hosted Claude deployment

## Install

Wanda is a pip-installable package (`wanda-fabric`).

```bash
pip install "wanda-fabric[sql]"
```

The `[sql]` extra adds `pyodbc` for the SQL-endpoint tools; `[mcp]` adds `fastmcp`
for the standalone MCP server; `[all]` adds both. The core install stays light for
notebooks. The SQL tools also need the OS-level **ODBC Driver 18 for SQL Server**.

**New here?** [docs/GETTING_STARTED.md](GETTING_STARTED.md) walks the full first-time
setup (Service Principal, ODBC driver, API key) in ~15 minutes.

*CM Labs internal — develop from the private repo:*

```bash
git clone https://github.com/cmlabs-ai/wanda.git
cd wanda
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -e ".[all]"          # core + sql (pyodbc) + mcp (fastmcp) extras
```

Then configure credentials:

```bash
cp .env.example .env
# Edit .env: Fabric Service Principal values + ANTHROPIC_API_KEY (and WANDA_PROVIDER if not "anthropic")
```

No GitHub Copilot login is required — Wanda calls the model provider directly.

## Run

Point Wanda at a pipeline that failed in **your** workspace:

```bash
# Investigate a failed pipeline (default mode)
wanda "Your Failed Pipeline Name"

# Pre-run scan: audit a pipeline before it runs
wanda "Your Pipeline Name" --scan

# (equivalently: python -m wanda "Your Pipeline Name")
```

You'll see each tool call logged to stderr as it happens, the final root-cause
report printed, and a polished HTML report saved to `./reports/`.

> The demo scenarios below run against CM Labs' own demo workspace
> (`LoadSalesPipeline`, etc.) — substitute your own pipeline names.

## Configuration

Set in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `FABRIC_TENANT_ID` / `FABRIC_CLIENT_ID` / `FABRIC_CLIENT_SECRET` / `FABRIC_WORKSPACE_ID` | Service Principal + workspace |
| `WANDA_PROVIDER` | `anthropic` (default) · `azure-openai` · `azure-anthropic` |
| `ANTHROPIC_API_KEY` | for the default `anthropic` provider |
| `WANDA_MODEL` | optional model override (default `claude-sonnet-4-6`) |
| `AZURE_OPENAI_*` / `AZURE_ANTHROPIC_*` | for the Azure providers |
| `WANDA_LOG_LEVEL` | logging verbosity (default `INFO`) |

## Repository layout

```
wanda/
├── src/wanda/                the installable package (wanda-fabric)
│   ├── __init__.py           exports Wanda, WandaReport
│   ├── core.py               Wanda class + WandaReport
│   ├── cli.py                command-line entry point (the `wanda` command)
│   ├── __main__.py           enables `python -m wanda`
│   ├── agent.py              provider-agnostic tool-use loop
│   ├── llm_provider.py       swappable LLM backend (Anthropic / Azure OpenAI)
│   ├── fabric_tools.py       the 6 Fabric tools (REST + SQL), called inline
│   ├── mcp_server.py         thin MCP wrapper over the same tools
│   ├── config.py             typed, fail-fast configuration
│   ├── log_setup.py          logging (stderr)
│   ├── render_report.py      text → self-contained HTML report
│   └── prompts/              investigate.md, scan.md (bundled package data)
├── notebooks/                template notebook for Fabric users
├── tests/                    34 offline tests (providers, agent loop, config)
├── docs/                     this README + architecture/business docs
├── presentations/            decks
├── reports/                  generated HTML reports (gitignored)
├── pyproject.toml            packaging + dependencies
├── mcp.json                  MCP server config (for any MCP client)
└── .env.example
```

## Responsible AI notes

- **Read-only — enforced in code.** Wanda calls Fabric REST and SQL endpoints in read mode only; the SQL tools reject anything that isn't a `SELECT`/`WITH` query, so Wanda cannot modify pipelines, notebooks, or table data.
- **Secrets stay local.** Credentials live in `.env` (gitignored) and are never logged, sent to the LLM, or written into reports.
- **Minimal data exposure.** Notebook source, pipeline structure, and table/column names go to the LLM so it can reason. A pre-run scan may read a *small sample* of rows (e.g. `SELECT TOP 1 *`) to validate data — never bulk data.
- **Evidence-based.** The system prompts restrict Wanda to evidence from its tool calls. Recommendations are descriptive ("change `order_enriched` to `orders_enriched`"), never actions Wanda performs itself.
- **Scoped access.** Service Principal authentication scopes Wanda's access to a single workspace.

## Tech stack

- **Agent runtime:** custom tool-use loop calling the LLM provider directly (Anthropic Messages API / Azure OpenAI), dependency-light (`requests`, no vendor SDKs)
- **Tools:** plain Python functions, also exposed via the Model Context Protocol (FastMCP)
- **Cloud:** Microsoft Fabric REST API, Fabric SQL endpoint, Microsoft Entra ID
- **Drivers:** Microsoft ODBC Driver 18 (SQL endpoint), Service Principal auth

## Origin

Wanda began at the **GitHub Copilot SDK Hackathon** (Web Summit Vancouver 2026),
where the original prototype ran on the GitHub Copilot SDK with an MCP subprocess.
It has since been rebuilt by **CM Labs** to call its model provider directly,
run inline (notebook-ready), and switch LLM providers via configuration —
the foundation for a Microsoft Fabric beta.
