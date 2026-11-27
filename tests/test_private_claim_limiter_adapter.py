"""Synthetic tests for claim rate-limiter injection boundary."""
import unittest
from unittest.mock import patch
from private_claim_limiter_adapter import build_claim_limiter


class ContextConn:
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


class Request:
    def get_json(self, silent=True):
        return {"messenger_code": "synthetic"}


class AdapterTests(unittest.TestCase):
    def test_explicit_trusted_identity_used(self):
        with patch("private_claim_limiter_adapter.require_both_buckets",
                   return_value=True) as check:
            limiter = build_claim_limiter(lambda: ContextConn(),
                                          lambda request: "trusted-client",
                                          secret="synthetic")
            self.assertTrue(limiter(Request()))
            self.assertEqual(check.call_args.kwargs["client_identifier"],
                             "trusted-client")

    def test_missing_trusted_identity_denied(self):
        limiter = build_claim_limiter(lambda: ContextConn(), lambda request: None,
                                      secret="synthetic")
        with self.assertRaises(ValueError):
            limiter(Request())

    def test_no_implicit_identity_resolver(self):
        with self.assertRaises(ValueError):
            build_claim_limiter(lambda: ContextConn(), None, secret="synthetic")

    def test_storage_error_propagates(self):
        with patch("private_claim_limiter_adapter.require_both_buckets",
                   side_effect=RuntimeError("synthetic outage")):
            limiter = build_claim_limiter(lambda: ContextConn(),
                                          lambda request: "trusted-client",
                                          secret="synthetic")
            with self.assertRaises(RuntimeError):
                limiter(Request())


if __name__ == "__main__":
    unittest.main()
