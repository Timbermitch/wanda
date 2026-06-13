"""
config.py — single typed source of truth for Wanda's configuration.

Replaces scattered ``os.getenv`` reads across ``wanda.py`` and
``fabric_mcp_server.py`` with one object that is validated up front. This lets
us fail fast with a clear, actionable message when ``.env`` is missing or still
contains the ``.env.example`` placeholders — instead of failing deep inside an
investigation with an opaque auth error.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Default lakehouse used by query_sql_endpoint when a caller does not name one.
DEFAULT_LAKEHOUSE = "SalesLakehouse"

FABRIC_BASE_URL = "https://api.fabric.microsoft.com/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"

# Values shipped in .env.example. If any of these survive into a real run, the
# user copied the template but never filled it in — treat as "not set".
_PLACEHOLDERS = {
    "your-tenant-guid-here",
    "your-service-principal-client-id-here",
    "your-service-principal-secret-here",
    "your-fabric-workspace-guid-here",
    "your-anthropic-api-key-here",
    "your-azure-openai-key-here",
    "your-azure-anthropic-key-here",
    "https://your-resource.openai.azure.com",
    "https://your-resource.services.ai.azure.com",
}


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


def _clean(value: str | None) -> str | None:
    """Normalize an env value: strip whitespace, treat empty/placeholder as unset."""
    if value is None:
        return None
    value = value.strip()
    if not value or value in _PLACEHOLDERS:
        return None
    return value


@dataclass(frozen=True)
class Config:
    """Typed view of Wanda's environment. Fields are ``None`` when unset so that
    ``require_*`` can produce one clear error listing everything that is missing.

    ``provider`` selects the LLM backend (see llm_provider.build_provider):
      - "anthropic"       Claude via the Anthropic API directly (default)
      - "azure-openai"    GPT models on Azure OpenAI (credit-funded)
      - "azure-anthropic" Claude hosted on Azure AI Foundry (experimental)
    """

    tenant_id: str | None
    client_id: str | None
    client_secret: str | None
    workspace_id: str | None
    anthropic_api_key: str | None
    model: str | None = None
    provider: str = "anthropic"
    anthropic_base_url: str = ANTHROPIC_BASE_URL
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_anthropic_endpoint: str | None = None
    azure_anthropic_api_key: str | None = None
    azure_anthropic_deployment: str | None = None
    base_url: str = FABRIC_BASE_URL
    default_lakehouse: str = DEFAULT_LAKEHOUSE

    # -- validation -----------------------------------------------------------
    def require_fabric(self) -> "Config":
        """Ensure the four Fabric Service Principal values are present.

        Returns ``self`` so it chains: ``config = load_config().require_fabric()``.
        """
        missing = [
            name
            for name, value in (
                ("FABRIC_TENANT_ID", self.tenant_id),
                ("FABRIC_CLIENT_ID", self.client_id),
                ("FABRIC_CLIENT_SECRET", self.client_secret),
                ("FABRIC_WORKSPACE_ID", self.workspace_id),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing or unfilled Fabric credentials: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill in your Service Principal "
                "values (tenant, client id, client secret, workspace id)."
            )
        return self

    def require_anthropic(self) -> "Config":
        """Ensure an Anthropic API key is available."""
        if not self.anthropic_api_key:
            raise ConfigError(
                "Missing ANTHROPIC_API_KEY. Set it in your .env or environment "
                "before running Wanda."
            )
        return self

    def require_azure_openai(self) -> "Config":
        """Ensure the Azure OpenAI connection values are present."""
        missing = [
            name
            for name, value in (
                ("AZURE_OPENAI_ENDPOINT", self.azure_openai_endpoint),
                ("AZURE_OPENAI_API_KEY", self.azure_openai_api_key),
                ("AZURE_OPENAI_DEPLOYMENT", self.azure_openai_deployment),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing Azure OpenAI settings: " + ", ".join(missing) + ". "
                "Find the endpoint and key on your Azure AI Foundry project, and set "
                "AZURE_OPENAI_DEPLOYMENT to your model deployment name (e.g. gpt-5)."
            )
        return self

    def require_azure_anthropic(self) -> "Config":
        """Ensure the Azure-hosted Claude connection values are present."""
        missing = [
            name
            for name, value in (
                ("AZURE_ANTHROPIC_ENDPOINT", self.azure_anthropic_endpoint),
                ("AZURE_ANTHROPIC_API_KEY", self.azure_anthropic_api_key),
                ("AZURE_ANTHROPIC_DEPLOYMENT", self.azure_anthropic_deployment),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing Azure-hosted Claude settings: " + ", ".join(missing) + "."
            )
        return self


def load_config() -> Config:
    """Read configuration from the environment (loading ``.env`` if present).

    Does not validate — call ``.require_fabric()`` / ``.require_anthropic()`` on
    the result to enforce what a given entry point actually needs.
    """
    load_dotenv()
    return Config(
        tenant_id=_clean(os.getenv("FABRIC_TENANT_ID")),
        client_id=_clean(os.getenv("FABRIC_CLIENT_ID")),
        client_secret=_clean(os.getenv("FABRIC_CLIENT_SECRET")),
        workspace_id=_clean(os.getenv("FABRIC_WORKSPACE_ID")),
        anthropic_api_key=_clean(os.getenv("ANTHROPIC_API_KEY")),
        model=_clean(os.getenv("WANDA_MODEL")),
        provider=_clean(os.getenv("WANDA_PROVIDER")) or "anthropic",
        anthropic_base_url=_clean(os.getenv("ANTHROPIC_BASE_URL")) or ANTHROPIC_BASE_URL,
        azure_openai_endpoint=_clean(os.getenv("AZURE_OPENAI_ENDPOINT")),
        azure_openai_api_key=_clean(os.getenv("AZURE_OPENAI_API_KEY")),
        azure_openai_deployment=_clean(os.getenv("AZURE_OPENAI_DEPLOYMENT")),
        azure_anthropic_endpoint=_clean(os.getenv("AZURE_ANTHROPIC_ENDPOINT")),
        azure_anthropic_api_key=_clean(os.getenv("AZURE_ANTHROPIC_API_KEY")),
        azure_anthropic_deployment=_clean(os.getenv("AZURE_ANTHROPIC_DEPLOYMENT")),
    )
