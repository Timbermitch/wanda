"""Agent-loop tests using a scripted fake provider — no network, no real model."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent import MAX_TOOL_RESULT_CHARS, run_agent
from llm_provider import ToolCall, ToolSpec, TurnResult

TOOLS = [ToolSpec(name="get_pipeline_run", description="d",
                  input_schema={"type": "object", "properties": {}})]


class FakeProvider:
    """Returns scripted TurnResults and records every messages list it saw."""
    label = "fake-model"

    def __init__(self, turns):
        self.turns = list(turns)
        self.seen_messages = []

    def complete(self, system, messages, tools):
        self.seen_messages.append([dict(m) for m in messages])
        return self.turns.pop(0)


def tool_turn(*calls):
    return TurnResult(text=None, tool_calls=list(calls), stop_reason="tool_use",
                      usage={"input_tokens": 10, "output_tokens": 5})


def final_turn(text, stop_reason="end_turn"):
    return TurnResult(text=text, tool_calls=[], stop_reason=stop_reason,
                      usage={"input_tokens": 20, "output_tokens": 15})


class TestRunAgent(unittest.TestCase):
    def test_tool_round_trip_then_final_report(self):
        provider = FakeProvider([
            tool_turn(ToolCall("t1", "get_pipeline_run", {"pipeline_name": "X"})),
            final_turn("ROOT CAUSE: missing table"),
        ])
        executed = []

        def execute(name, args):
            executed.append((name, args))
            return "Pipeline failed: TABLE_OR_VIEW_NOT_FOUND"

        result = run_agent(provider, "sys", "investigate X", TOOLS, execute)

        self.assertEqual(result.report, "ROOT CAUSE: missing table")
        self.assertEqual(executed, [("get_pipeline_run", {"pipeline_name": "X"})])
        self.assertEqual(result.turns, 2)
        self.assertEqual(len(result.steps), 1)
        # Usage accumulated across both turns
        self.assertEqual(result.usage, {"input_tokens": 30, "output_tokens": 20})
        # Second model call saw assistant tool_calls + tool result appended
        second = provider.seen_messages[1]
        self.assertEqual([m["role"] for m in second], ["user", "assistant", "tool"])
        self.assertEqual(second[2]["content"], "Pipeline failed: TABLE_OR_VIEW_NOT_FOUND")

    def test_tool_exception_becomes_readable_result(self):
        provider = FakeProvider([
            tool_turn(ToolCall("t1", "get_pipeline_run", {})),
            final_turn("done"),
        ])

        def execute(name, args):
            raise RuntimeError("boom")

        result = run_agent(provider, "sys", "go", TOOLS, execute)
        self.assertIn("Tool error: boom", result.steps[0].result)
        self.assertEqual(result.report, "done")

    def test_huge_tool_result_is_truncated(self):
        provider = FakeProvider([
            tool_turn(ToolCall("t1", "get_pipeline_run", {})),
            final_turn("done"),
        ])
        result = run_agent(provider, "sys", "go", TOOLS,
                           lambda n, a: "x" * (MAX_TOOL_RESULT_CHARS + 5000))
        stored = result.steps[0].result
        self.assertLess(len(stored), MAX_TOOL_RESULT_CHARS + 100)
        self.assertIn("truncated", stored)

    def test_step_limit_guard(self):
        provider = FakeProvider([
            tool_turn(ToolCall(f"t{i}", "get_pipeline_run", {})) for i in range(3)
        ])
        result = run_agent(provider, "sys", "go", TOOLS, lambda n, a: "r", max_turns=3)
        self.assertIn("did not complete", result.report)
        self.assertEqual(result.turns, 3)
        self.assertEqual(len(result.steps), 3)

    def test_max_tokens_warning_appended(self):
        provider = FakeProvider([final_turn("partial report", stop_reason="max_tokens")])
        result = run_agent(provider, "sys", "go", TOOLS, lambda n, a: "r")
        self.assertIn("partial report", result.report)
        self.assertIn("output limit", result.report)

    def test_truncated_tool_call_is_not_executed(self):
        # A tool_use turn cut off by max_tokens may carry partial/empty args —
        # it must be retried, never executed.
        truncated = TurnResult(text="analysis…",
                               tool_calls=[ToolCall("t1", "get_pipeline_run", {})],
                               stop_reason="max_tokens", usage={})
        provider = FakeProvider([truncated, final_turn("done")])
        executed = []
        result = run_agent(provider, "sys", "go", TOOLS,
                           lambda n, a: executed.append(n) or "r")
        self.assertEqual(executed, [])          # nothing ran
        self.assertEqual(result.report, "done")
        # The retry nudge went back to the model as a user message
        second = provider.seen_messages[1]
        self.assertEqual(second[-1]["role"], "user")
        self.assertIn("cut off", second[-1]["content"])

    def test_empty_final_turn_yields_readable_report(self):
        provider = FakeProvider([TurnResult(text=None, tool_calls=[],
                                            stop_reason="refusal", usage={})])
        result = run_agent(provider, "sys", "go", TOOLS, lambda n, a: "r")
        self.assertIn("No report was produced", result.report)
        self.assertIn("refusal", result.report)

    def test_raw_content_passed_through_to_history(self):
        raw = [{"type": "thinking", "thinking": "", "signature": "s"},
               {"type": "tool_use", "id": "t1", "name": "get_pipeline_run", "input": {}}]
        first = TurnResult(text=None,
                           tool_calls=[ToolCall("t1", "get_pipeline_run", {})],
                           stop_reason="tool_use", usage={}, raw_content=raw)
        provider = FakeProvider([first, final_turn("done")])
        run_agent(provider, "sys", "go", TOOLS, lambda n, a: "r")
        assistant_msg = provider.seen_messages[1][1]
        self.assertEqual(assistant_msg["raw_content"], raw)


if __name__ == "__main__":
    unittest.main()
