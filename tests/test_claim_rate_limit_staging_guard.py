"""Synthetic guard and result checks; does not open any database."""
import unittest
from scripts.drill_claim_rate_limit_concurrency import (
    WORKERS, check_configuration, evaluate_results,
)


def env(**overrides):
    values = {
        "TAN_STAGING_DATABASE_URL": "postgresql://synthetic/staging",
        "TAN_DATABASE_URL": "postgresql://synthetic/production",
        "TAN_STAGING_CONFIRM": "disposable-isolated-database",
        "TAN_STAGING_DB_NAME": "tan_disposable_test",
    }
    values.update(overrides)
    return values


class ConcurrencyDrillGuardTests(unittest.TestCase):
    def test_valid_configuration(self):
        self.assertEqual(check_configuration(env())[1], "tan_disposable_test")

    def test_missing_staging_url_rejected(self):
        with self.assertRaises(RuntimeError):
            check_configuration(env(TAN_STAGING_DATABASE_URL=""))

    def test_production_url_rejected(self):
        with self.assertRaises(RuntimeError):
            check_configuration(env(TAN_STAGING_DATABASE_URL="same",
                                    TAN_DATABASE_URL="same"))

    def test_missing_confirmation_rejected(self):
        with self.assertRaises(RuntimeError):
            check_configuration(env(TAN_STAGING_CONFIRM=""))

    def test_generic_database_name_rejected(self):
        with self.assertRaises(RuntimeError):
            check_configuration(env(TAN_STAGING_DB_NAME="postgres"))

    def test_exactly_five_allowed(self):
        evaluate_results([True] * 5 + [False] * (WORKERS - 5))

    def test_over_limit_detected(self):
        with self.assertRaises(AssertionError):
            evaluate_results([True] * 6 + [False] * (WORKERS - 6))

    def test_under_limit_detected(self):
        with self.assertRaises(AssertionError):
            evaluate_results([True] * 4 + [False] * (WORKERS - 4))

    def test_missing_worker_detected(self):
        with self.assertRaises(AssertionError):
            evaluate_results([True] * 5)

    def test_non_boolean_detected(self):
        with self.assertRaises(AssertionError):
            evaluate_results([1] * 5 + [False] * (WORKERS - 5))


if __name__ == "__main__":
    unittest.main()
