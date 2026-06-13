# Wanda — Beta Roadmap

From hackathon prototype to testable product for real Microsoft Fabric users.

**Owners:** Matthew Arrogante, Claire Ann Bayoda **Status:** Post-hackathon (3rd place, GitHub Copilot SDK Hackathon, Web Summit Vancouver 2026\) **Goal:** Publish Wanda for beta testing by existing Microsoft Fabric users, delivered as a Fabric notebook. **Last updated:** *fill in as you go*

---

## TL;DR — Where We Are vs. Where We Need To Be

Wanda works. It demos beautifully. But it's a **hackathon prototype**, which means roughly 70% of the work to make it usable by anyone other than us is still ahead. That's normal. The job now is to be ruthless about what actually matters for beta — and what's a distraction.

**The single biggest blocker right now:** Wanda runs as a local Python CLI that requires Service Principal credentials, BYOK API keys, ODBC drivers, and `.env` setup. **No Microsoft Fabric user is going to get through that setup just to try a tool.** Solving the distribution problem is the whole game for the next 4-6 weeks.

**The notebook-based distribution idea is the right one.** This roadmap is structured around making that real.

---

## Guiding Principles

1. **Beta means real users, not us.** If we have to be in the loop to make it work, it's not beta yet.  
2. **Cut everything that doesn't make beta possible.** Cool features can wait. Stability can't.  
3. **The notebook is the product.** Until a Fabric user can open a notebook, fill in one cell, run it, and get a report — we don't have a product. We have a demo.  
4. **Honest telemetry beats vibes.** We need to know what's actually working when real users try it.  
5. **Two-person team.** Scope must reflect reality.

---

# Phase 1 — Pre-Beta Hardening (Weeks 1-2)

Goal: Wanda doesn't break under realistic conditions.

These are the things that *will* hit us the moment a real user runs Wanda on their own Fabric workspace. Most of them weren't issues in our demo because we controlled the environment.

## 1.1 Error Handling & Edge Cases

- [ ] **Fabric REST API rate limits** — what happens when we hit 429? Right now: probably an unhandled exception. Need: exponential backoff with retry.  
- [ ] **Token expiry mid-investigation** — Service Principal tokens expire. Need to refresh transparently.  
- [ ] **Empty / null responses** — `get_pipeline_run` can return no runs, `failureReason` can be missing. Audit every parser for `None` handling.  
- [ ] **Notebook source extraction edge cases** — non-Python notebooks (Spark SQL, T-SQL), notebooks with binary cells, notebooks larger than 2KB display limit, notebooks that have never been run.  
- [ ] **SQL endpoint not provisioned** — Fabric Lakehouse SQL endpoints take 1-2 minutes to come up. Wanda should detect and message clearly, not crash.  
- [ ] **Pipeline with 0 activities** — empty draft pipelines.  
- [ ] **Pipeline with unsupported activity types** — Dataflow Gen2, Web activity, Variable activities. Wanda currently only handles notebooks, copy, and SP cleanly.  
- [ ] **Service Principal lacks permission** — clear error message telling user *which* permission is missing.  
- [ ] **LLM context window overflow** — for big pipelines with long notebook sources, we'll bust the model's context. Need truncation strategy.

## 1.2 Security & Credentials

- [ ] **Never log credentials** — audit log statements for accidental secret leakage.  
- [ ] **Credential validation at startup** — fail fast if `.env` is malformed, instead of failing mid-investigation.  
- [ ] **Document the minimum Fabric permissions needed** — exact role \+ tenant settings, with screenshots in setup guide.  
- [ ] **Rotate the Anthropic API key strategy for beta** — testers shouldn't see ours. Either each tester brings their own, or we host (see Phase 2).  
- [ ] **`.env.example` audit** — confirm no real secrets ever committed.  
- [ ] **GitHub secret-scanning enabled** on the repo.

## 1.3 Testing

- [ ] **Unit tests for the MCP server's 5 tools** — at minimum, happy path \+ 2 error cases each.  
- [ ] **Mock the Fabric API** — `responses` or `respx` to test without hitting real Fabric.  
- [ ] **Snapshot tests for report rendering** — `render_report.py` shouldn't silently regress when prompts change.  
- [ ] **End-to-end smoke test** — one script that runs investigation \+ scan against our demo workspace, checks both produce valid reports.  
- [ ] **GitHub Actions CI** — run the test suite on every PR.

