#!/usr/bin/env python
"""
bakeoff.py — Claude-vs-GPT bake-off harness for Wanda.

Runs the SAME Fabric investigation across three model configs and prints a
scorecard (tool calls, latency, tokens, estimated cost), and saves each
root-cause report so you can compare CORRECTNESS side by side.

    ./.venv/Scripts/python.exe bakeoff.py LoadSalesPipeline
    ./.venv/Scripts/python.exe bakeoff.py Pipeline_A Pipeline_B --mode scan
    ./.venv/Scripts/python.exe bakeoff.py LoadSalesPipeline --only gpt-5.4 --only opus-4-8

The three configs:
    sonnet-4-6   Claude Sonnet 4.6 (direct Anthropic) — current default, baseline
    opus-4-8     Claude Opus 4.8   (direct Anthropic) — flagship
    gpt-5.4      Azure OpenAI gpt-5.4 (credit-funded) — the contender

Credentials come from your environment / .env — NEVER from this file:
  - Claude runs need ANTHROPIC_API_KEY.
  - The GPT run needs AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and
    AZURE_OPENAI_DEPLOYMENT (your gpt-5.4 deployment name).
  - All runs need Fabric access (FABRIC_WORKSPACE_ID + a token or Service
    Principal) — the same env Wanda already uses.

A config whose credentials are missing is SKIPPED, not fatal, so you can run
whatever subset you currently have keys for (e.g. --only gpt-5.4).

Note: every line we print here is deliberately ASCII (`->`, `~$`, `[EMPTY]`),
so a cp1252 Windows console can't raise UnicodeEncodeError even if the utf-8
reconfigure below fails. Keep it that way — report unicode goes to files only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

# Best-effort: let the console print utf-8. Guarded because all our own prints
# are ASCII anyway (see module docstring), so a failure here is harmless.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from wanda import Wanda  # uses the installed wanda-fabric

# Per-1M-token USD list prices, for a rough cash-cost estimate only.
#  - Anthropic splits input into uncached / cache-write / cache-read; Wanda
#    records all four, so Claude costs include caching (the `cache_*` rates).
#  - gpt-5.4 numbers are APPROXIMATE list price (the Azure pricing page was
#    unverifiable at build time). Reasoning tokens are folded into output and
#    billed at the output rate; Wanda's azure-openai path records only
#    input/output tokens (no Azure prompt-cache discount is separated out), so
#    the GPT run carries no cache terms. On credit-funded Azure the real cash
#    cost is ~$0 regardless — treat `~cost$` for gpt-5.4 as "what it would cost
#    direct".
RATES = {
    "sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "opus-4-8":   {"input": 5.00, "output": 25.00, "cache_write": 6.25, "cache_read": 0.50},
    "gpt-5.4":    {"input": 2.50, "output": 15.00},  # no cache terms — Azure path doesn't emit them
}

CONFIGS = [
    {"key": "sonnet-4-6", "provider": "anthropic",   "model": "claude-sonnet-4-6"},
    {"key": "opus-4-8",   "provider": "anthropic",   "model": "claude-opus-4-8"},
    # gpt-5.4: deployment name comes from AZURE_OPENAI_DEPLOYMENT. We pass
    # model=None so Wanda.__init__ applies no model override; the azure-openai
    # provider ignores cfg.model entirely (it uses the deployment), so a stale
    # WANDA_MODEL in the env is inert for this config by design.
    {"key": "gpt-5.4",    "provider": "azure-openai", "model": None},
]

OUT_DIR = Path("reports") / "bakeoff"

# agent.py returns these exact prefixes when a run produced no real report
# (empty/refused final turn, or the 12-turn step limit was hit). Either means
# "no usable root cause" and must be flagged so it doesn't skew the comparison.
_FAILURE_PREFIXES = ("No report was produced", "Investigation did not complete")


def estimate_cost(key: str, usage: dict) -> float:
    """Rough USD cash cost from token usage. Missing usage/rate keys count as 0."""
    r = RATES.get(key)
    if not r:
        return 0.0
    return (
        usage.get("input_tokens", 0) * r.get("input", 0)
        + usage.get("output_tokens", 0) * r.get("output", 0)
        + usage.get("cache_creation_input_tokens", 0) * r.get("cache_write", 0)
        + usage.get("cache_read_input_tokens", 0) * r.get("cache_read", 0)
    ) / 1_000_000


def _safe_name(s: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in s) or "pipeline"
    # If sanitizing changed the name, append a short hash so two different
    # pipeline names can't sanitize to the same file and clobber each other.
    if safe != s:
        safe = f"{safe}_{hashlib.sha1(s.encode()).hexdigest()[:6]}"
    return safe


def run_one(cfg: dict, pipeline: str, scan: bool) -> dict:
    """Run one config on one pipeline. Returns a result record; never raises."""
    key = cfg["key"]
    print(f"  -> {key:<11} ", end="", flush=True)

    # Construction validates LLM creds fail-fast (build_provider -> require_*).
    try:
        wanda = Wanda(provider=cfg["provider"], model=cfg["model"])
    except Exception as e:
        print(f"SKIP (setup: {type(e).__name__})")
        return {"config": key, "status": "skipped",
                "reason": f"{type(e).__name__}: {e}"}

    start = time.time()
    try:
        report = (wanda.scan if scan else wanda.investigate)(pipeline)
    except Exception as e:
        dur = time.time() - start
        print(f"ERROR after {dur:5.1f}s ({type(e).__name__})")
        return {"config": key, "status": "error",
                "reason": f"{type(e).__name__}: {e}",
                "duration_seconds": round(dur, 1)}

    usage = report.usage or {}
    tools = [s.tool for s in report.steps]
    cost = estimate_cost(key, usage)
    text = (report.content or "").strip()
    empty = (not text) or text.startswith(_FAILURE_PREFIXES)

    print(f"{len(report.steps):>2} tools  {report.duration_seconds:5.1f}s  "
          f"~${cost:.5f}" + ("   [EMPTY / NO REPORT]" if empty else ""))

    # Save the actual report so correctness can be judged by eye. Isolated so a
    # save failure (path length, permissions, disk full) degrades to
    # report_file=None instead of aborting the whole bake-off.
    report_file = None
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{_safe_name(pipeline)}__{key}.md"
        path.write_text(
            f"# {report.mode} — {pipeline} — {report.model}\n\n"
            f"_{report.duration_seconds:.1f}s · {len(report.steps)} tool calls · "
            f"tools: {' -> '.join(tools) or 'none'}_\n\n"
            f"{report.content}\n",
            encoding="utf-8",
        )
        report_file = str(path)
    except Exception as e:
        print(f"     (note: could not save report for {key}: {type(e).__name__})")

    return {
        "config": key, "status": "ok", "model": report.model,
        "duration_seconds": round(report.duration_seconds, 1),
        "tool_calls": len(report.steps), "tools": tools,
        "usage": usage, "est_cost_usd": round(cost, 5),
        "empty_report": empty, "report_file": report_file,
    }


def print_scorecard(pipeline: str, mode: str, rows: list[dict]) -> None:
    print(f"\n  Scorecard — {mode} — {pipeline}")
    print(f"  {'config':<11} {'status':<8} {'tools':>5} {'secs':>6} "
          f"{'in':>8} {'out':>7} {'cache_wr':>9} {'cache_rd':>9} {'~cost$':>10}")
    for r in rows:
        if r["status"] != "ok":
            print(f"  {r['config']:<11} {r['status']:<8} "
                  f"({r.get('reason', '')[:48]})")
            continue
        u = r["usage"]
        flag = "  EMPTY" if r.get("empty_report") else ""
        print(f"  {r['config']:<11} {'ok':<8} {r['tool_calls']:>5} "
              f"{r['duration_seconds']:>6.1f} {u.get('input_tokens', 0):>8} "
              f"{u.get('output_tokens', 0):>7} "
              f"{u.get('cache_creation_input_tokens', 0):>9} "
              f"{u.get('cache_read_input_tokens', 0):>9} "
              f"{r['est_cost_usd']:>10.5f}{flag}")
    print("  (in = full-rate input tokens; for Claude that's the uncached "
          "remainder. ~cost$ = in+out+cache_wr+cache_rd at list price.)")


def main() -> int:
    # Guard: every config must have a rate entry, or its cost silently reads $0.
    missing = {c["key"] for c in CONFIGS} - set(RATES)
    assert not missing, f"CONFIG(s) without a RATES entry: {missing}"

    ap = argparse.ArgumentParser(
        description="Wanda Claude-vs-GPT bake-off (runs in YOUR env with YOUR creds).")
    ap.add_argument("pipelines", nargs="+",
                    help="Fabric pipeline name(s) to investigate")
    ap.add_argument("--mode", choices=["investigate", "scan"], default="investigate")
    ap.add_argument("--only", action="append", choices=[c["key"] for c in CONFIGS],
                    help="run only this config (repeatable); default runs all three")
    args = ap.parse_args()

    scan = args.mode == "scan"
    if args.only:
        # Preserve the order the user requested, deduped.
        by_key = {c["key"]: c for c in CONFIGS}
        configs = [by_key[k] for k in dict.fromkeys(args.only)]
    else:
        configs = CONFIGS
    all_results = []

    for pipeline in args.pipelines:
        print(f"\n=== {args.mode.upper()} '{pipeline}' "
              f"across {len(configs)} config(s) ===")
        rows = [run_one(c, pipeline, scan) for c in configs]
        print_scorecard(pipeline, args.mode, rows)
        all_results.append({"pipeline": pipeline, "mode": args.mode, "results": rows})

    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "summary.json").write_text(
            json.dumps(all_results, indent=2), encoding="utf-8")
        print(f"\nReports + summary written to {OUT_DIR}/ "
              f"(summary.json + one .md per run).")
    except Exception as e:
        print(f"\n(note: could not write summary.json: {type(e).__name__})")

    print("Correctness is the human-judged axis: open the .md files and compare "
          "the root causes side by side. The scorecard covers everything else "
          "(tool discipline, turns, tokens, latency, cost).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
