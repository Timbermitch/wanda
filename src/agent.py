"""
agent.py — Wanda's tool-use loop, the part the GitHub Copilot SDK used to do.

Provider-agnostic: drive any LLMProvider through repeated turns — the model
asks for tools, we execute them inline (fabric_tools), feed results back, and
stop when the model produces its final report. Bounded by a step limit and a
per-result size cap so a pathological run can neither loop forever nor blow
out the context window (roadmap 1.1: context-overflow strategy).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from llm_provider import LLMProvider, ToolSpec
from log_setup import get_logger

logger = get_logger("agent")

MAX_TURNS = 12               # model turns (each may contain several tool calls)
MAX_TOOL_RESULT_CHARS = 8000  # context-overflow guard per tool result


@dataclass
class AgentStep:
    """One executed tool call (for logs, telemetry, and debugging)."""
    tool: str
    arguments: dict
    result: str


@dataclass
class AgentResult:
    report: str
    steps: list[AgentStep] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    turns: int = 0


def _accumulate_usage(total: dict[str, int], turn_usage: dict[str, int]) -> None:
    for key, value in (turn_usage or {}).items():
        total[key] = total.get(key, 0) + int(value or 0)


def run_agent(
    provider: LLMProvider,
    system_prompt: str,
    user_request: str,
    tool_specs: list[ToolSpec],
    execute_tool: Callable[[str, dict], str],
    max_turns: int = MAX_TURNS,
) -> AgentResult:
    """Run one investigation/scan to completion and return the final report."""
    messages: list[dict] = [{"role": "user", "content": user_request}]
    steps: list[AgentStep] = []
    usage: dict[str, int] = {}

    for turn in range(1, max_turns + 1):
        result = provider.complete(system=system_prompt, messages=messages, tools=tool_specs)
        _accumulate_usage(usage, result.usage)

        if result.tool_calls:
            if result.stop_reason == "max_tokens":
                # The turn was cut off mid tool call — its arguments may be
                # partial/empty. Don't execute; drop the incomplete calls and
                # ask the model to re-issue them.
                logger.warning("Turn %d truncated by the output limit mid tool call — retrying", turn)
                messages.append({"role": "assistant",
                                 "content": result.text or "(response truncated)"})
                messages.append({"role": "user", "content": (
                    "Your previous reply was cut off by the output limit before the tool "
                    "call completed. Re-issue the tool call(s), keeping any commentary brief."
                )})
                continue

            messages.append({
                "role": "assistant",
                "content": result.text,
                "tool_calls": [
                    {"id": c.id, "name": c.name, "arguments": c.arguments}
                    for c in result.tool_calls
                ],
                "raw_content": result.raw_content,
            })
            for call in result.tool_calls:
                logger.info("TOOL %s(%s)", call.name, json.dumps(call.arguments)[:200])
                try:
                    output = str(execute_tool(call.name, call.arguments))
                except Exception as e:  # tool bugs become readable model input
                    output = f"Tool error: {e}"
                    logger.warning("Tool %s raised: %s", call.name, e)
                if len(output) > MAX_TOOL_RESULT_CHARS:
                    output = output[:MAX_TOOL_RESULT_CHARS] + "\n…(tool result truncated)…"
                steps.append(AgentStep(tool=call.name, arguments=call.arguments, result=output))
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": output,
                })
            continue

        # No tool calls — this is the final report.
        report = result.text or ""
        if result.stop_reason == "max_tokens":
            report += "\n\n[warning: the model hit its output limit; the report may be truncated]"
        if not report.strip():
            # Refusals / content filters / reasoning-budget exhaustion can end a
            # run with an empty turn. Surface that instead of a blank report.
            logger.warning("Model ended the run with an empty turn (stop_reason=%r)",
                           result.stop_reason)
            report = (
                "No report was produced: the model ended the run without any output "
                f"(stop_reason: {result.stop_reason or 'unknown'}). Re-run the "
                "investigation; if this persists, check the provider's output limits "
                "or content filters."
            )
        return AgentResult(report=report, steps=steps, usage=usage, turns=turn)

    logger.warning("Agent stopped after %d turns without a final report", max_turns)
    return AgentResult(
        report=(
            "Investigation did not complete: the step limit was reached before the model "
            "produced a final report. Partial evidence gathered is in the run log."
        ),
        steps=steps,
        usage=usage,
        turns=max_turns,
    )
