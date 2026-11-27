"""Synthetic-only checks for disposable staging database identity guard."""
import importlib.util
from pathlib import Path
import unittest

p = Path(__file__).resolve().parents[1] / "scripts/drill_messenger_link_concurrency.py"
spec = importlib.util.spec_from_file_location("staging_drill", p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Cursor:
    def __init__(self, identity, markers):
        self.identity, self.markers = identity, markers
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql):
        self.queries.append(sql)

    def fetchone(self):
        return self.identity

    def fetchall(self):
        return self.markers


class Conn:
    def __init__(self, identity, markers):
        self.cur = Cursor(identity, markers)

    def cursor(self):
        return self.cur


class GuardTests(unittest.TestCase):
    def test_matching_disposable_database(self):
        conn = Conn(("tan_test_disposable", "tan_private.staging_drill_guard"),
                    [("disposable-isolated-database",)])
        module.verify_staging_identity(conn, "tan_test_disposable")
        self.assertEqual(len(conn.cur.queries), 2)

    def test_wrong_database_rejected(self):
        conn = Conn(("production", "tan_private.staging_drill_guard"),
                    [("disposable-isolated-database",)])
        with self.assertRaises(RuntimeError):
            module.verify_staging_identity(conn, "tan_test_disposable")
        self.assertEqual(len(conn.cur.queries), 1)

    def test_missing_guard_rejected(self):
        conn = Conn(("tan_test_disposable", None), [])
        with self.assertRaises(RuntimeError):
            module.verify_staging_identity(conn, "tan_test_disposable")

    def test_invalid_marker_rejected(self):
        conn = Conn(("tan_test_disposable", "tan_private.staging_drill_guard"), [("wrong",)])
        with self.assertRaises(RuntimeError):
            module.verify_staging_identity(conn, "tan_test_disposable")

    def test_generic_database_name_rejected(self):
        conn = Conn(("postgres", "tan_private.staging_drill_guard"),
                    [("disposable-isolated-database",)])
        with self.assertRaises(RuntimeError):
            module.verify_staging_identity(conn, "postgres")
        self.assertEqual(conn.cur.queries, [])


if __name__ == "__main__":
    unittest.main()
