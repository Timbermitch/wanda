# Wanda — Work Log

A running record of every change we make to Wanda. The roadmap
([WANDA_ROADMAP.md](WANDA_ROADMAP.md)) is *the plan*; this file is *what we
actually did*. Each session gets a dated entry, **newest first**. Reference
roadmap items by their number (e.g. 1.1, 1.4) so the two stay linked.

Entry template:

```
## YYYY-MM-DD — <short title>
**Roadmap:** <phase/items touched>  ·  **Status:** done / in progress
**Files:** <files added/changed>

### What changed
- ...

### Why
- ...

### Verification
- ...

### Open / follow-ups
- ...
```

---

## 2026-06-17 — ✅ Token mode VERIFIED LIVE in a Fabric notebook
**Roadmap:** Phase 2 (validation)  ·  **Status:** ✅ passed end-to-end
**Files:** `notebooks/Wanda_Template.ipynb` (cleaned to valid nbformat)

### Result
- Matthew ran `wanda-fabric` 0.1.1 inside a real Fabric notebook with bring-your-own-token:
  `os.environ["FABRIC_ACCESS_TOKEN"] = notebookutils.credentials.getToken("pbi")`.
- **`getToken("pbi")` IS accepted by api.fabric.microsoft.com** — the previously-unverified
  REST audience is now CONFIRMED working live. No Service Principal, no app registration.
- `Wanda().investigate("DailySalesETL")` ran clean: 3 REST tool calls over 4 turns in 23.8s,
  default model claude-sonnet-4-6, prompt caching active, rendered an HTML root-cause report.
- SQL tools correctly auto-disabled (no `FABRIC_SQL_ACCESS_TOKEN`) via the startup INFO message,
  by design; the REST investigation still completed.

### Follow-ups
- Fabric's `.ipynb` importer 400s on generic notebooks; the reliable path is create-in-Fabric
  (or Export FROM Fabric to get an import-clean template). Template cleaned to valid nbformat regardless.
- **SECURITY:** test notebook had the Anthropic key inline → rotate it; push testers to Key Vault /
  workspace secrets.
- `FABRIC_SQL_ACCESS_TOKEN` audience for the SQL-endpoint tools still unverified live.

---

## 2026-06-16 — Bring-your-own-token auth: run in a Fabric notebook, no Service Principal (v0.1.1)
**Roadmap:** Phase 2 (adoption)  ·  **Status:** built + reviewed (3 lenses, 0 blockers); 0.1.1 wheel ready to publish
**Files:** `src/wanda/config.py`, `src/wanda/fabric_tools.py`, `.env.example`, `docs/GETTING_STARTED.md`,
`docs/README.md`, `notebooks/Wanda_Template.ipynb`, `tests/test_config.py`, `tests/test_fabric_tools.py`,
`pyproject.toml` + `src/wanda/__init__.py` (0.1.0 → 0.1.1)

