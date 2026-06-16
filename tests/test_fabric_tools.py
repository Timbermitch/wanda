"""Fabric tools tests — the code-enforced read-only SQL guard."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import wanda.fabric_tools as ft
from wanda.config import Config
from wanda.fabric_tools import _is_read_only_sql, _run_sql, _sql_token_struct


class TestReadOnlySqlGuard(unittest.TestCase):
    def test_allows_plain_selects(self):
        for q in [
            "SELECT * FROM Orders",
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES",
            "select top 1 * from sales",
            "WITH c AS (SELECT 1) SELECT * FROM c",
        ]:
            self.assertTrue(_is_read_only_sql(q), q)

    def test_allows_names_that_embed_keywords(self):
        # Underscores/letters around a keyword mean it isn't a real verb.
        for q in ["SELECT * FROM update_log", "SELECT created_at FROM t"]:
            self.assertTrue(_is_read_only_sql(q), q)

    def test_rejects_writes_and_ddl(self):
        for q in [
            "DROP TABLE t",
            "DELETE FROM t WHERE 1=1",
            "UPDATE t SET x=1",
            "INSERT INTO t VALUES (1)",
            "SELECT * INTO new_t FROM t",   # SELECT ... INTO writes a table
            "TRUNCATE TABLE t",
            "EXEC sp_who",
            "MERGE t USING s ON t.id=s.id WHEN MATCHED THEN UPDATE SET x=1",
        ]:
            self.assertFalse(_is_read_only_sql(q), q)

    def test_run_sql_refuses_writes_before_connecting(self):
        # A write query must be refused without ever importing pyodbc / connecting.
        out = _run_sql("server", "db", "DROP TABLE t", "SQL")
        self.assertIn("Refused", out)
        self.assertIn("read-only", out)


class TokenAuthTest(unittest.TestCase):
    def setUp(self):
        self._orig_cfg = ft._cfg

    def tearDown(self):
        ft._cfg = self._orig_cfg

    def test_get_token_uses_supplied_token_without_http(self):
        # With a bring-your-own-token, get_token returns it directly — no SP, no HTTP.
        ft._cfg = Config(tenant_id=None, client_id=None, client_secret=None,
                         workspace_id="w", anthropic_api_key=None,
                         fabric_access_token="my-fabric-token")
        self.assertEqual(ft.get_token(), "my-fabric-token")

    def test_sql_token_struct_is_length_prefixed_utf16(self):
        packed = _sql_token_struct("abc")
        # 4-byte little-endian length prefix, then UTF-16-LE bytes (6 for "abc").
        self.assertEqual(packed[:4], (6).to_bytes(4, "little"))
        self.assertEqual(packed[4:], "abc".encode("utf-16-le"))

    def test_run_sql_skips_cleanly_when_no_credentials(self):
        ft._cfg = Config(tenant_id=None, client_id=None, client_secret=None,
                         workspace_id="w", anthropic_api_key=None)
        out = _run_sql("server", "db", "SELECT 1", "SQL")
        # Graceful skip (no crash) whether pyodbc is absent or creds are missing.
        self.assertTrue(any(s in out.lower() for s in ("skipped", "not installed", "unavailable")), out)


if __name__ == "__main__":
    unittest.main()
