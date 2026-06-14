# Wanda — Beta Architecture

How Wanda is built for beta, what's done, what's missing, and where the money is.
Companion docs: [WANDA_ROADMAP.md](../WANDA_ROADMAP.md) (the plan),
[WANDA_BUSINESS.md](WANDA_BUSINESS.md) (the business model),
[WANDA_WORKLOG.md](../WANDA_WORKLOG.md) (what actually happened).

**Last updated:** 2026-06-12

---

## 1. The big architectural shift (2026-06-12)

The GitHub Copilot SDK runtime is **gone**. It was the hackathon requirement, but it
forced a local-subprocess design (CLI → MCP subprocess over stdio) that could never run
inside a Fabric notebook, and it required testers to have a GitHub Copilot login.

Wanda now talks to its model provider **directly**, and the Fabric tools are **plain
Python functions called inline** — no subprocess. That single change is what unlocks
notebook distribution (Phase 2) and makes the model a config switch.

```
BEFORE (hackathon)                          AFTER (beta)
──────────────────                          ────────────
wanda.py ──Copilot SDK──► LLM               Wanda class / CLI (wanda.py)
   │                                           └── agent.py ── tool-use loop
   └─spawns──► fabric_mcp_server.py                ├── llm_provider.py ──► Claude (direct/Azure)
               (subprocess, stdio)                 │                       or GPT (Azure OpenAI)
               6 tools inside it                   └── fabric_tools.py ──► Fabric REST + SQL
                                                       (the 6 tools, inline)

                                            fabric_mcp_server.py still exists as a thin
                                            MCP wrapper over the SAME fabric_tools —
                                            for Claude Desktop / Cursor / VS Code users.
```

## 2. The layers

| Layer | File | Job |
|---|---|---|
| **Entry points** | `wanda/core.py` · `wanda/cli.py` | `Wanda` class (`.investigate()` / `.scan()` → `WandaReport`) + the `wanda` CLI. |
| **Agent loop** | `wanda/agent.py` | Drive any provider through turns: model asks for tools → execute inline → feed results back → final report. Bounded (12 turns, 8K chars/tool result). |
| **Provider abstraction** | `wanda/llm_provider.py` | One neutral dialect; each provider translates to its wire format. `WANDA_PROVIDER` = `anthropic` \| `azure-openai` \| `azure-anthropic`. Anthropic path has prompt caching (system prompt cached → ~90% cheaper on the static prefix every turn). |
| **Tools** | `wanda/fabric_tools.py` | The 6 Fabric tools as plain functions + registry. Hardened REST layer (token cache/refresh, 429/5xx backoff, friendly 401/403/404 errors). Lazy config: importable without credentials. |
| **MCP front door** | `wanda/mcp_server.py` | Thin FastMCP wrapper over the same 6 functions, for external MCP clients. |
| **Config** | `wanda/config.py` | Typed, frozen, fail-fast validation per provider. All env-driven. |
| **Prompts** | `wanda/prompts/*.md` | The investigate/scan system prompts, bundled as package data. |
| **Reports** | `wanda/render_report.py` | Text → self-contained HTML; `build_html()` for inline notebook display, `render_report()` for files. |
| **Tests** | `tests/` | 34 offline tests: provider wire formats (mocked HTTP), agent loop (fake provider), config validation. |

## 3. Why this shape (the three constraints it solves)

1. **Fabric notebooks can't spawn subprocesses** → tools must be importable functions.
   They are. The notebook story is now: `pip install` → `from wanda import Wanda` → go.
2. **The model must be swappable without rework** — Azure quota sagas, bake-offs,
   credit-funded vs BYOK… all of that is now `WANDA_PROVIDER=` one line:
   - `anthropic` — Claude via Anthropic API (works **today**, cash/BYOK)
   - `azure-openai` — GPT on Azure (credit-funded, once quota lands)
   - `azure-anthropic` — Claude on Azure Foundry (same Messages wire format; experimental until quota lands and a live call verifies it)
3. **Correctness is the product** → everything is bounded and observable: step limits,
   result truncation (context-overflow guard), per-run token usage accounting (the seed
   of Phase 3 telemetry), every tool call logged to stderr.

## 4. What a tester sees (beta UX target)

```
Cell 1:  !pip install wanda-fabric            ← not yet published
Cell 2:  from wanda import Wanda
         wanda = Wanda(anthropic_api_key="…") ← or CM Labs beta token via proxy
Cell 3:  report = wanda.investigate("MyPipeline")
         report.display()                     ← inline HTML, already works
```

## 5. Status: done / in progress / missing

### ✅ Done (verified offline)
- Phase 1 hardening: retries, token refresh, None-safety, logging, typed config, prompts-as-files
- **Provider abstraction + direct LLM runtime (Copilot SDK removed)**
- **Inline tools + `Wanda` class + notebook-ready `report.display()`**
- MCP server preserved as a wrapper (same tools, one source of truth)
- 34 offline tests; multi-agent adversarial review run over the refactor

### 🔶 In progress / blocked
- **One live end-to-end run** (needs `ANTHROPIC_API_KEY` + live Fabric) — nothing has
  hit a real workspace since the refactor. **This is the next action.**
- **Azure model deployment** — blocked on Free Tier quota; Tier 1 upgrade + quota
  request pending (~2026-06-15). Then: deploy Claude/GPT, run the **credit test** and
  the **quality bake-off**.
- GitHub Actions CI for the test suite.

### ❌ Missing for beta (the gap list)
- **pip package** (`wanda-fabric` on PyPI) + the **template .ipynb**
- **Fabric workspace-identity auth** (`mssparkutils.credentials`) so notebook testers
  need no Service Principal — the Week-2 spike, needs live Fabric
- **CM Labs beta proxy** (token-gated, capped, credit-funded LLM) + telemetry (Phase 3)
- Tester docs: quickstart, what-it-can't-do, troubleshooting, privacy statement
- Beta sign-off criteria (roadmap): 3 foreign workspaces, <15-min setup, feedback channel

## 6. The path to profitable (condensed from WANDA_BUSINESS.md)

1. **Beta (now):** free for testers (CM Labs token or BYOK). Goal = learn, not earn.
   Audience: Data Engineering Pilipinas. Cost ≈ $0 (credits + capped spend).
2. **Validate the one unknown — price.** Ask every tester: *"if this ran automatically
   and posted to Teams/Slack when a pipeline failed, would you pay $X/mo?"*
3. **Product:** open-core. Free notebook (BYOK) for adoption → **paid hosted tier**
   (auto-trigger on failure, Teams/Slack delivery, history, team features).
4. **Sell through Azure Marketplace** — customers spend committed Azure budget;
   Microsoft takes ~3%; procurement friction ≈ zero.
5. **Margin mechanics:** ~cents of LLM tokens per investigation vs ~$200/mo price
   point → ~80% gross margin; costs stay near-flat as customers stack.

**Biggest risk** stays the same: Microsoft building this into Fabric. Counter: move
fast, own the niche, be the thing they'd rather partner with/acquire than rebuild.