### Why
Matthew wants to test Wanda on his own enterprise project but does **not** want to create an Entra app
registration + client secret (could trip his company's security review). Inside a Fabric notebook you can
authenticate as **your own identity**, so the Service Principal can be optional.

### What changed
- `require_fabric()` now needs `FABRIC_WORKSPACE_ID` + **EITHER** a token **OR** the full Service Principal.
- `get_token()` returns a supplied `FABRIC_ACCESS_TOKEN` directly — no app registration, no secret, no OAuth.
- SQL tools use `FABRIC_SQL_ACCESS_TOKEN` injected via the ODBC `SQL_COPT_SS_ACCESS_TOKEN` attribute; absent
  it they **skip cleanly** (the REST-based investigation still runs).
- 401/403 messages, the 401 log line, and a startup INFO are now **auth-mode-aware** (no misleading
  "Service Principal" wording in token mode); SQL failures hint at a wrong-audience token.

### Verification
- **49 tests pass** (+6 for token auth). Adversarial review (3 lenses) = **0 blockers**: gating correct,
  ODBC token struct **empirically byte-correct** (4-byte LE length + UTF-16-LE, attr 1256), SP path
  unchanged, no token leakage. Fixed every confirmed nit.
- **0.1.1 wheel built** (12 modules + LICENSE + prompts), sitting in `dist/`.

### ⚠️ UNVERIFIED against live Fabric (Matthew confirms in a notebook)
- That `getToken("pbi")` yields a token `api.fabric.microsoft.com` accepts (the SP path uses the
  `.../.default` audience). If REST calls 401, the audience needs adjusting — the new 401 message says so.
- The correct audience for `FABRIC_SQL_ACCESS_TOKEN` (the Fabric SQL endpoint — different from REST).

### Next
- Matthew: republish 0.1.1 (`python -m build`; `twine upload dist/*`) → test in a notebook.
- Then: feedback form + telemetry endpoint; invite DEP testers; Azure bake-off.

---

## 2026-06-14 — Opt-in telemetry + feedback loop (last beta blocker I own)
**Roadmap:** Phase 2 (beta prep)  ·  **Status:** client side built; endpoint + form are Matthew's
**Files:** new `src/wanda/telemetry.py`, `docs/FEEDBACK_FORM.md`, `tests/test_telemetry.py`;
changed `src/wanda/core.py`, `.env.example`, `docs/GETTING_STARTED.md`, `notebooks/Wanda_Template.ipynb`

### What changed
- `telemetry.py`: **opt-in** (`WANDA_TELEMETRY=on` + `WANDA_TELEMETRY_URL`), anonymous,
  fire-and-forget daemon-thread POST that can never block or break a run. Sends *operational*
  metrics only — event, status, mode, duration, tool_calls, turns, token usage, a random
  install id, version, python, os — and **never** pipeline/table names, queries, data, or secrets.
- `core._run()` emits a `run` event (ok/error; error = exception CLASS name only, never the message);
  `WandaReport.feedback(useful, note)` sends an anonymous 👍/👎 for notebook testers.
- `docs/FEEDBACK_FORM.md`: a paste-ready ~2-min form built around the three things a beta must
  learn — **accuracy, time saved, willingness-to-pay** — plus a "how to read the results" guide.
- Opt-in disclosure added to `.env.example`, `GETTING_STARTED.md`, and the notebook's closing cell.

### Verification
- **43 tests pass** (+5 telemetry: off-by-default · opt-in needs flag+URL · no-op when off ·
  leak-checked payload when on · `_post` swallows all errors).
- Behavioral check: off by default; opted-in payload carries only operational keys, leak-check clean.
- Wheel rebuilds clean: **12 modules** (telemetry incl.) + LICENSE + prompts bundled.

### Open / Matthew's to do
- Provide the collection endpoint (a Form / serverless URL): set `DEFAULT_TELEMETRY_URL` or hand
  testers `WANDA_TELEMETRY_URL` in the invite.
- Build the real feedback form from `FEEDBACK_FORM.md`; drop its link into GETTING_STARTED + notebook.
- Then: commit everything → publish to PyPI → invite first DEP testers.

---

## 2026-06-14 — Beta-readiness audit + on-ramp hardening
**Roadmap:** Phase 2 (beta prep)  ·  **Status:** blockers I own = cleared; 2 items need Matthew
**Files:** new `LICENSE`, `docs/GETTING_STARTED.md`, `tests/test_fabric_tools.py`; changed
`src/wanda/cli.py`, `src/wanda/fabric_tools.py`, `pyproject.toml`, `notebooks/Wanda_Template.ipynb`, `docs/README.md`

### What changed
- Ran a 4-lens beta-readiness audit (cold-start journey · robustness · beta-program · security).
  Engine + safety = ready (0 blockers each); on-ramp + beta-program = not-ready.
  **Verdict: not beta-ready yet — but the gap is the on-ramp, not the code.**
- **Distribution decided (Matthew):** publish `wanda-fabric` to PyPI; repo stays private.
- Cleared the on-ramp blockers I own:
  - CLI no longer dumps raw tracebacks — an invalid/unfunded key, wrong SP secret, or
    bad pipeline name now prints an actionable message + a GETTING_STARTED pointer (`cli.py`).
  - SQL tools are now read-only **in code**, not just by prompt: `_is_read_only_sql` refuses
    anything but `SELECT`/`WITH` before connecting (`fabric_tools.py`) + `tests/test_fabric_tools.py`.
  - `LICENSE` added (proprietary beta-evaluation — have counsel review before wide release).
  - `pyproject.toml`: `license` + full classifiers; the built wheel now bundles `LICENSE`.
  - `docs/GETTING_STARTED.md`: a real ~15-min tester walkthrough (install + ODBC Driver 18 +
    Anthropic key + Service Principal + workspace grant + run + troubleshooting + cost + privacy).
  - Notebook + README: active install line → `wanda-fabric[sql]`; examples generic-ized
    (no more `LoadSalesPipeline` for strangers); privacy note corrected (scan reads small row
    samples, not "no data values"); both link GETTING_STARTED.

### Verification
- **38 tests pass** (added 4 for the read-only guard); guard hand-checked on 13 edge cases,
  incl. underscore-protected names (`update_log`) and the subtle `SELECT … INTO` write.
- Fresh wheel builds cleanly with the new metadata; bundles `LICENSE`
  (`dist-info/licenses/LICENSE`) + both prompts + 11 modules; `[sql]`/`[mcp]`/`[all]` resolve.

### Open / follow-ups
- **Matthew:** (1) publish to PyPI — `python -m build` then `twine upload dist/*` (name is free);
  (2) stand up a feedback form + minimal opt-in telemetry (needs your accounts).
- Have counsel glance at `LICENSE` before a wide beta.
- `requirements.txt` still redundant with pyproject — recommend deleting it.
- Then commit everything + invite the first Data Engineering Pilipinas testers.

---

## 2026-06-14 — Wanda is a pip-installable package (`wanda-fabric`) + reviewed
**Roadmap:** Phase 2 (packaging + template notebook)  ·  **Status:** ✅ done, reviewed, fixes applied
**Files:** new `pyproject.toml`, restructured `src/*.py` → `src/wanda/` package
(`__init__.py`, `__main__.py`, `core.py`, `cli.py`, `agent.py`, `llm_provider.py`,
`fabric_tools.py`, `mcp_server.py` [was `fabric_mcp_server.py`], `config.py`,
`log_setup.py`, `render_report.py`, `prompts/*.md`); new `notebooks/Wanda_Template.ipynb`;
updated `mcp.json`, `tests/`, `docs/README.md`, `docs/WANDA_BETA_ARCHITECTURE.md`, `AGENTS.md`

### What changed
- **Restructured into a proper src-layout package.** Flat `src/wanda.py` split into
  `core.py` (Wanda + WandaReport + load_prompt), `cli.py` (the `wanda` command), and
  `__init__.py`/`__main__.py`. All internal imports are now package-relative.
- **`pyproject.toml`** — `wanda-fabric` v0.1.0, console script `wanda = wanda.cli:main`,
  light core deps (`requests`, `python-dotenv`) with optional extras `[sql]` (pyodbc),
  `[mcp]` (fastmcp), `[all]`. Prompts ship as package data (`wanda/prompts/*.md`).
- **Prompt loading** moved to `importlib.resources` so prompts resolve from the installed
  package, not a relative path. **Reports** now write to `./reports/` under the caller's
  CWD (env-overridable via `WANDA_REPORTS_DIR`), resolved at call time.
- **Template notebook** — 3-step tester experience (install → paste keys → `wanda.investigate(...).display()`).

### Review + fixes (3-lens adversarial workflow — no blockers/majors in the package itself)
- Reviewer empirically built sdist+wheel, installed into a clean venv, ran all 34 tests
  against the installed wheel, confirmed extras resolve and prompts are bundled.
- Fixed: notebook git-install used deprecated `#egg=` (silently dropped `[sql]`) → PEP 508
  `wanda-fabric[sql] @ git+…`; single-sourced `__version__` via `importlib.metadata`;
  broadened `load_prompt` except; `render_report` resolves the reports dir at call time;
  refreshed stale paths/tool-count/Copilot-SDK references in `fabric_tools` docstring,
  `WANDA_BETA_ARCHITECTURE.md`, and `AGENTS.md` (now 6 tools, direct-provider runtime).

### Verification
- Editable install works; `from wanda import Wanda` + `wanda.__version__` (0.1.0) work;
  prompts load via `importlib.resources`; `wanda LoadSalesPipeline` console script produced
  a correct **live** root-cause report; built wheel bundles `wanda/prompts/{investigate,scan}.md`
  + all 11 modules + the console entry point; all **34 tests pass** after the fixes.

### Open / follow-ups
- `requirements.txt` is now redundant with `pyproject.toml` (and contradicts the light-core
  design) — recommend deleting it; left in place pending the user's call.
- Commit the restructure to `cmlabs-ai/wanda` (user commits/pushes themselves).
- `WANDA_ROADMAP.md` / `docs/CMLABS_AZURE_SETUP.md` still mention the old Copilot SDK runtime
  in planning prose — low priority, historical.

---

## 2026-06-13 — ✅ First live run of the rebuilt Wanda — PASSED
**Roadmap:** Phase 1 verification  ·  **Status:** ✅ verified live end-to-end
**Files:** small fix to `src/wanda.py` (UTF-8 stdout + save-before-print)

### Result
- First attempt failed at the API only on $0 Anthropic balance (clean 400, not a code bug).
  User funded $5; re-ran `python src/wanda.py LoadSalesPipeline`.
- **Full success against the real Fabric workspace:** 7 tool calls / 5 turns / 98.5s →
  get_pipeline_run, get_pipeline_definition, 3× get_notebook_source, query_sql_endpoint.
  Correct diagnosis: `Write_Gold_Orders` reads misspelled `order_enriched` vs `orders_enriched`
  → TABLE_OR_VIEW_NOT_FOUND; cited notebook line + SQL confirmation (18 tables); concrete fix.
- **Verified live:** model `claude-sonnet-4-6` accepted ✅ · tool loop ✅ · prompt caching
  (cache_read_input_tokens ~9448 > 0) ✅ · HTML report saved ✅.
- One bug found & fixed mid-run: report `print()` crashed on Windows cp1252 vs an emoji in the
  report → main() now forces UTF-8 stdout/stderr and saves the HTML before printing.
- Observation (not a blocker): get_pipeline_run returned no failure detail this run; the agent
  adapted (definition + notebooks + SQL) and still nailed it. Future polish: harden get_pipeline_run.

### Next
- Commit the whole rebuild to a branch (still all uncommitted on main) — pending user go-ahead.
- Optional: also smoke-test --scan mode (different prompt/path).

---

## 2026-06-13 — Architecture + business presentation (self-contained animated HTML)
**Roadmap:** Phase 5 (pre-launch polish / pitch material)  ·  **Status:** done, reviewed
**Files:** added `presentations/wanda-overview.html`; fixed test count in `docs/WANDA_BETA_ARCHITECTURE.md`

### What changed
- Built a 16-slide self-contained animated HTML deck (no external deps; keyboard nav +
  autoplay + fullscreen → screen-recordable as a video): Wanda before → now → future, then
  the open-core + Azure Marketplace profitability model and a 3-scenario revenue projection.
- Grounded the financials with a research+model workflow (real Fabric adoption ~31K paid
  orgs/$2B+ ARR; comparable pricing Metaplane $1.5–3K/mo, Monte Carlo $25–50K ACV).

### The grounded model (replaces earlier placeholders)
- **Pricing:** $249/mo per Fabric workspace (Team tier); blended ACV ~$2,400/$2,700/$3,000.
- **Base case:** Y1 23 cust/$62K → Y2 55/$149K → Y3 130/$351K ARR; ~90–95% margin; both
  founders paid within Y1 (breakeven ≈ 18 paying workspaces). Conservative: stays a
  side-project ($22K Y3). Optimistic: ~$3.3M Y3. All gated on beta-validated pricing/conversion.

### Adversarial review (2 workflows: 1 research/model + 1 deck review, ~5 agents)
Deck review found 3 real issues → all fixed: "Before" said 6 tools (hackathon had 4);
`WANDA_PROVIDER=claude` (invalid → anthropic); $2,700 ACV mislabeled as whole-table (it's
Base only). Plus honesty refinements (price→ACV bridge, margin basis footnote, assumptions
disclaimer) + a fullscreen promise-rejection guard. HTML verified self-contained, 16 slides,
all revenue cells internally consistent (cust × ACV = ARR).

---

## 2026-06-12/13 — THE BIG ONE: Copilot SDK removed; direct provider architecture + Wanda class
**Roadmap:** Phase 2.1 Option A (inline mode) + 2.2 (Wanda class API) + 1.1/1.3/1.4 carryovers  ·  **Status:** done, verified offline; needs ONE live run
**Files:** rewrote `src/wanda.py`, `src/fabric_mcp_server.py`, `requirements.txt`; new `src/llm_provider.py`, `src/agent.py`, `src/fabric_tools.py`, `tests/` (34 tests), `docs/WANDA_BETA_ARCHITECTURE.md`; updated `src/config.py`, `src/render_report.py`, `.env.example`

### What changed
- **GitHub Copilot SDK runtime removed.** New stack: `wanda.py` (Wanda class + CLI) →
  `agent.py` (tool-use loop, 12-turn cap, 8K/result truncation, usage accounting) →
  `llm_provider.py` (neutral dialect; AnthropicProvider w/ 2-breakpoint prompt caching +
  AzureOpenAIProvider; `WANDA_PROVIDER` = anthropic | azure-openai | azure-anthropic) →
  `fabric_tools.py` (6 tools inline, lazy config, hardened REST). MCP server kept as a
  thin wrapper over the same tools.
- **`Wanda` class shipped** (roadmap 2.2): `.investigate()` / `.scan()` → `WandaReport`
  with `.save()` / `.to_html()` / `.display()` (inline notebook HTML). CLI contract preserved.
- Default model now **claude-sonnet-4-6** (`WANDA_MODEL` override); requirements.txt
  rebuilt minimal (requests, dotenv, fastmcp, pyodbc — Copilot SDK gone).

### Ultracode adversarial review (61 agents: 4 lenses → 3 refuters per finding)
19 findings → **13 confirmed, 6 refuted as false alarms. All 13 fixed**, incl. 4 major:
1. **Thinking blocks dropped on replay** → tool loop would 400 on thinking-enabled models
   (claude-fable-5). Fixed: `raw_content` passthrough replays assistant turns verbatim.
2. **Azure `finish_reason` never normalized** → truncation warnings could never fire on
   the Azure path. Fixed: length→max_tokens etc. mapping.
3. **gpt-5 reasoning tokens starve `max_completion_tokens=4096`** → empty final reports.
   Fixed: Azure budget 16384 + readable empty-turn fallback report.
4. **No timeouts on Fabric HTTP calls** → indefinite hangs. Fixed: 30s/60s + transport-
   error retries (also added to the LLM layer).
   Plus: incremental conversation cache breakpoint (the system-only one was a likely
   no-op below Sonnet's 2048-token floor), truncated-tool-call turns retried instead of
   executed, stale "GitHub Copilot SDK" report footer → "CM Labs", azure-anthropic auth
   errors now name the right env vars, placeholder detection for Azure template values.
   (Regression lens died on session limit → replaced with manual check: all 6 MCP tools
   registered w/ schemas+descriptions; stdout clean.)

### Verification
- 34/34 offline tests green (wire formats, agent loop incl. new edge cases, config).
- py_compile + import all 8 modules; MCP registration verified via FastMCP list_tools.
- **NOT yet verified live** — needs one real run (`ANTHROPIC_API_KEY` + live Fabric):
  model id, end-to-end tool loop, cache_read_input_tokens > 0.

### Open / follow-ups
- One live E2E run, then commit everything to a branch (still all uncommitted on `main`!).
- ~Jun 15: retry Azure deploys (Tier 1 quota) → credit test → Claude-vs-GPT bake-off.
- Next build: pip packaging + template notebook (Phase 2), GitHub Actions CI, beta proxy.
- Doc drift remains: README/AGENTS.md still describe the hackathon architecture.

---

## 2026-06-12 — Azure premium-model provisioning blocked on quota (Tier 1 pending)
**Roadmap:** Phase 2 (LLM hosting)  ·  **Status:** ⏳ blocked — waiting on quota (external)
**Files:** none (Azure portal work)

### What happened
- **Claude IS available in Azure Foundry** (real Anthropic models: sonnet-4-5/4-6, opus-4-8, haiku-4-5, fable-5). The Opus 4.8 Marketplace offer shows **"Azure benefit eligible"** + $0/mo subscription + pay-go tokens — so credit-coverage is *plausible* but still **unverified** (couldn't deploy to test).
- **All premium/frontier/third-party models are quota-blocked** on the new Founders Hub subscription: `claude-sonnet-4-6`, `claude-opus-4-8`, `gpt-5.5` all fail "insufficient quota." Only mainstream models (gpt-5, gpt-5-mini, gpt-4o) have default quota.
- Confirmed it's a **quota** problem, not region: Claude is supported in **East US 2** + Sweden Central (East US = not supported). Our project is in East US.
- Got a legit-looking Microsoft email (`azure-noreply@microsoft.com`): subscription eligible for auto-upgrade **Free Tier → Tier 1** within ~3 days (= more quota). Guidance: don't click the opt-out link; let it auto-upgrade; verify in portal.

### Decision / next
- ⏳ **Retry deploying `claude-sonnet-4-6` (East US 2 project) + `gpt-5.5` after ~2026-06-15** (post Tier 1). If they deploy → run the **credit-coverage test** (Cost Management).
- ✅ **Don't block on it — build Wanda now.** The model is a config switch via the provider abstraction: use **Claude via Anthropic direct** today → flip to **credit-funded Claude-on-Azure (East US 2)** when quota lands.
- East US Foundry leftovers (`cmlabs-wanda-dev` project/foundry/aoai) are empty/$0 — delete during cleanup.

---

## 2026-06-10 — Finalized beta LLM access + provisioning Azure OpenAI
**Roadmap:** Phase 2 distribution + Phase 3 telemetry groundwork  ·  **Status:** in progress
**Files:** updated `docs/WANDA_BUSINESS.md`

### Decision
- **Beta LLM = CM Labs-provided, free to testers** (no Anthropic account/billing). Behind a
  token-gated proxy, default to the **bake-off winner**: Azure OpenAI GPT-4o (credit-funded)
  if quality holds up, else Claude (cash, capped). **BYOK optional.** Proxy + telemetry on
  Azure credits → seeds the Stage 3 backend.
- **Product (later) = freemium:** free Azure OpenAI tier + Claude "Recommended" premium.
- Rationale: audience is **Data Engineering Pilipinas** (~38k, education-first, friction-
  sensitive) — removing payment friction maximizes beta participation; LLM cost is trivial/capped.

### Provisioning started
- Creating **Azure OpenAI `cmlabs-wanda-dev-aoai`** in `cmlabs-wanda-dev-rg`, **East US**
  (best model availability), **Standard S0** (pay-per-token; no idle cost). Next: deploy **gpt-4o**.

### Next
- Deploy gpt-4o → **quality bake-off** (Claude-Sonnet vs GPT-4o on the demo pipelines) → wire
  the winner. Then build the **provider abstraction** + the **beta proxy**.

---

## 2026-06-10 — Business model one-pager
**Roadmap:** company/strategy (informs Phase 2 distribution + monetization)  ·  **Status:** draft for founders to react to
**Files:** added `docs/WANDA_BUSINESS.md`

### What changed
- Wrote a plain-language business one-pager: **open-core + Azure Marketplace SaaS**. Free
  BYOK notebook tier (costs us $0) for adoption; paid auto-run/Teams-Slack/history tier for
  revenue; sold via Azure Marketplace (spends customers' existing Microsoft commitment).
- Includes placeholder profit math (~$200 price − ~$40 cost ≈ ~$160/customer/mo, ~80%),
  scaling table, honest risks (Microsoft could build it; narrow TAM; trust bar; useful≠paid),
  and the key validation question to ask testers about price.

### Why
- Matthew asked to simplify "how do we make profit." Captured it so he + Claire have one
  reference, and so the beta is pointed at the one unknown that matters: **will people pay,
  and how much.**

### Open / follow-ups
- Validate **price** during beta ("would you pay $200/mo if it ran automatically + posted to Slack?").
- Don't build the hosted/automated backend until the beta proves demand.
- Decisions for later: bundle LLM cost vs customer's own Azure OpenAI; exact tier features.

---

## 2026-06-06 — CM Labs Azure / Founders Hub setup plan
**Roadmap:** company foundation (precedes Wanda Phase 2 hosting/distribution)  ·  **Status:** in progress (application in review)
**Files:** added `docs/CMLABS_AZURE_SETUP.md`

### What changed
- CM Labs won the GitHub Copilot SDK Hackathon (Web Summit Vancouver) → invited to
  **Microsoft for Startups (Founders Hub)** via referral. Application submitted, **in
  review** (up to 3 business days). Active now: **$1,000 starter credit, exp Sep 2, 2026**
  on "Azure subscription 1". On approval: up to **$150K** credits (staged, ~2-yr window)
  + Azure OpenAI + GitHub Copilot Enterprise (1 yr) + a Microsoft/GitHub social feature.
- Wrote `docs/CMLABS_AZURE_SETUP.md` — the foundation-first runbook (identity/MFA, cost
  budgets, naming + **per-product tagging**, claim perks, region) with do-now / do-not-yet /
  verify-on-approval checklists.

### Why
- Maximize the reward without waste: the highest-value first moves cost **$0 of credit**
  (identity, governance, tagging, claiming non-credit perks). Credits are time-boxed and
  use-it-or-lose-it, and "$150K" is a staged ceiling — so plan frugally and get per-product
  cost visibility in place before any app (Wanda first) provisions resources.

### Open / follow-ups
- On approval: confirm *granted* credit amount, expiry start, target subscription, and
  whether credits cover Fabric F-SKUs + Azure OpenAI.
- Don't deploy the portal AI-app templates on the $1,000 starter; bookmark the Azure
  OpenAI sample as reference for Wanda's future credit-funded hosted tier.
- Build the thin model-provider abstraction in Wanda so Claude (cash/BYOK) ↔ Azure OpenAI
  (credits) is a config switch (Claude isn't on Azure).

---

## 2026-05-30 — Phase 1 code-hardening pass (round 1)
**Roadmap:** Phase 1 — 1.1 (error handling), 1.2 (credential validation), 1.4 (code quality)  ·  **Status:** done (offline-verified; not yet committed)
**Files:** added `prompts/investigate.md`, `prompts/scan.md`, `src/config.py`, `src/log_setup.py`; changed `src/wanda.py`, `src/fabric_mcp_server.py`

### What changed
- **Prompts out of code (1.4).** `INVESTIGATE_MESSAGE` / `SCAN_MESSAGE` moved verbatim
  into `prompts/investigate.md` and `prompts/scan.md`; `wanda.py` loads them at runtime
  via `load_prompt()`.
- **Typed config + fail-fast validation (1.2 + 1.4).** New `src/config.py` with a frozen
  `Config` and `require_fabric()` / `require_anthropic()` that raise one clear message
  listing exactly what's missing. Detects the unfilled `.env.example` placeholders and
  treats them as "not set." Both `wanda.py` and the MCP server now validate credentials
  at startup instead of failing mid-investigation.
- **Logging instead of print() (1.4).** New `src/log_setup.py`; `WANDA_LOG_LEVEL` controls
  verbosity. Logs go to **stderr** (the MCP server's stdout is the JSON-RPC channel — must
  stay clean). `wanda.py` diagnostics now log; the report still prints to stdout.
- **REST hardening in the MCP server (1.1).**
  - Token caching with transparent refresh; a 401 forces a refresh and retries.
  - New `fabric_request()` wraps every Fabric call: honors `Retry-After`, then exponential
    backoff (cap 60s) on 429 / 5xx.
  - `_http_error()` maps 401/403/404/429 to plain-English messages (e.g. 403 → "Service
    Principal lacks the required role" instead of a crash).
- **None-safety / empty-response audit across all 6 tools (1.1).** Clear messages for: 0 runs,
  0-activity (empty/draft) pipelines, un-provisioned SQL endpoints, and notebooks with no
  extractable Python (Spark-SQL / binary / never-run), plus a source-truncation marker.
- **Entry point guarded.** `wanda.py` now runs under `if __name__ == "__main__"`, making it
  importable (needed for tests and the eventual Phase 2 `Wanda` class).
- **Type hints** added across `wanda.py` and the server's helpers.

### Why
- These are the failures a real user's own workspace will trigger that our controlled demo
  never did (rate limits, token expiry, missing permissions, empty/odd pipelines). Per the
  roadmap, Phase 1 must hold before beta. Several items (prompts→files, Config, importable
  entry point) also de-risk the Phase 2 notebook port.

### Verification
- `py_compile` + import of all five modules — green.
- `Config`: placeholder/blank detection, missing-creds messages, happy-path chaining.
- Retry/auth logic with fully mocked HTTP (no network, no real sleeps): `Retry-After`
  honored, exponential fallback, token cached (single fetch), 429→200 retry, 401→forced
  refresh→200. All pass.
- Could **not** run end-to-end: needs a live Fabric workspace + Copilot SDK login.

### Open / follow-ups
- **Model id decision (1.4):** did *not* hard-change `MODEL = "claude-opus-4-1"`; made it
  overridable via `WANDA_MODEL` (default unchanged) because the accepted model-id strings
  for the Copilot SDK + Anthropic provider can't be verified offline. Needs a live run to
  pick + confirm a current id.
- **Not committed yet** — on `main`; branch first before committing.
- **Doc drift:** `docs/README.md` and `AGENTS.md` still say "4 tools" (there are 6);
  `AGENTS.md` has escaped `\#`/`\-` markdown. Cleanup pass needed.
- **Next session candidate — Phase 1.3 testing:** the mocked retry/auth checks are the seed
  of a pytest suite (pytest + respx, 6 tools × happy/error, `render_report` snapshot, GitHub
  Actions CI).
