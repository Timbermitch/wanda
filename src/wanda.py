"""
Wanda — agentic Microsoft Fabric pipeline investigator.

Two modes:
  - investigate (default): root-cause a failed pipeline run
  - scan (--scan): pre-run audit of a pipeline before execution

Architecture (beta):

    Wanda class / CLI (this file)
        └── agent.py          provider-agnostic tool-use loop
            ├── llm_provider.py   Claude (Anthropic direct or Azure) / Azure OpenAI
            └── fabric_tools.py   the 6 Fabric tools, called inline — no subprocess

    fabric_mcp_server.py exposes the same tools over MCP for external clients.

The GitHub Copilot SDK runtime is gone: Wanda talks to its model provider
directly, which is what lets it run inside a Fabric notebook (no subprocess)
and switch providers via WANDA_PROVIDER without code changes.

Library use (notebook or script):

    from wanda import Wanda
    wanda = Wanda(anthropic_api_key="sk-ant-...")   # or rely on .env
    report = wanda.investigate("LoadSalesPipeline")
    report.display()                                 # inline HTML in notebooks
"""
from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path

from agent import AgentStep, run_agent
from config import ConfigError, load_config
from fabric_tools import TOOL_SPECS, ensure_configured, execute_tool
from llm_provider import ToolSpec, build_provider
from log_setup import get_logger
from render_report import build_html, render_report

logger = get_logger("cli")

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

INVESTIGATE_REQUEST = (
    "The pipeline '{pipeline}' just failed. "
    "Investigate using the Fabric tools and give me a root-cause report."
)
SCAN_REQUEST = (
    "Pre-run scan: audit the pipeline '{pipeline}' before it runs. "
    "Use the Fabric tools to validate every activity against the workspace. "
    "Report what will pass, what will fail, and exactly what needs to be fixed first."
)


def load_prompt(name: str) -> str:
    """Load a system prompt from prompts/<name>.md so prompts are versionable
    and editable without touching code."""
    path = PROMPTS_DIR / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"System prompt '{name}' not found at {path}. "
            "Expected prompts/investigate.md and prompts/scan.md in the repo."
        ) from exc


class WandaReport:
    """The outcome of one investigation or scan."""

    def __init__(self, content: str, pipeline_name: str, mode: str, model: str,
                 duration_seconds: float, usage: dict[str, int], steps: list[AgentStep]):
        self.content = content
        self.pipeline_name = pipeline_name
        self.mode = mode
        self.model = model
        self.duration_seconds = duration_seconds
        self.usage = usage
        self.steps = steps

    @property
    def text(self) -> str:
        return self.content

    def to_html(self) -> str:
        """Self-contained HTML document for this report."""
        return build_html(self.content, self.pipeline_name, self.mode,
                          self.model, self.duration_seconds)

    def save(self) -> Path:
        """Write the HTML report to reports/ and return its path."""
        return render_report(content=self.content, pipeline_name=self.pipeline_name,
                             mode=self.mode, model=self.model,
                             duration_seconds=self.duration_seconds)

    def display(self) -> None:
        """Render inline in a notebook output cell; falls back to print()."""
        try:
            from IPython.display import HTML, display
            display(HTML(self.to_html()))
        except ImportError:
            print(self.content)

    def __repr__(self) -> str:
        return (f"<WandaReport {self.mode} '{self.pipeline_name}' "
                f"{len(self.content)} chars, {len(self.steps)} tool calls>")


class Wanda:
    """Importable entry point: construct once, then .investigate() / .scan()."""

    def __init__(self, anthropic_api_key: str | None = None,
                 provider: str | None = None, model: str | None = None):
        cfg = load_config()
        overrides = {}
        if anthropic_api_key:
            overrides["anthropic_api_key"] = anthropic_api_key
        if provider:
            overrides["provider"] = provider
        if model:
            overrides["model"] = model
        if overrides:
            cfg = dataclasses.replace(cfg, **overrides)
        self.config = cfg
        self.provider = build_provider(cfg)  # validates LLM settings fail-fast
        self._tool_specs = [ToolSpec(**spec) for spec in TOOL_SPECS]

    def investigate(self, pipeline_name: str) -> WandaReport:
        return self._run(pipeline_name, scan=False)

    def scan(self, pipeline_name: str) -> WandaReport:
        return self._run(pipeline_name, scan=True)

    def _run(self, pipeline_name: str, scan: bool) -> WandaReport:
        ensure_configured()  # fail fast on missing Fabric credentials
        mode_label = "PRE-RUN SCAN" if scan else "INVESTIGATION"
        system_prompt = load_prompt("scan" if scan else "investigate")
        request = (SCAN_REQUEST if scan else INVESTIGATE_REQUEST).format(pipeline=pipeline_name)

        logger.info("Wanda — %s — pipeline: %s — model: %s",
                    mode_label, pipeline_name, self.provider.label)
        start = time.time()
        result = run_agent(
            provider=self.provider,
            system_prompt=system_prompt,
            user_request=request,
            tool_specs=self._tool_specs,
            execute_tool=execute_tool,
        )
        duration = time.time() - start
        logger.info("Done in %.1fs — %d tool calls over %d turns — tokens: %s",
                    duration, len(result.steps), result.turns, result.usage or "n/a")

        return WandaReport(content=result.report, pipeline_name=pipeline_name,
                           mode=mode_label, model=self.provider.label,
                           duration_seconds=duration, usage=result.usage,
                           steps=result.steps)


def main() -> None:
    # Windows consoles default to cp1252, which can't encode emoji a model may
    # put in a report. Force UTF-8 so printing never crashes the run.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    # Parse args: support --scan flag
    args = sys.argv[1:]
    scan_mode = "--scan" in args
    args = [a for a in args if a != "--scan"]
    pipeline_name = args[0] if args else "LoadSalesPipeline"

    try:
        wanda = Wanda()
        report = wanda.scan(pipeline_name) if scan_mode else wanda.investigate(pipeline_name)
    except ConfigError as e:
        logger.error("%s", e)
        sys.exit(2)

    # Save the HTML artifact first — a console hiccup must never lose the report.
    report_path = report.save()

    print("\n========== WANDA REPORT ==========")
    print(report.content)
    print("===================================\n")

    logger.info("Report saved: %s", report_path)
    logger.info("Open in browser: %s", report_path.resolve().as_uri())


if __name__ == "__main__":
    main()
