"""Config validation tests — placeholder detection and per-provider requires."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wanda.config import Config, ConfigError, _clean


def make_config(**kw):
    base = dict(tenant_id="t", client_id="c", client_secret="s", workspace_id="w",
                anthropic_api_key="sk")
    base.update(kw)
    return Config(**base)


class TestClean(unittest.TestCase):
    def test_placeholders_treated_as_unset(self):
        self.assertIsNone(_clean("your-tenant-guid-here"))
        self.assertIsNone(_clean("your-anthropic-api-key-here"))
        self.assertIsNone(_clean("   "))
        self.assertIsNone(_clean(None))

    def test_real_values_pass_through_stripped(self):
        self.assertEqual(_clean("  value "), "value")


class TestRequires(unittest.TestCase):
    def test_require_fabric_workspace_always_required(self):
        cfg = make_config(workspace_id=None)
        with self.assertRaises(ConfigError) as ctx:
            cfg.require_fabric()
        self.assertIn("FABRIC_WORKSPACE_ID", str(ctx.exception))

    def test_require_fabric_lists_missing_service_principal_values(self):
        # Workspace present, token absent → must list the missing SP values.
        cfg = make_config(tenant_id=None, client_secret=None)
        with self.assertRaises(ConfigError) as ctx:
            cfg.require_fabric()
        message = str(ctx.exception)
        self.assertIn("FABRIC_TENANT_ID", message)
        self.assertIn("FABRIC_CLIENT_SECRET", message)
        self.assertNotIn("FABRIC_CLIENT_ID,", message)  # client_id present → not listed

    def test_require_fabric_token_mode_skips_service_principal(self):
        # A bring-your-own-token + workspace is enough; no SP needed.
        cfg = make_config(tenant_id=None, client_id=None, client_secret=None,
                          fabric_access_token="tok")
        self.assertIs(cfg.require_fabric(), cfg)

    def test_require_fabric_token_without_workspace_still_fails(self):
        # Workspace is required even in token mode — checked before the token.
        cfg = make_config(workspace_id=None, tenant_id=None, client_id=None,
                          client_secret=None, fabric_access_token="tok")
        with self.assertRaises(ConfigError) as ctx:
            cfg.require_fabric()
        self.assertIn("FABRIC_WORKSPACE_ID", str(ctx.exception))

    def test_require_anthropic(self):
        with self.assertRaises(ConfigError):
            make_config(anthropic_api_key=None).require_anthropic()
        cfg = make_config()
        self.assertIs(cfg.require_anthropic(), cfg)

    def test_require_azure_openai_lists_missing(self):
        cfg = make_config(provider="azure-openai",
                          azure_openai_endpoint="https://e.openai.azure.com")
        with self.assertRaises(ConfigError) as ctx:
            cfg.require_azure_openai()
        message = str(ctx.exception)
        self.assertIn("AZURE_OPENAI_API_KEY", message)
        self.assertIn("AZURE_OPENAI_DEPLOYMENT", message)
        self.assertNotIn("AZURE_OPENAI_ENDPOINT,", message)

    def test_chaining_returns_self(self):
        cfg = make_config()
        self.assertIs(cfg.require_fabric().require_anthropic(), cfg)


if __name__ == "__main__":
    unittest.main()