## 1.4 Code Quality

- [ ] **Type hints** across `wanda.py` and `fabric_mcp_server.py`.  
- [ ] **Logging instead of print()** — use Python `logging` so we can switch verbosity.  
- [ ] **Refactor the system prompts out of `wanda.py`** — move INVESTIGATE\_MESSAGE and SCAN\_MESSAGE into `prompts/*.md` so they're versionable and editable without touching code.  
- [ ] **Configuration class** — replace scattered `os.environ` reads with a single typed config object.

---

# Phase 2 — Notebook Distribution (Weeks 2-4)

Goal: A Fabric user can clone a notebook, fill in three values, click "Run all," and get a Wanda report.

This is the biggest unknown and the most important deliverable. Everything else is in service of this.

## 2.1 The Core Question: How Does Wanda Run *Inside* a Notebook?

Right now Wanda runs via:

- A local Python process (`wanda.py`)  
- That spawns the MCP server as a subprocess (`fabric_mcp_server.py`)  
- Talking over stdio (JSON-RPC)

A Fabric notebook is a Jupyter-like environment running PySpark. It cannot spawn subprocesses the same way. We have three options:

### Option A — Inline mode (recommended for beta)

Refactor Wanda so it can run **without the MCP subprocess**. The 5 tools become regular Python functions imported directly into the notebook. The agent loop runs inline. We lose the MCP abstraction (which was great for hackathon storytelling) but gain the ability to actually run in a notebook.

**Tradeoff:** Less elegant architecturally. We can still describe it as MCP-compatible by keeping the tool signatures and the FastMCP wrapping for the local/CLI version. The notebook version is a "thin client" view of the same tools.

### Option B — Hosted backend

Wanda runs on a cloud function (Azure Functions, Cloud Run). The notebook is a thin client that POSTs the pipeline name and gets back the report. We pay for the LLM tokens.

**Tradeoff:** We absorb cost. Requires hosting infrastructure. But far simpler for users — they don't need an Anthropic key.

### Option C — Hybrid

Notebook prompts user for Anthropic API key the first time, stores it as a Fabric workspace secret. Wanda runs inline in the notebook using their key. Best of both worlds, slightly more setup.

**Decision needed by end of Week 2\.** I'd lean Option A for beta — fastest to ship, lets us learn before we commit to hosting costs. Revisit Option B/C after we have 10+ testers and real usage data.

- [ ] **Pick the model.** Document the decision.  
- [ ] **Spike: get Wanda's investigation loop running in a Fabric notebook cell.** Even ugly — just prove it's possible.  
- [ ] **Authentication inside Fabric** — Fabric notebooks have access to the workspace identity via `mssparkutils.credentials`. This may let us *skip* Service Principal setup entirely for users running inside their own workspace. Huge if true.

## 2.2 The Notebook UX

What the tester actually sees:

┌─────────────────────────────────────────────────┐

