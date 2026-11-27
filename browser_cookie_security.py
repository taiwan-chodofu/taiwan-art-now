"""Isolated browser cookie and same-origin request guards.

NOT wired to app routes. Host must configure canonical HTTPS origin and
trusted proxy settings before these helpers can be used for authentication.
"""
from urllib.parse import urlsplit

COOKIE_NAME = "__Host-tan_session"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _canonical_origin(value):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Invalid origin")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.path or parsed.query or parsed.fragment or
            not parsed.netloc or parsed.netloc.endswith(":")):
        raise ValueError("HTTPS origin required")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid port") from exc
    if port is not None and port != 443:
        raise ValueError("Unexpected origin port")
    return "https://" + parsed.hostname.lower()


def require_same_origin(method, origin, allowed_origin, sec_fetch_site=None):
    """Reject unsafe requests without an exact trusted Origin header.

    This is a defense-in-depth guard, not a substitute for verified sessions.
    """
    if not isinstance(method, str):
        return False
    if method.upper() in SAFE_METHODS:
        return True
    try:
        expected = _canonical_origin(allowed_origin)
        supplied = _canonical_origin(origin)
    except ValueError:
        return False
    if supplied != expected:
        return False
    if sec_fetch_site is not None and sec_fetch_site not in ("same-origin", "none"):
        return False
    return True


def set_session_cookie(response, token, *, max_age=3600):
    if not isinstance(token, str) or not token or len(token) > 256 or any(
        ord(ch) < 33 or ord(ch) > 126 or ch in ';,"\\' for ch in token
    ):
        raise ValueError("Invalid cookie token")
    if not isinstance(max_age, int) or isinstance(max_age, bool) or not 1 <= max_age <= 86400:
        raise ValueError("Invalid cookie lifetime")
    response.set_cookie(
        COOKIE_NAME, token, max_age=max_age, secure=True, httponly=True,
        samesite="Lax", path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def clear_session_cookie(response):
    response.delete_cookie(COOKIE_NAME, secure=True, httponly=True,
                           samesite="Lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return response
