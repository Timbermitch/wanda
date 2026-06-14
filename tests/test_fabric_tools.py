"""Fabric tools tests — the code-enforced read-only SQL guard."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wanda.fabric_tools import _is_read_only_sql, _run_sql


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


if __name__ == "__main__":
    unittest.main()
