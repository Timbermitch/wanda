"""Telemetry tests — opt-in only, anonymous, leak-proof, and never fatal."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wanda import telemetry


class TelemetryTest(unittest.TestCase):
    def setUp(self):
        for k in ("WANDA_TELEMETRY", "WANDA_TELEMETRY_URL"):
            os.environ.pop(k, None)
        telemetry._threads.clear()
        self._orig_post = telemetry._post
        self._orig_install = telemetry._install_id
        telemetry._install_id = lambda: "test-install-id"
        self.sent = []
        telemetry._post = lambda url, payload: self.sent.append((url, payload))

    def tearDown(self):
        telemetry._post = self._orig_post
        telemetry._install_id = self._orig_install
        for k in ("WANDA_TELEMETRY", "WANDA_TELEMETRY_URL"):
            os.environ.pop(k, None)

    def _drain(self):
        for t in list(telemetry._threads):
            t.join(timeout=2)

    def test_disabled_by_default(self):
        self.assertFalse(telemetry.is_enabled())

    def test_opt_in_needs_both_flag_and_url(self):
        os.environ["WANDA_TELEMETRY"] = "on"
        self.assertFalse(telemetry.is_enabled())          # flag but no endpoint
        os.environ["WANDA_TELEMETRY_URL"] = "https://collect.example"
        self.assertTrue(telemetry.is_enabled())

    def test_emit_is_noop_when_disabled(self):
        telemetry.emit("run", status="ok", mode="INVESTIGATION")
        self._drain()
        self.assertEqual(self.sent, [])

    def test_emit_sends_safe_payload_when_enabled(self):
        os.environ["WANDA_TELEMETRY"] = "on"
        os.environ["WANDA_TELEMETRY_URL"] = "https://collect.example"
        telemetry.emit("run", status="ok", mode="INVESTIGATION",
                       duration_seconds=12.3, tool_calls=4, turns=3)
        self._drain()
        self.assertEqual(len(self.sent), 1)
        url, payload = self.sent[0]
        self.assertEqual(url, "https://collect.example")
        self.assertEqual(payload["event"], "run")
        self.assertEqual(payload["install_id"], "test-install-id")
        self.assertIn("wanda_version", payload)
        self.assertEqual(payload["status"], "ok")
        # Leak-proof: no identifying/sensitive keys or values anywhere in the blob.
        blob = json.dumps(payload).lower()
        for bad in ("client_secret", "api_key", "password", "pipeline_name",
                    "workspace", "sk-ant", "select "):
            self.assertNotIn(bad, blob)

    def test_post_swallows_all_errors(self):
        # The real _post must never raise — here an invalid URL makes requests
        # throw immediately (no network), and _post must absorb it.
        telemetry._post = self._orig_post
        try:
            telemetry._post("not-a-valid-url", {"event": "run"})
        except Exception as exc:  # pragma: no cover
            self.fail(f"_post() must never raise, but raised {exc!r}")


if __name__ == "__main__":
    unittest.main()
