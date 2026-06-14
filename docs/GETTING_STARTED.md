# Getting started with Wanda

Wanda is an AI Data Engineer for Microsoft Fabric. When a pipeline fails, Wanda
investigates it for you — reads the run, the notebook source, and the lakehouse —
and hands back an evidence-backed root-cause report. It can also audit a pipeline
*before* it runs.

This guide takes you from nothing to your first report. Budget **15–20 minutes**
the first time (most of it is the one-time Fabric setup).

---

## What you'll need (one-time)

| # | Thing | Why | Roughly how long |
|---|---|---|---|
| 1 | Python 3.11+ and `pip install wanda-fabric[sql]` | The tool itself | 2 min |
| 2 | Microsoft ODBC Driver 18 for SQL Server | Lets Wanda query your lakehouse | 3 min |
| 3 | An Anthropic API key with a small balance | The LLM that does the reasoning | 3 min |
| 4 | A Fabric **Service Principal** with read access to your workspace | How Wanda reaches Fabric | 8 min |

You run Wanda against **your own** Fabric workspace with **your own** keys. Wanda
is read-only and never modifies anything (see [Privacy & safety](#privacy--safety)).

---

## 1. Install Wanda

```bash
pip install "wanda-fabric[sql]"
```

The `[sql]` extra adds `pyodbc`, which powers the lakehouse-query tool. Plain
`pip install wanda-fabric` works too, but the SQL checks (used to confirm missing
tables) will be disabled.

## 2. Install ODBC Driver 18

`pyodbc` needs the Microsoft ODBC driver at the OS level (pip can't install this):

- **Windows:** [Download ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) and run the installer.
- **macOS:** `brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release && brew install msodbcsql18`
- **Linux:** follow [Microsoft's apt/yum instructions](https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server) for `msodbcsql18`.

## 3. Get an Anthropic API key

1. Sign in at [console.anthropic.com](https://console.anthropic.com) → **API Keys** → create a key.
2. Add a small amount of credit under **Billing** (a few dollars is plenty — see [Cost](#cost)).

> Wanda uses Claude by default. You can instead point it at Azure OpenAI or
> Azure-hosted Claude — see `WANDA_PROVIDER` in [.env.example](../.env.example).

## 4. Create a Fabric Service Principal

A Service Principal is an app identity Wanda uses to call Fabric. In the
[Azure portal](https://portal.azure.com):

1. **Microsoft Entra ID** → **App registrations** → **New registration**. Name it
   e.g. `wanda-beta`, leave defaults, **Register**.
2. On the app's **Overview**, copy the **Application (client) ID** and the
   **Directory (tenant) ID** — these are `FABRIC_CLIENT_ID` and `FABRIC_TENANT_ID`.
3. **Certificates & secrets** → **New client secret** → copy the secret **Value**
   immediately (you can't see it again) — this is `FABRIC_CLIENT_SECRET`.

## 5. Grant the Service Principal access to your workspace

Fabric does **not** give a new app access to your data by default — you must add it.

1. In [Fabric](https://app.fabric.microsoft.com), open your workspace → **Manage access**.
2. **Add people or groups** → search for your app name (`wanda-beta`) → give it at
   least the **Viewer** role (read-only is enough for Wanda; **Contributor** also works).
3. Get the **workspace ID**: it's the GUID in the workspace URL
   (`app.fabric.microsoft.com/groups/<THIS-GUID>/...`) — this is `FABRIC_WORKSPACE_ID`.

> **Tenant setting:** if the app can't authenticate at all, an admin may need to
> enable *"Service principals can use Fabric APIs"* in the Fabric Admin portal.

## 6. Configure Wanda

Create a `.env` file in your working directory (copy [.env.example](../.env.example)):

```bash
FABRIC_TENANT_ID=...        # from step 4.2
FABRIC_CLIENT_ID=...        # from step 4.2
FABRIC_CLIENT_SECRET=...    # from step 4.3
FABRIC_WORKSPACE_ID=...     # from step 5.3
ANTHROPIC_API_KEY=...       # from step 3
```

In a **Fabric notebook**, set these with `os.environ[...]` instead — prefer Fabric
workspace secrets / Key Vault over pasting keys inline. See
[notebooks/Wanda_Template.ipynb](../notebooks/Wanda_Template.ipynb).

## 7. Run it

Point Wanda at a pipeline in **your** workspace that has actually failed:

```bash
# Investigate a failed pipeline (use YOUR pipeline's name)
wanda "Your Failed Pipeline Name"

# Audit a pipeline BEFORE you run it
wanda "Your Pipeline Name" --scan
```

You'll see each tool call logged as it happens, the root-cause report printed, and
a self-contained HTML report saved to `./reports/`.

> **No failed pipeline to test on?** Create a tiny one that's wrong on purpose —
> e.g. a notebook that reads a table name that doesn't exist — run it once so it
> fails, then point Wanda at it.

---

## Troubleshooting

| What you see | What it means | Fix |
|---|---|---|
| `Configuration problem: ... is not set` | A required env var is missing | Set it in `.env` (step 6) |
| `Authentication failed (401)` | Wrong client id/secret | Re-check `FABRIC_CLIENT_ID` / `FABRIC_CLIENT_SECRET` (step 4) |
| `Permission denied (403)` | SP has no role on the workspace | Add it under **Manage access** (step 5) |
| `Pipeline '...' not found` | That pipeline isn't in this workspace | Use a real pipeline name from *your* workspace |
| `credit balance is too low` | Anthropic key has no funds | Add credit (step 3.2) |
| `...query failed: ...driver...` | ODBC Driver 18 missing | Install it (step 2) |
| `SQL endpoint ... not provisioned yet` | Fresh lakehouse warming up | Wait 1–2 minutes and retry |

## Cost

Wanda pays per use through **your** Anthropic key. A typical investigation is a
handful of model turns and runs in the **low cents to ~tens of cents**. A large
multi-activity pipeline (more notebooks to read) costs more. You're billed by
Anthropic directly; Wanda adds nothing.

## Privacy & safety

- **Read-only.** Wanda only reads from Fabric. The SQL tools are restricted in code
  to `SELECT`/`WITH` queries — they refuse anything that would modify data.
- **What leaves your machine:** notebook source, pipeline structure, and table/column
  names go to *your* LLM provider so it can reason. During a pre-run **scan**, Wanda
  may read a *small sample* of rows (e.g. `SELECT TOP 1 *`) to validate data — never
  bulk data. Your secrets are never sent to the LLM or written into reports.
- **Scoped to one workspace** by the Service Principal you created. Grant it the
  least access it needs (Viewer is enough).

## Help us improve (optional)

You're an early tester — your feedback shapes Wanda. Three ways to share, all optional:

1. **The feedback form** (no setup): **[link — coming with your invite]**. Two minutes;
   the single most useful thing you can do.
2. **One-line feedback from a notebook** — if you've opted into telemetry (below):
   ```python
   report = wanda.investigate("My Pipeline")
   report.feedback(True, "nailed the missing-table root cause")   # or False, "missed it"
   ```
3. **Anonymous usage metrics** (opt-in). Set `WANDA_TELEMETRY=on` and
   `WANDA_TELEMETRY_URL` (from your invite) to share *operational* signal only —
   mode, duration, tool-call counts, token usage, success/error, and a random
   install id. **Never** your pipeline/table names, data, queries, or secrets.
   It's off until you turn it on, and it can never slow down or break a run.
