"""
llm_provider.py — swappable LLM backend layer for Wanda.

The agent loop (agent.py) speaks one neutral dialect; each provider translates
it to its wire format. That makes "which model" a config switch instead of a
rewrite:

  - AnthropicProvider    Claude via the Anthropic Messages API. Used for the
                         direct API today, and reusable for Claude-on-Azure
                         (AI Foundry) later by pointing base_url/auth at the
                         Azure endpoint — same Messages wire format.
  - AzureOpenAIProvider  GPT models on Azure OpenAI (credit-funded), via the
                         v1 chat-completions endpoint.

Neutral message format used by agent.py:
  {"role": "user", "content": str}
  {"role": "assistant", "content": str|None,
   "tool_calls": [{"id": str, "name": str, "arguments": dict}],
   "raw_content": <opaque provider-native blocks, replayed verbatim>}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str}

"raw_content" exists because the Messages API requires assistant turns to be
replayed exactly as received — including thinking blocks on thinking-enabled
models (claude-fable-5 etc.); reconstructing from text+tool_calls alone would
400 on the next request. Providers that returned the turn replay it verbatim;
other providers ignore it.

Implemented over `requests` (already a dependency) rather than vendor SDKs so
the package stays dependency-light and fully testable offline. The Anthropic
path sets two prompt-cache breakpoints: the system prefix (tools + system
prompt) and the tail of the growing conversation, so later turns of a run
re-read earlier turns from cache. Note Anthropic enforces a minimum cacheable
prefix (~2048 tokens on Sonnet) — very short first turns may not cache yet.
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import requests

from .config import Config, ConfigError
from .log_setup import get_logger

logger = get_logger("llm")

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_VERSION = "2023-06-01"
MAX_OUTPUT_TOKENS = 4096
LLM_MAX_RETRIES = 5
REQUEST_TIMEOUT = 300  # seconds — investigation prompts can get large


@dataclass(frozen=True)
class ToolSpec:
    """Provider-neutral tool definition (JSON Schema parameters)."""
    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class TurnResult:
    """One model turn: assistant text and/or tool calls, plus usage.
    raw_content carries the provider-native assistant blocks for verbatim
    replay (preserves thinking blocks on thinking-enabled Claude models)."""
    text: str | None
    tool_calls: list[ToolCall]
    stop_reason: str
    usage: dict[str, int] = field(default_factory=dict)
    raw_content: list | None = None


def _retry_after_seconds(resp: requests.Response, attempt: int) -> float:
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), 60.0)
        except ValueError:
            pass
    return min(2.0 ** attempt, 60.0)


def _post_with_retries(url: str, headers: dict, body: dict, label: str) -> requests.Response:
    """POST with exponential backoff on 429/5xx (honoring Retry-After) and on
    transport-level failures (connection resets, read timeouts)."""
    resp = None
    for attempt in range(LLM_MAX_RETRIES):
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            if attempt < LLM_MAX_RETRIES - 1:
                wait = min(2.0 ** attempt, 60.0)
                logger.warning(
                    "%s request failed (%s) — backing off %.1fs (attempt %d/%d)",
                    label, e.__class__.__name__, wait, attempt + 1, LLM_MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"{label} request failed after {LLM_MAX_RETRIES} attempts: {e}"
            ) from e
        if (resp.status_code == 429 or resp.status_code >= 500) and attempt < LLM_MAX_RETRIES - 1:
            wait = _retry_after_seconds(resp, attempt)
            logger.warning(
                "%s returned %s — backing off %.1fs (attempt %d/%d)",
                label, resp.status_code, wait, attempt + 1, LLM_MAX_RETRIES,
            )
            time.sleep(wait)
            continue
        return resp
    return resp


def _parse_json(resp: requests.Response, label: str) -> dict:
    try:
        return resp.json()
    except ValueError as e:
        raise RuntimeError(
            f"{label} returned a non-JSON response (status {resp.status_code}): {resp.text[:200]}"
        ) from e


class LLMProvider(ABC):
    """One model turn in, one TurnResult out. Stateless between calls."""

    label: str  # human-readable model identifier for logs and reports

    @abstractmethod
    def complete(self, system: str, messages: list[dict], tools: list[ToolSpec]) -> TurnResult:
        ...


# -----------------------------------------------------------------------------
# Anthropic Messages API (direct, and Azure-hosted Claude later)
# -----------------------------------------------------------------------------
class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        base_url: str = "https://api.anthropic.com",
        auth_header: str = "x-api-key",
        max_tokens: int = MAX_OUTPUT_TOKENS,
        error_hint: str | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.auth_header = auth_header
        self.max_tokens = max_tokens
        self.label = model
        # Auth-failure guidance differs between Anthropic-direct and Azure-hosted.
        self.error_hint = error_hint or "Check ANTHROPIC_API_KEY (console.anthropic.com → API Keys)."

    @staticmethod
    def _convert_messages(messages: list[dict]) -> list[dict]:
        """Neutral → Anthropic. Consecutive tool results merge into a single
        user message so user/assistant roles keep alternating. Assistant turns
        that carry raw_content are replayed verbatim — required so thinking
        blocks survive the round-trip on thinking-enabled models."""
        out: list[dict] = []
        pending_results: list[dict] = []

        def flush_results():
            nonlocal pending_results
            if pending_results:
                out.append({"role": "user", "content": pending_results})
                pending_results = []

        for m in messages:
            role = m["role"]
            if role == "tool":
                pending_results.append({
                    "type": "tool_result",
                    "tool_use_id": m["tool_call_id"],
                    "content": m["content"],
                })
                continue
            flush_results()
            if role == "user":
                out.append({"role": "user", "content": [{"type": "text", "text": m["content"]}]})
            elif role == "assistant":
                raw = m.get("raw_content")
                if raw:
                    out.append({"role": "assistant", "content": raw})
                    continue
                blocks: list[dict] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    })
                out.append({"role": "assistant", "content": blocks})
        flush_results()
        return out

    def complete(self, system: str, messages: list[dict], tools: list[ToolSpec]) -> TurnResult:
        converted = self._convert_messages(messages)
        # Incremental conversation caching: a second breakpoint on the tail of
        # the latest message lets each turn re-read the previous turns from
        # cache instead of re-billing the growing history at full price. The
        # last message is always user/tool_result (we never call mid-assistant),
        # so this never touches replayed raw assistant blocks. Copy, don't
        # mutate — the neutral history is reused across turns.
        if converted:
            tail_blocks = converted[-1].get("content")
            if isinstance(tail_blocks, list) and tail_blocks and \
                    tail_blocks[-1].get("type") in ("text", "tool_result"):
                tail_blocks[-1] = {**tail_blocks[-1], "cache_control": {"type": "ephemeral"}}

        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            # cache_control on the system block caches the static prefix
            # (tools + system prompt) across turns and runs.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": converted,
        }
        if tools:
            body["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]

        headers = {
            self.auth_header: self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        resp = _post_with_retries(f"{self.base_url}/v1/messages", headers, body, "Anthropic")
        if resp.status_code in (401, 403):
            raise RuntimeError(
                f"Anthropic authentication failed ({resp.status_code}). {self.error_hint}"
            )
        if not resp.ok:
            raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text[:300]}")

        data = _parse_json(resp, "Anthropic")
        content = data.get("content") or []
        text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
        tool_calls = [
            ToolCall(id=b["id"], name=b["name"], arguments=b.get("input") or {})
            for b in content
            if b.get("type") == "tool_use"
        ]
        raw_usage = data.get("usage") or {}
        usage = {k: int(v) for k, v in raw_usage.items() if isinstance(v, (int, float))}
        text = "\n".join(p for p in text_parts if p).strip() or None
        return TurnResult(text=text, tool_calls=tool_calls,
                          stop_reason=data.get("stop_reason") or "", usage=usage,
                          raw_content=content or None)


# -----------------------------------------------------------------------------
# Azure OpenAI chat completions (v1 endpoint)
# -----------------------------------------------------------------------------
# gpt-5-family reasoning models spend max_completion_tokens on BOTH invisible
# reasoning and visible output; 4096 can be eaten by reasoning alone, returning
# an empty turn. Budget generously — tokens are only billed if used.
AZURE_MAX_COMPLETION_TOKENS = 16384

# Azure/OpenAI finish_reason → the neutral stop_reason dialect agent.py checks.
_FINISH_REASON_MAP = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
}


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, endpoint: str, api_key: str, deployment: str,
                 max_tokens: int = AZURE_MAX_COMPLETION_TOKENS):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.deployment = deployment
        self.max_tokens = max_tokens
        self.label = f"{deployment} (azure-openai)"

    @staticmethod
    def _convert_messages(system: str, messages: list[dict]) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            role = m["role"]
            if role == "user":
                out.append({"role": "user", "content": m["content"]})
            elif role == "assistant":
                entry: dict = {"role": "assistant", "content": m.get("content")}
                if m.get("tool_calls"):
                    entry["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]),
                            },
                        }
                        for tc in m["tool_calls"]
                    ]
                out.append(entry)
            elif role == "tool":
                out.append({
                    "role": "tool",
                    "tool_call_id": m["tool_call_id"],
                    "content": m["content"],
                })
        return out

    def complete(self, system: str, messages: list[dict], tools: list[ToolSpec]) -> TurnResult:
        body: dict = {
            "model": self.deployment,
            "messages": self._convert_messages(system, messages),
            # Newer Azure OpenAI models (gpt-5 family) reject max_tokens.
            "max_completion_tokens": self.max_tokens,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]

        headers = {"api-key": self.api_key, "content-type": "application/json"}
        url = f"{self.endpoint}/openai/v1/chat/completions"
        resp = _post_with_retries(url, headers, body, "Azure OpenAI")
        if resp.status_code in (401, 403):
            raise RuntimeError(
                f"Azure OpenAI authentication failed ({resp.status_code}). "
                "Check AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT."
            )
        if not resp.ok:
            raise RuntimeError(f"Azure OpenAI API error {resp.status_code}: {resp.text[:300]}")

        data = _parse_json(resp, "Azure OpenAI")
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=arguments))
        raw_usage = data.get("usage") or {}
        usage = {}
        if "prompt_tokens" in raw_usage:
            usage["input_tokens"] = int(raw_usage["prompt_tokens"])
        if "completion_tokens" in raw_usage:
            usage["output_tokens"] = int(raw_usage["completion_tokens"])
        text = message.get("content") or None
        finish_reason = choice.get("finish_reason") or ""
        return TurnResult(text=text.strip() if isinstance(text, str) else text,
                          tool_calls=tool_calls,
                          stop_reason=_FINISH_REASON_MAP.get(finish_reason, finish_reason),
                          usage=usage)


# -----------------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------------
def build_provider(cfg: Config) -> LLMProvider:
    """Build the configured provider, validating only the settings it needs."""
    provider = (cfg.provider or "anthropic").lower()

    if provider == "anthropic":
        cfg.require_anthropic()
        return AnthropicProvider(
            api_key=cfg.anthropic_api_key,
            model=cfg.model or DEFAULT_ANTHROPIC_MODEL,
            base_url=cfg.anthropic_base_url,
        )

    if provider in ("azure-openai", "azure_openai", "azure"):
        cfg.require_azure_openai()
        return AzureOpenAIProvider(
            endpoint=cfg.azure_openai_endpoint,
            api_key=cfg.azure_openai_api_key,
            deployment=cfg.azure_openai_deployment,
        )

    if provider in ("azure-anthropic", "azure_anthropic"):
        # Claude on Azure AI Foundry exposes the Anthropic Messages wire format,
        # so we reuse AnthropicProvider with Azure's endpoint + api-key header.
        # Experimental until Azure quota lands and a live call verifies it.
        cfg.require_azure_anthropic()
        logger.warning("azure-anthropic provider is experimental — verify with a live call.")
        return AnthropicProvider(
            api_key=cfg.azure_anthropic_api_key,
            model=cfg.azure_anthropic_deployment,
            base_url=cfg.azure_anthropic_endpoint,
            auth_header="api-key",
            error_hint="Check AZURE_ANTHROPIC_API_KEY and AZURE_ANTHROPIC_ENDPOINT "
                       "(Azure AI Foundry project → endpoints and keys).",
        )

    raise ConfigError(
        f"Unknown WANDA_PROVIDER '{cfg.provider}'. "
        "Use 'anthropic', 'azure-openai', or 'azure-anthropic'."
    )
