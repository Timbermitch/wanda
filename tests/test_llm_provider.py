"""Wire-format tests for the provider layer — fully offline (requests mocked)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import llm_provider as lp
from config import Config, ConfigError


def fake_response(status=200, json_data=None, headers=None, text=""):
    resp = mock.Mock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.headers = headers or {}
    resp.text = text
    resp.json = mock.Mock(return_value=json_data or {})
    return resp


def anthropic_tool_use_response():
    return {
        "content": [
            {"type": "text", "text": "Checking the pipeline run."},
            {"type": "tool_use", "id": "toolu_1", "name": "get_pipeline_run",
             "input": {"pipeline_name": "LoadSalesPipeline"}},
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 1200, "output_tokens": 80,
                  "cache_read_input_tokens": 1000},
    }


TOOLS = [lp.ToolSpec(name="get_pipeline_run", description="Get latest run",
                     input_schema={"type": "object", "properties": {}})]


class TestAnthropicProvider(unittest.TestCase):
    def setUp(self):
        self.provider = lp.AnthropicProvider(api_key="sk-test", model="claude-sonnet-4-6")

    def test_request_shape_and_tool_use_parse(self):
        with mock.patch.object(lp.requests, "post",
                               return_value=fake_response(200, anthropic_tool_use_response())) as post:
            result = self.provider.complete(
                system="You are Wanda.",
                messages=[{"role": "user", "content": "Investigate X"}],
                tools=TOOLS,
            )
        body = post.call_args.kwargs["json"]
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(post.call_args.args[0], "https://api.anthropic.com/v1/messages")
        self.assertEqual(headers["x-api-key"], "sk-test")
        self.assertEqual(body["model"], "claude-sonnet-4-6")
        self.assertIn("max_tokens", body)
        # System prompt is a cached block (prompt caching).
        self.assertEqual(body["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(body["tools"][0]["name"], "get_pipeline_run")
        self.assertEqual(body["messages"][0]["role"], "user")
        # Response parsing
        self.assertEqual(result.text, "Checking the pipeline run.")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].name, "get_pipeline_run")
        self.assertEqual(result.tool_calls[0].arguments, {"pipeline_name": "LoadSalesPipeline"})
        self.assertEqual(result.stop_reason, "tool_use")
        self.assertEqual(result.usage["cache_read_input_tokens"], 1000)

    def test_tool_results_merge_into_single_user_message(self):
        messages = [
            {"role": "user", "content": "Investigate X"},
            {"role": "assistant", "content": "Calling tools", "tool_calls": [
                {"id": "t1", "name": "a", "arguments": {"x": 1}},
                {"id": "t2", "name": "b", "arguments": {}},
            ]},
            {"role": "tool", "tool_call_id": "t1", "name": "a", "content": "result-1"},
            {"role": "tool", "tool_call_id": "t2", "name": "b", "content": "result-2"},
        ]
        converted = lp.AnthropicProvider._convert_messages(messages)
        roles = [m["role"] for m in converted]
        # user / assistant / user — alternation preserved, both results merged.
        self.assertEqual(roles, ["user", "assistant", "user"])
        results = converted[2]["content"]
        self.assertEqual([b["type"] for b in results], ["tool_result", "tool_result"])
        self.assertEqual(results[0]["tool_use_id"], "t1")
        # Assistant tool_use blocks present
        kinds = [b["type"] for b in converted[1]["content"]]
        self.assertEqual(kinds, ["text", "tool_use", "tool_use"])

    def test_retry_on_429_then_success(self):
        responses = [
            fake_response(429, headers={"Retry-After": "1"}),
            fake_response(200, {"content": [{"type": "text", "text": "ok"}],
                                "stop_reason": "end_turn", "usage": {}}),
        ]
        with mock.patch.object(lp.requests, "post", side_effect=responses) as post, \
             mock.patch.object(lp.time, "sleep") as slept:
            result = self.provider.complete("sys", [{"role": "user", "content": "hi"}], [])
        self.assertEqual(post.call_count, 2)
        self.assertTrue(slept.called)
        self.assertEqual(result.text, "ok")

    def test_transport_error_retried_then_success(self):
        import requests as real_requests
        responses = [
            real_requests.exceptions.ConnectionError("reset"),
            fake_response(200, {"content": [{"type": "text", "text": "ok"}],
                                "stop_reason": "end_turn", "usage": {}}),
        ]
        with mock.patch.object(lp.requests, "post", side_effect=responses) as post, \
             mock.patch.object(lp.time, "sleep"):
            result = self.provider.complete("sys", [{"role": "user", "content": "hi"}], [])
        self.assertEqual(post.call_count, 2)
        self.assertEqual(result.text, "ok")

    def test_raw_content_replayed_verbatim_preserves_thinking_blocks(self):
        # Thinking-enabled models (claude-fable-5) require the assistant turn —
        # including its thinking block — to be replayed exactly as received.
        raw = [
            {"type": "thinking", "thinking": "", "signature": "sig123"},
            {"type": "text", "text": "Calling tool"},
            {"type": "tool_use", "id": "t1", "name": "a", "input": {"x": 1}},
        ]
        messages = [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": "Calling tool",
             "tool_calls": [{"id": "t1", "name": "a", "arguments": {"x": 1}}],
             "raw_content": raw},
            {"role": "tool", "tool_call_id": "t1", "name": "a", "content": "out"},
        ]
        converted = lp.AnthropicProvider._convert_messages(messages)
        self.assertEqual(converted[1]["content"], raw)  # verbatim, thinking intact

    def test_complete_returns_raw_content(self):
        with mock.patch.object(lp.requests, "post",
                               return_value=fake_response(200, anthropic_tool_use_response())):
            result = self.provider.complete("sys", [{"role": "user", "content": "hi"}], TOOLS)
        self.assertEqual(result.raw_content[1]["type"], "tool_use")

    def test_incremental_cache_breakpoint_on_conversation_tail(self):
        with mock.patch.object(lp.requests, "post",
                               return_value=fake_response(200, anthropic_tool_use_response())) as post:
            self.provider.complete(
                "sys",
                [
                    {"role": "user", "content": "go"},
                    {"role": "assistant", "content": None,
                     "tool_calls": [{"id": "t1", "name": "a", "arguments": {}}]},
                    {"role": "tool", "tool_call_id": "t1", "name": "a", "content": "out"},
                ],
                TOOLS,
            )
        body = post.call_args.kwargs["json"]
        tail_block = body["messages"][-1]["content"][-1]
        self.assertEqual(tail_block["type"], "tool_result")
        self.assertEqual(tail_block["cache_control"], {"type": "ephemeral"})
        # Assistant tool_use blocks must NOT get cache_control bolted on
        for block in body["messages"][1]["content"]:
            self.assertNotIn("cache_control", block)

    def test_auth_failure_is_actionable(self):
        with mock.patch.object(lp.requests, "post", return_value=fake_response(401)):
            with self.assertRaises(RuntimeError) as ctx:
                self.provider.complete("sys", [{"role": "user", "content": "hi"}], [])
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))


class TestAzureOpenAIProvider(unittest.TestCase):
    def setUp(self):
        self.provider = lp.AzureOpenAIProvider(
            endpoint="https://cmlabs.openai.azure.com/", api_key="azkey", deployment="gpt-5")

    def test_request_shape_and_tool_call_parse(self):
        azure_response = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1", "type": "function",
                        "function": {"name": "get_pipeline_run",
                                     "arguments": "{\"pipeline_name\": \"X\"}"},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 900, "completion_tokens": 50},
        }
        with mock.patch.object(lp.requests, "post",
                               return_value=fake_response(200, azure_response)) as post:
            result = self.provider.complete(
                system="You are Wanda.",
                messages=[{"role": "user", "content": "Investigate X"}],
                tools=TOOLS,
            )
        url = post.call_args.args[0]
        body = post.call_args.kwargs["json"]
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(url, "https://cmlabs.openai.azure.com/openai/v1/chat/completions")
        self.assertEqual(headers["api-key"], "azkey")
        self.assertEqual(body["model"], "gpt-5")
        self.assertIn("max_completion_tokens", body)
        self.assertNotIn("max_tokens", body)  # gpt-5 family rejects max_tokens
        self.assertEqual(body["messages"][0], {"role": "system", "content": "You are Wanda."})
        self.assertEqual(body["tools"][0]["type"], "function")
        # Parse
        self.assertIsNone(result.text)
        self.assertEqual(result.tool_calls[0].arguments, {"pipeline_name": "X"})
        self.assertEqual(result.usage, {"input_tokens": 900, "output_tokens": 50})

    def test_assistant_and_tool_message_conversion(self):
        messages = [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "name": "f", "arguments": {"a": 1}}]},
            {"role": "tool", "tool_call_id": "c1", "name": "f", "content": "out"},
        ]
        converted = lp.AzureOpenAIProvider._convert_messages("sys", messages)
        self.assertEqual(converted[2]["tool_calls"][0]["function"]["arguments"], "{\"a\": 1}")
        self.assertEqual(converted[3], {"role": "tool", "tool_call_id": "c1", "content": "out"})

    def test_malformed_tool_arguments_fall_back_to_empty(self):
        azure_response = {
            "choices": [{"message": {"content": None, "tool_calls": [{
                "id": "c", "type": "function",
                "function": {"name": "f", "arguments": "{not json"}}]},
                "finish_reason": "tool_calls"}],
            "usage": {},
        }
        with mock.patch.object(lp.requests, "post",
                               return_value=fake_response(200, azure_response)):
            result = self.provider.complete("s", [{"role": "user", "content": "x"}], [])
        self.assertEqual(result.tool_calls[0].arguments, {})

    def test_finish_reason_normalized_to_neutral_dialect(self):
        # 'length' must surface as 'max_tokens' so agent.py's truncation
        # warning fires on the Azure path too.
        for wire, neutral in (("length", "max_tokens"), ("stop", "end_turn"),
                              ("tool_calls", "tool_use"), ("content_filter", "content_filter")):
            azure_response = {
                "choices": [{"message": {"content": "hi"}, "finish_reason": wire}],
                "usage": {},
            }
            with mock.patch.object(lp.requests, "post",
                                   return_value=fake_response(200, azure_response)):
                result = self.provider.complete("s", [{"role": "user", "content": "x"}], [])
            self.assertEqual(result.stop_reason, neutral, wire)

    def test_reasoning_friendly_output_budget(self):
        # gpt-5 family spends max_completion_tokens on reasoning + output;
        # 4096 starves it. The Azure default must be substantially higher.
        azure_response = {"choices": [{"message": {"content": "ok"},
                                       "finish_reason": "stop"}], "usage": {}}
        with mock.patch.object(lp.requests, "post",
                               return_value=fake_response(200, azure_response)) as post:
            self.provider.complete("s", [{"role": "user", "content": "x"}], [])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["max_completion_tokens"], lp.AZURE_MAX_COMPLETION_TOKENS)
        self.assertGreaterEqual(body["max_completion_tokens"], 16384)


class TestBuildProvider(unittest.TestCase):
    @staticmethod
    def _cfg(**kw):
        base = dict(tenant_id="t", client_id="c", client_secret="s", workspace_id="w",
                    anthropic_api_key=None)
        base.update(kw)
        return Config(**base)

    def test_default_anthropic(self):
        provider = lp.build_provider(self._cfg(anthropic_api_key="sk"))
        self.assertIsInstance(provider, lp.AnthropicProvider)
        self.assertEqual(provider.model, lp.DEFAULT_ANTHROPIC_MODEL)

    def test_model_override(self):
        provider = lp.build_provider(self._cfg(anthropic_api_key="sk", model="claude-opus-4-8"))
        self.assertEqual(provider.model, "claude-opus-4-8")

    def test_azure_openai_requires_settings(self):
        with self.assertRaises(ConfigError):
            lp.build_provider(self._cfg(provider="azure-openai"))

    def test_azure_openai_built(self):
        provider = lp.build_provider(self._cfg(
            provider="azure-openai", azure_openai_endpoint="https://e.openai.azure.com",
            azure_openai_api_key="k", azure_openai_deployment="gpt-5"))
        self.assertIsInstance(provider, lp.AzureOpenAIProvider)

    def test_azure_anthropic_uses_api_key_header(self):
        provider = lp.build_provider(self._cfg(
            provider="azure-anthropic",
            azure_anthropic_endpoint="https://e.services.ai.azure.com",
            azure_anthropic_api_key="k", azure_anthropic_deployment="claude-sonnet-4-6"))
        self.assertIsInstance(provider, lp.AnthropicProvider)
        self.assertEqual(provider.auth_header, "api-key")

    def test_azure_anthropic_auth_error_names_the_right_env_vars(self):
        provider = lp.build_provider(self._cfg(
            provider="azure-anthropic",
            azure_anthropic_endpoint="https://e.services.ai.azure.com",
            azure_anthropic_api_key="bad", azure_anthropic_deployment="claude-sonnet-4-6"))
        with mock.patch.object(lp.requests, "post", return_value=fake_response(401)):
            with self.assertRaises(RuntimeError) as ctx:
                provider.complete("s", [{"role": "user", "content": "x"}], [])
        self.assertIn("AZURE_ANTHROPIC_API_KEY", str(ctx.exception))
        self.assertNotIn("console.anthropic.com", str(ctx.exception))

    def test_unknown_provider(self):
        with self.assertRaises(ConfigError):
            lp.build_provider(self._cfg(provider="gemini"))


if __name__ == "__main__":
    unittest.main()
