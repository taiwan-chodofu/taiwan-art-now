"""Explicit opt-in adapter for the isolated claim route.

The client identity resolver MUST be configured from trusted deployment
network metadata, not request.remote_addr without proxy review and never a
raw X-Forwarded-For header. Not registered in production.
"""
from private_claim_rate_limit import require_both_buckets


def build_claim_limiter(connect, trusted_client_identity, *, secret):
    if not callable(connect) or not callable(trusted_client_identity):
        raise ValueError("Trusted connector and identity resolver required")

    def limiter(request):
        client = trusted_client_identity(request)
        if not isinstance(client, str) or not client:
            raise ValueError("Trusted client identity unavailable")
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ValueError("Invalid claim payload")
        challenge = body.get("messenger_code")
        if not isinstance(challenge, str) or not challenge:
            raise ValueError("Invalid challenge")
        with connect() as conn:
            return require_both_buckets(
                conn, client_identifier=client,
                challenge_identifier=challenge, secret=secret)
    return limiter
