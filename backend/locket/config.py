"""Flask config knobs sourced from environment variables.

`configure(app)` mutates `app.config` and `app.wsgi_app` in place. Called once
from `create_app`. Keep this small — most behaviour-driving env vars
(`EMAIL`, `gist_token_url`, `ADMIN_PASSWORD`, …) are read by the modules that
use them, not lifted into Flask config.
"""

import os
import secrets


def configure(app):
    behind_https = os.getenv("BEHIND_HTTPS") == "1"
    secret = os.getenv("FLASK_SECRET_KEY")
    if behind_https and not secret:
        raise RuntimeError(
            "CRITICAL: FLASK_SECRET_KEY must be configured in production (BEHIND_HTTPS=1)."
        )
    if not secret:
        secret = secrets.token_hex(32)
        print(
            "WARNING: FLASK_SECRET_KEY not set; admin sessions will be invalidated on restart."
        )
    app.config["SECRET_KEY"] = secret
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = behind_https

    # Request size limit: max 10MB to prevent memory DoS on large uploads
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    # Resolve review storage root after env is loaded
    storage_root = os.getenv("REVIEW_STORAGE_ROOT")
    if behind_https and not storage_root:
        raise RuntimeError(
            "CRITICAL: REVIEW_STORAGE_ROOT must be configured in production (BEHIND_HTTPS=1)."
        )
    if not storage_root:
        storage_root = os.path.abspath(
            os.path.join(app.root_path, "..", "storage", "reviews")
        )
    app.config["REVIEW_STORAGE_ROOT"] = storage_root
    try:
        os.makedirs(storage_root, exist_ok=True)
    except OSError as e:
        print(f"Warning: could not create storage root at {storage_root}: {e}")

    creator_storage_root = os.getenv("CREATOR_STORAGE_ROOT")
    if not creator_storage_root:
        creator_storage_root = os.path.join(storage_root, "creators")
    app.config["CREATOR_STORAGE_ROOT"] = creator_storage_root
    try:
        os.makedirs(creator_storage_root, exist_ok=True)
    except OSError as e:
        print(f"Warning: could not create creator storage at {creator_storage_root}: {e}")

    if behind_https:
        # Trust X-Forwarded-* headers from nginx so url_for() / scheme
        # detection know we're behind TLS. Without this, redirects after
        # login can drop to http.
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
