"""Session-based admin auth with CSRF protection.

Single password from ADMIN_PASSWORD env. After login, session["admin"] = True
and Flask's session cookie (HttpOnly, SameSite=Lax) is set. The decorator
distinguishes HTML and JSON callers: HTML pages get a redirect to /admin/login,
JSON endpoints get a 401 so the frontend can show its own error.
"""

import hmac
import os
import secrets
from functools import wraps

from flask import jsonify, redirect, request, session


def is_admin_logged_in():
    return bool(session.get("admin"))


def check_credentials(username, password):
    expected_user = os.getenv("ADMIN_USERNAME")
    expected_pass = os.getenv("ADMIN_PASSWORD")
    if not expected_user or not expected_pass:
        return False
    return username == expected_user and password == expected_pass


def get_admin_csrf_token():
    """Ensure an admin-specific CSRF token exists in the session."""
    token = session.get("admin_csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["admin_csrf_token"] = token
    return token


def validate_admin_csrf():
    """Validate admin CSRF token sent in X-CSRF-Token header."""
    session_token = session.get("admin_csrf_token")
    if not session_token:
        return False
    header_token = request.headers.get("X-CSRF-Token")
    if not header_token and request.is_json and request.json:
        header_token = request.json.get("csrf_token")
    if not header_token and request.form:
        header_token = request.form.get("csrf_token")
    if not header_token:
        return False
    return hmac.compare_digest(header_token, session_token)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if is_admin_logged_in():
            return view(*args, **kwargs)
        if request.path.startswith("/admin/api/"):
            return jsonify({"success": False, "error": "unauthorized"}), 401
        return redirect("/admin/login")

    return wrapped
