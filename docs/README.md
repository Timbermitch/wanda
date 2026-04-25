# Wanda

> An AI Data Engineer for Microsoft Fabric. Hours → minutes for pipeline root-cause analysis.

Wanda is an AI Data Engineer built on the **GitHub Copilot SDK** that
investigates failed Microsoft Fabric pipelines and produces evidence-backed
root-cause reports. The agent reaches Fabric through a custom **Model
Context Protocol (MCP) server** that wraps the Fabric REST API and SQL
endpoint.

Submitted to the **Vancouver Web Summit 2026 GitHub Copilot SDK Hackathon**.

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

```
┌──────────────────┐         ┌──────────────────────────┐
│   wanda.py       │   MCP   │  fabric_mcp_server.py    │       Microsoft
│   (agent loop)   │ ◄─────► │  (4 Fabric tools)        │ ────► Fabric
│   Copilot SDK    │  stdio  │  FastMCP                 │       REST + SQL
└──────────────────┘         └──────────────────────────┘
```

- `src/wanda.py` — Copilot SDK agent. Drives the LLM, makes tool decisions.
- `src/fabric_mcp_server.py` — MCP server exposing four tools over stdio.
- The Copilot SDK launches the MCP server as a subprocess automatically.

Because the tools are exposed over MCP, any MCP-compatible client (Claude
Desktop, Cursor, VS Code Copilot) can use them too — see `mcp.json`.

## Demo scenarios

Three demo pipelines in the Fabric workspace, each failing in a different way.
The agent takes a different investigation path for each:

**Scenario 1 — `LoadSalesPipeline`** (missing table)
1. `get_pipeline_run` → finds `TABLE_OR_VIEW_NOT_FOUND` for `SalesStaging`
2. `get_notebook_source` → reads the offending `INSERT INTO SalesStaging` line
3. `query_sql_endpoint` → confirms `SalesStaging` does not exist in the lakehouse

**Scenario 2 — `TransformSalesPipeline`** (code bug)
1. `get_pipeline_run` → finds `AttributeError: 'DataFrame' has no attribute 'Revenue'`
2. `get_notebook_source` → reads the offending `df.Revenue` reference
3. Skips SQL check — code bug, not a missing table

**Scenario 3 — `DailySalesETL`** (multi-activity ETL chain)
A 5-activity pipeline: Copy data → cleanup notebook → parallel branches (aggregate notebook + stored procedure) → summarize notebook.
1. `get_pipeline_run` → identifies `Aggregate_Data` as the failed activity in the chain
2. `get_notebook_source` → reads the notebook, finds wrong column name
3. Reports: Copy succeeded, cleanup succeeded, stored procedure succeeded — only `Aggregate_Data` failed

The divergent tool paths are the proof that the agent is genuinely agentic.

## Prerequisites

- Windows or macOS, Python 3.11+
- An Azure tenant with a Microsoft Fabric trial or capacity
- A Fabric workspace with a Lakehouse, demo pipelines, and notebooks
- An Entra ID App Registration (Service Principal) with Contributor access
- ODBC Driver 18 for SQL Server (for the SQL endpoint tool)
- The GitHub Copilot CLI installed (`npm i -g @github/copilot`)

## Setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/Timbermitch/wanda.git
cd wanda

# 2. Create a virtual environment and install dependencies
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
# Then edit .env with your Fabric tenant, workspace, and Service Principal values

# 4. Authenticate the Copilot CLI once
copilot
# Follow the device-code prompt to sign in
```

## Run

```bash
# Investigate the missing-table pipeline
python src/wanda.py LoadSalesPipeline

# Investigate the code-bug pipeline
python src/wanda.py TransformSalesPipeline

# Investigate the multi-activity ETL pipeline
python src/wanda.py DailySalesETL
```

You'll see the agent's narration, each MCP tool call as it happens, and the
final root-cause report.

## Repository layout

```
wanda/
├── src/
│   ├── wanda.py              Agent — Copilot SDK + MCP client
│   └── fabric_mcp_server.py  MCP server — 4 tools over Fabric APIs
├── docs/
│   └── README.md             This file
├── presentations/
│   └── Wanda.pptx            Hackathon deck
├── AGENTS.md                 Agent persona, rules, report format
├── apm.yml                   Agent Package Manifest (APM)
├── mcp.json                  MCP server config (for any MCP client)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Responsible AI notes

- Wanda is read-only. The agent calls Fabric REST and SQL endpoints in read
  mode only. It does not modify pipelines, notebooks, or table data.
- Credentials live in `.env` and are never logged or sent to the LLM. The
  Copilot SDK passes them to the MCP server as environment variables.
- The system message restricts Wanda to evidence-based reporting.
  Recommendations are descriptive ("change `Revenue` to `Amount`"), never
  prescriptive actions Wanda performs itself.
- Service Principal authentication scopes Wanda's access to a single workspace.

## Tech stack

- **Agent runtime:** GitHub Copilot SDK (Python)
- **Tool packaging:** Model Context Protocol (FastMCP)
- **Cloud:** Microsoft Fabric REST API, Fabric SQL endpoint, Microsoft Entra ID
- **Drivers:** Microsoft ODBC Driver 18 (SQL endpoint), Service Principal auth