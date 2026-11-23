"""Explicitly isolated, test-only Flask app factory for the versioned API.

Never import or register this factory in the production app. The caller must
provide a connector; this module does not read any production environment URL.
"""
from flask import Flask
from versioned_subscriber_api_routes import versioned_blueprint


def create_isolated_staging_app(*, db_connect, canonical_origin, environment):
    if environment != "isolated-staging" or not callable(db_connect):
        raise ValueError("An explicit isolated-staging environment and DB connector are required")
    if not isinstance(canonical_origin, str) or canonical_origin not in ("https://localhost", "https://127.0.0.1"):
        raise ValueError("Staging canonical origin must be HTTPS loopback")
    app = Flask("tan_versioned_isolated_staging")
    app.config.update(TESTING=True, TAN_PRIVATE_DB_CONNECT=db_connect,
                      TAN_CANONICAL_ORIGIN=canonical_origin)
    app.register_blueprint(versioned_blueprint)
    return app
