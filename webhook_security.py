"""Verify Meta webhook X-Hub-Signature-256 using raw request bytes.

No fallback secret. Never log raw payloads, signatures, or app secrets.
"""
import hashlib
import hmac
import os


def verify_meta_webhook(raw_body, signature_header, *, app_secret=None):
    if app_secret is None:
        app_secret = os.environ.get("META_APP_SECRET", "")
    if not isinstance(raw_body, bytes) or not isinstance(signature_header, str):
        return False
    if not app_secret or not signature_header.startswith("sha256="):
        return False
    supplied = signature_header[len("sha256="):]
    if len(supplied) != 64:
        return False
    try:
        int(supplied, 16)
    except ValueError:
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied.lower())