│ Cell 1: Setup (provided by us — they don't edit)│

│   \!pip install wanda-fabric                     │

│   from wanda import Wanda                       │

├─────────────────────────────────────────────────┤

│ Cell 2: Configure (they edit one value)         │

│   wanda \= Wanda(                                │

│       anthropic\_api\_key="sk-ant-...",           │

│       \# or set as workspace secret              │

│   )                                             │

├─────────────────────────────────────────────────┤

│ Cell 3: Investigate (they edit pipeline name)   │

│   report \= wanda.investigate("MyPipeline")      │

│   report.display()                              │

└─────────────────────────────────────────────────┘

- [ ] **Pip-installable package** — `pip install wanda-fabric` on PyPI. Bundles the agent, the tools, the prompts.  
- [ ] **The `Wanda` class API** — simple, importable, three methods: `.investigate(pipeline_name)`, `.scan(pipeline_name)`, `.report.display()`.  
- [ ] **Report rendering inline in the notebook** — display the HTML report directly in the notebook output cell, not as a saved file.  
- [ ] **The "template notebook"** — a `.ipynb` we ship in the repo. Testers download → upload to their Fabric workspace → fill in one cell → run.

## 2.3 Authentication: The Hard Part

For each tester:

- They need to authenticate to **their own Fabric workspace** (so Wanda can read pipeline runs there)  
- They need access to an **LLM** (their Anthropic key, or we host)

The default Fabric notebook identity (`mssparkutils.credentials.getToken('fabric')`) should work for the first part — Wanda would inherit the notebook's permissions. **This eliminates Service Principal setup for testers.** Verify this in the Week 2 spike.

- [ ] **Confirm `mssparkutils.credentials` gives us the access we need** (pipeline runs, notebooks, lakehouse, SQL endpoint).  
- [ ] **Fallback to explicit Service Principal** for users who need to scope tighter.  
- [ ] **Secrets management** — document how testers store their Anthropic key in Fabric (workspace secret, Key Vault, or inline).

## 2.4 Documentation for Testers

- [ ] **Quickstart guide** — 5-step setup, with screenshots of every click.  
- [ ] **"What Wanda does" page** — plain English, no marketing.  
- [ ] **"What Wanda CAN'T do yet" page** — set expectations honestly. Beta users are forgiving when they know the gaps.  
- [ ] **Troubleshooting page** — top 10 errors testers will hit, with fixes.  
- [ ] **Privacy / data usage statement** — what Wanda sends to the LLM (notebook source, schema, error messages), what it doesn't (data values, secrets).

---

# Phase 3 — Telemetry & Feedback (Week 4\)

Goal: We learn what's actually happening when testers try Wanda.

Without telemetry, beta tells us nothing. We can't fix what we can't see.

## 3.1 What to Instrument

- [ ] **Run started / completed / errored** with anonymous tester ID \+ timestamp.  
- [ ] **Which tools the agent called** (helps us see if the investigation logic generalizes).  
- [ ] **Pipeline shape** — number of activities, types, depth — not the actual pipeline content.  
- [ ] **Investigation outcome** — did Wanda produce a report? How long did it take? How many tokens?  
- [ ] **Tester feedback button** in the notebook — "Was this report useful? 👍 / 👎 / 💬"

## 3.2 What NOT to Capture

- [ ] **No pipeline names, table names, or column names** — privacy-sensitive.  
- [ ] **No notebook source code.**  
- [ ] **No query results or data values.**  
- [ ] **No error messages from user pipelines** — these can contain PII or business data.

We send *aggregate signals*, not content. State this explicitly in the privacy doc.

## 3.3 Feedback Channels

- [ ] **GitHub Discussions** on the repo — public, async, low-friction.  
- [ ] **A simple feedback form** linked from the notebook (Tally, Typeform, or a Google Form).  
- [ ] **Optional: a Discord or Slack** for testers — only if 10+ active users justify it.

---

# Phase 4 — Feature Expansion (Weeks 4-8, *only after beta is live*)

Goal: Cover the failure modes Wanda doesn't handle well today.

Do not start any of these until Phase 1-3 are done. Resist the temptation.

## 4.1 More Activity Types

Currently Wanda handles notebook, copy, and stored procedure activities well. Real Fabric pipelines also use:

- [ ] **Dataflow Gen2** — needs a tool to fetch dataflow definition \+ transformation steps.  
- [ ] **Lookup** activity — fetch the query, check the source.  
- [ ] **Script** activity — T-SQL inline.  
- [ ] **Web** activity — REST calls.  
- [ ] **ForEach / If / Switch** — control flow, makes investigation paths branchier.

Each one is a new MCP tool \+ a new section in the system prompt. Estimate \~2 days each.

## 4.2 Investigation Quality

- [ ] **Better failed-activity detection** in `get_pipeline_run` — current regex misses some patterns. Replace with structured parsing of Fabric's response.  
- [ ] **Cross-pipeline reasoning** — when activity B fails because activity A (in a different pipeline) didn't produce data. Wanda doesn't see this today.  
- [ ] **Historical context** — "this pipeline has failed 4 times this week with the same error" is more useful than "it failed once."  
- [ ] **Schema drift detection in scan mode** — already partially there. Tighten up.

## 4.3 Output Improvements

- [ ] **Markdown report option** — for embedding in Teams / Slack / GitHub issues.  
- [ ] **Optional: open a GitHub issue / Jira ticket** with the report as the body (with user consent).  
- [ ] **Compare two investigations** — same pipeline, different runs, what changed.

## 4.4 Multi-LLM Support

Currently locked to Anthropic via BYOK. Add:

- [ ] **OpenAI** — same Copilot SDK supports it.  
- [ ] **Azure OpenAI** — for enterprise testers who can't use direct Anthropic.  
- [ ] **Local models via Ollama** — for the privacy-paranoid (Wanda runs locally, model runs locally, nothing leaves the box).

---

# Phase 5 — Pre-Launch Polish (Week 8\)

Goal: When testers tell their friends, the project looks legit.

- [ ] **Landing page** — `cmlabs.dev/wanda` or `wanda.cmlabs.dev`. One page: what it does, demo video, "request beta access" button.  
- [ ] **Demo GIFs in README** — not just static screenshots. People scroll past static.  
- [ ] **A blog post** — "What we learned building Wanda for the Microsoft hackathon" — technical, honest, posted on LinkedIn \+ Hacker News.  
- [ ] **A short loom video** — 2 minutes, "here's what Wanda does and how to install it." Different from the hackathon pitch video — this one is product-focused.

---

# Open Questions (Decide Together)

These are decisions Matthew \+ Claire need to make before Phase 2 starts. Don't let them sit.

1. **Will we ever monetize Wanda?** If yes, when? If no, are we OK with this being a high-effort portfolio piece?  
2. **Hosted backend (Option B) — yes or no?** If yes, we need a budget and an Azure Function set up.  
3. **CM Labs as a brand or just a project label?** Affects whether we incorporate, get a domain, take payments.  
4. **What's the maximum tester pool for beta?** 10? 50? 200? Capacity affects how much support we can give each one.  
5. **Who do we tell first?** Ve Sharma, Venkat, Paula, Ilya, Cecilia — they're all warm contacts who could share Wanda. But not everyone should hear about it on day one. Sequence the announcements.  
6. **License?** Currently public on GitHub but no LICENSE file. Pick one (MIT? Apache 2.0?) before testers show up.

---

# What We're NOT Doing (Important)

This is the "do not do" list. Adding to it is more valuable than adding to the do list.

- ❌ **Multi-platform support** (Databricks, Snowflake) — beautiful idea, but not before Fabric beta works.  
- ❌ **A UI / web app** — the notebook IS the UI.  
- ❌ **Auto-remediation** (Wanda fixes the pipeline) — too risky, too soon. Reports only.  
- ❌ **Customer support tooling** — until we have 50+ testers, GitHub Discussions is enough.  
- ❌ **A pitch deck rewrite / new branding sprint** — current deck is fine.  
- ❌ **Microsoft partnership conversations** — happy to take meetings if they happen, but not pursuing actively until the beta has data.

---

# Suggested Weekly Rhythm

- **Monday:** 30-min planning sync between Matthew \+ Claire. Pick 3-5 items from this doc for the week.  
- **Wednesday:** Mid-week check-in. Are we blocked?  
- **Friday:** Demo what you built. Even ugly. Update this doc.

Keep this file in the repo at `docs/ROADMAP.md`. Update it ruthlessly. It's not a contract — it's a working document.

---

# Sign-off Criteria for Beta

We are ready to publish for testing when ALL of these are true:

- [ ] A new tester can go from "I want to try Wanda" → "I have a report" in **under 15 minutes** without contacting us.  
- [ ] Wanda has run cleanly on at least **3 different Fabric workspaces** (not just ours).  
- [ ] All Phase 1 error-handling items are checked.  
- [ ] Telemetry is live and we can see runs happening.  
- [ ] Documentation answers the top 10 likely questions.  
- [ ] We have a way to receive feedback (form \+ GitHub Discussions).  
- [ ] Privacy statement is written and linked.

If any one of these is false, we don't ship. We fix it first.

---

*End of document.*  
