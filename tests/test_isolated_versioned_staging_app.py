import unittest
from isolated_versioned_staging_app import create_isolated_staging_app


class IsolatedStagingFactoryTests(unittest.TestCase):
    def test_refuses_missing_environment_or_connector(self):
        for env, connector in (("production", lambda: None), ("isolated-staging", None)):
            with self.subTest(env=env):
                with self.assertRaises(ValueError):
                    create_isolated_staging_app(db_connect=connector,
                        canonical_origin="https://127.0.0.1", environment=env)

    def test_refuses_external_origin(self):
        with self.assertRaises(ValueError):
            create_isolated_staging_app(db_connect=lambda: None,
                canonical_origin="https://taiwan-art-now.onrender.com",
                environment="isolated-staging")

    def test_registers_only_versioned_and_review_routes_and_denies_without_cookie(self):
        class FakeConnection:
            autocommit = False
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def rollback(self): pass
            def cursor(self):
                class Cursor:
                    def __enter__(self): return self
                    def __exit__(self, *_): return False
                    def execute(self, *_): pass
                    def fetchone(self): return None
                return Cursor()
        app=create_isolated_staging_app(db_connect=FakeConnection,
            canonical_origin="https://127.0.0.1", environment="isolated-staging")
        routes={rule.rule for rule in app.url_map.iter_rules() if rule.rule!="/static/<path:filename>"}
        self.assertEqual(routes,{"/api/private-subscribers/v2/state",
                                 "/api/private-subscribers/v2/changes",
                                 "/api/private-subscribers/v2/review/keep/issue",
                                 "/api/private-subscribers/v2/review/keep/consume"})
        with app.test_client() as client:
            response=client.get("/api/private-subscribers/v2/state",
                headers={"Origin":"https://127.0.0.1"})
            self.assertEqual(response.status_code,403)


if __name__ == "__main__": unittest.main()
