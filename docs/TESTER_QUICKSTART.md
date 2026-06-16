# Try Wanda — 5-minute tester quickstart

Thanks for testing **Wanda**, an AI Data Engineer for Microsoft Fabric. When a
pipeline fails, Wanda investigates it for you and hands back an evidence-backed
root-cause report — right inside a Fabric notebook. This runs as **you**, using
your existing workspace access. No Azure setup, no Service Principal.

## What you need
1. **A Microsoft Fabric workspace** you can open (Admin/Member/Contributor) — your own project is perfect.
2. **A pipeline that has failed** in that workspace (or run one so it fails).
3. **An Anthropic API key** — get one at [console.anthropic.com](https://console.anthropic.com) → *API Keys*, and add a few dollars of credit. A run costs cents; you're billed by Anthropic directly.

## Run it (in a Fabric notebook)

Open a new notebook **in your workspace** and run these three cells.

**1. Install**
```python
%pip install -U "wanda-fabric[sql]"
```

**2. Connect (this is the whole setup — runs as you, nothing to register)**
```python
import os, notebookutils
os.environ["FABRIC_ACCESS_TOKEN"] = notebookutils.credentials.getToken("pbi")
os.environ["FABRIC_WORKSPACE_ID"] = "your-workspace-guid"   # the id in your workspace URL:
                                                            # app.fabric.microsoft.com/groups/<THIS>/
os.environ["ANTHROPIC_API_KEY"]   = "sk-ant-..."            # your Anthropic key
```

**3. Investigate the failed pipeline**
```python
from wanda import Wanda
report = Wanda().investigate("Your_Failed_Pipeline_Name")   # ← your pipeline's exact name
report.display()
```

That's it — you'll get a root-cause report inline.

**Audit a pipeline *before* it runs instead:**
```python
Wanda().scan("Your_Pipeline_Name").display()
```

## Tips for a smooth first run
- **Point at the pipeline that actually failed.** If you use a master → child setup, point at the **child** pipeline that failed (Wanda investigates one pipeline at a time today).
- **Skip the SQL token for now.** Leave `FABRIC_SQL_ACCESS_TOKEN` unset on your first run — the investigation works without it (you'll see a clean "SQL skipped" note, not an error).
- **Token expired? (401 after a long session)** Just re-run cell 2 to grab a fresh token.

## If something errors
| You see | Do this |
|---|---|
| `401` on the first tool call | Re-run cell 2 for a fresh token; if it persists, tell us — the token audience may need a tweak |
| `403` | Your account needs at least **Viewer** on the workspace |
| `Pipeline ... not found` | Use the exact pipeline display name from your workspace |
| `credit balance is too low` | Add a little credit to your Anthropic key |

## Privacy
Wanda is **read-only** — it never changes your workspace. It sends notebook source,
pipeline structure, and table/column names to your own Anthropic key so the model
can reason; during a pre-run scan it may read a *small sample* of rows. It never
sends your data values or secrets.

## Tell us how it went
This is the whole point — your feedback shapes Wanda:

👉 **Feedback form: [link]**

Tell us: did it find the real root cause? was the report clear? how long would this
have taken you by hand? Two minutes, and it decides what we build next. Thank you! 🙏
