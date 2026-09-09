"""Token Authentication Module for Locket Gold.

Features:
- HS256-signed Access Tokens (held strictly in React memory on frontend)
- Opaque random Refresh Tokens (stored exclusively in HttpOnly cookies, Path=/api/auth)
- HMAC-SHA256 hashed refresh tokens in database (never plain text)
- Refresh Token Rotation (RTR) on every refresh
- Refresh Token Replay Detection (revoking entire token family on reuse)
- Session Family management in auth_sessions table
- @access_required decorator checking Bearer token, session revocation, and active user state
- Complete isolation from Flask admin session (session["admin"])
"""

import hashlib
import hmac
import os
import secrets
import time
from functools import wraps

import jwt
from flask import g, jsonify, request

from . import db
from . import env  # Ensures .env is loaded before module-level os.getenv evaluation

# Configuration knobs from environment
JWT_ISSUER = os.getenv("JWT_ISSUER", "locket-gold")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "locket-gold-web")
ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "600"))  # 10 minutes
REFRESH_TOKEN_TTL_SECONDS = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "2592000"))  # 30 days
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "locket_refresh")
BEHIND_HTTPS = os.getenv("BEHIND_HTTPS") == "1"

# Secrets validation
_jwt_secret = os.getenv("JWT_SECRET")
_refresh_pepper = os.getenv("REFRESH_TOKEN_PEPPER")

if BEHIND_HTTPS and (not _jwt_secret or not _refresh_pepper):
    raise RuntimeError(
        "CRITICAL: JWT_SECRET and REFRESH_TOKEN_PEPPER environment variables must be configured in production (BEHIND_HTTPS=1)."
    )

if _jwt_secret and _refresh_pepper and _jwt_secret == _refresh_pepper:
    raise RuntimeError(
        "CRITICAL: JWT_SECRET and REFRESH_TOKEN_PEPPER must be distinct secrets."
    )

# Development fallbacks if unset in local non-production environment
DEFAULT_DEV_JWT_SECRET = "dev-jwt-secret-key-change-in-production-1234567890"
DEFAULT_DEV_PEPPER = "dev-refresh-pepper-change-in-production-0987654321"

JWT_SECRET = _jwt_secret or DEFAULT_DEV_JWT_SECRET
REFRESH_TOKEN_PEPPER = _refresh_pepper or DEFAULT_DEV_PEPPER


def add_no_store_headers(response):
    """Add strict Cache-Control headers to auth responses."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


# ---- Access Token Management ----

def create_access_token(user_id: int, family_id: str, expires_in: int = None) -> str:
    """Create an HS256-signed JWT access token."""
    now = int(time.time())
    ttl = expires_in if expires_in is not None else ACCESS_TOKEN_TTL_SECONDS
    payload = {
        "sub": str(user_id),
        "jti": secrets.token_hex(16),
        "sid": family_id,
        "type": "access",
        "iat": now,
        "exp": now + ttl,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Strictly decode and validate an access token using HS256 algorithm only."""
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=["HS256"],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={
            "require": ["exp", "iat", "sub", "jti", "sid", "type"],
            "verify_exp": True,
            "verify_iat": True,
            "verify_iss": True,
            "verify_aud": True,
        },
    )


# ---- Refresh Token Management ----

def generate_refresh_token() -> str:
    """Generate high-entropy cryptographically secure random refresh token."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    """Compute HMAC-SHA256 of the raw refresh token using REFRESH_TOKEN_PEPPER."""
    return hmac.new(
        REFRESH_TOKEN_PEPPER.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_token_family(user_id: int, remember_me: bool = False):
    """Create a new auth session family and initial refresh token.
    Returns: (family_id, raw_refresh_token, session_ttl)
    """
    family_id = secrets.token_hex(16)
    session_ttl = REFRESH_TOKEN_TTL_SECONDS if remember_me else 86400  # 30 days vs 1 day
    expires_at = time.time() + session_ttl

    db.create_auth_session(family_id, user_id, expires_at, remember_me=1 if remember_me else 0)

    raw_token = generate_refresh_token()
    token_id = secrets.token_hex(16)
    token_hash = hash_refresh_token(raw_token)
    db.store_refresh_token(token_id, family_id, token_hash, None, expires_at)

    return family_id, raw_token, session_ttl


def rotate_refresh_token(raw_token: str):
    """Rotate an existing refresh token with replay detection in an atomic transaction.
    Returns: (status, new_raw_token, new_access_token, user_dict, family_id, remember_me, remaining_ttl)
    """
    if not raw_token:
        return "missing_token", None, None, None, None, False, 0

    token_hash = hash_refresh_token(raw_token)
    token_record = db.get_refresh_token_by_hash(token_hash)
    if not token_record:
        return "invalid_token", None, None, None, None, False, 0

    family_id = token_record["family_id"]
    session_family = db.get_auth_session(family_id)
    if not session_family:
        return "session_not_found", None, None, None, None, False, 0

    remember_me = bool(session_family.get("remember_me", 0))
    now = time.time()
    remaining_ttl = max(0, int(session_family["expires_at"] - now))

    # Check if session family is already revoked
    if session_family.get("revoked_at") is not None:
        return "session_revoked", None, None, None, family_id, remember_me, remaining_ttl

    # Check if session family is expired
    if session_family["expires_at"] < now:
        db.revoke_auth_session(family_id, "session_expired")
        return "session_expired", None, None, None, family_id, remember_me, 0

    # Check if this specific refresh token was already used or revoked (REPLAY DETECTION)
    if token_record.get("used_at") is not None or token_record.get("revoked_at") is not None:
        db.revoke_auth_session(family_id, "replay_detected")
        return "replay_detected", None, None, None, family_id, remember_me, remaining_ttl

    # Check if this specific token is expired
    if token_record["expires_at"] < now:
        db.revoke_auth_session(family_id, "token_expired")
        return "token_expired", None, None, None, family_id, remember_me, 0

    # Prepare next rotated token
    new_raw_token = generate_refresh_token()
    new_token_id = secrets.token_hex(16)
    new_token_hash = hash_refresh_token(new_raw_token)
    # Match expiration with the session family
    new_expires_at = session_family["expires_at"]

    status, err = db.rotate_refresh_token_tx(
        family_id=family_id,
        old_token_id=token_record["id"],
        new_token_id=new_token_id,
        new_token_hash=new_token_hash,
        new_expires_at=new_expires_at,
    )

    if status == "replay_detected":
        return "replay_detected", None, None, None, family_id, remember_me, remaining_ttl
    if status != "ok":
        return "rotation_failed", None, None, None, family_id, remember_me, remaining_ttl

    # Fetch user & generate fresh access token
    user = db.get_user_by_id(session_family["user_id"])
    if not user or not user.get("is_active"):
        db.revoke_auth_session(family_id, "account_inactive")
        return "account_inactive", None, None, None, family_id, remember_me, remaining_ttl

    new_access_token = create_access_token(user["id"], family_id)
    return "ok", new_raw_token, new_access_token, user, family_id, remember_me, remaining_ttl


def revoke_token_family(family_id: str, reason: str = "user_logout"):
    """Revoke an entire token family."""
    if family_id:
        db.revoke_auth_session(family_id, reason)


# ---- Cookie Helpers ----

def get_refresh_cookie() -> str:
    """Retrieve raw refresh token from HttpOnly cookie."""
    return request.cookies.get(REFRESH_COOKIE_NAME)


def set_refresh_cookie(response, raw_token: str, remember_me: bool = False, max_age: int = None):
    """Set the HttpOnly refresh token cookie on a Flask response.
    If remember_me is False, max_age is strictly None (browser session cookie).
    If remember_me is True, max_age preserves the remaining family TTL.
    """
    cookie_max_age = (max_age if max_age is not None else REFRESH_TOKEN_TTL_SECONDS) if remember_me else None
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        raw_token,
        max_age=cookie_max_age,
        httponly=True,
        secure=BEHIND_HTTPS,
        samesite="Lax",
        path="/api/auth",
    )
    return response


def clear_refresh_cookie(response):
    """Clear the refresh token cookie using identical path, samesite, and secure settings."""
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        "",
        max_age=0,
        expires=0,
        httponly=True,
        secure=BEHIND_HTTPS,
        samesite="Lax",
        path="/api/auth",
    )
    return response


# ---- access_required Decorator ----

def access_required(view):
    """Decorator protecting service endpoints using Bearer JWT access tokens.
    Populates g.current_user and g.access_token upon success.
    Returns standard JSON errors on failure without leaking internals.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "").strip()
        if not auth_header:
            return jsonify({
                "success": False,
                "error": "missing_access_token",
                "msg": "Vui lòng cung cấp Access Token trong header Authorization: Bearer <token>.",
            }), 401

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({
                "success": False,
                "error": "invalid_access_token",
                "msg": "Định dạng header Authorization không hợp lệ. Yêu cầu Bearer <token>.",
            }), 401

        raw_jwt = parts[1]

        try:
            payload = decode_access_token(raw_jwt)
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "error": "access_token_expired",
                "msg": "Access Token đã hết hạn. Vui lòng làm mới token.",
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "error": "invalid_access_token",
                "msg": "Access Token không hợp lệ hoặc đã bị chỉnh sửa.",
            }), 401
        except Exception:
            return jsonify({
                "success": False,
                "error": "invalid_access_token",
                "msg": "Không thể giải mã Access Token.",
            }), 401

        # Verify token type
        if payload.get("type") != "access":
            return jsonify({
                "success": False,
                "error": "invalid_access_token",
                "msg": "Token không phải là loại access token.",
            }), 401

        # Check session family validity in DB
        family_id = payload.get("sid")
        session_family = db.get_auth_session(family_id)
        if not session_family or session_family.get("revoked_at") is not None:
            return jsonify({
                "success": False,
                "error": "token_session_revoked",
                "msg": "Phiên đăng nhập đã bị thu hồi hoặc đã đăng xuất.",
            }), 401

        # Check session family expiration in DB
        now = time.time()
        if session_family.get("expires_at", 0) < now:
            db.revoke_auth_session(family_id, "session_expired")
            return jsonify({
                "success": False,
                "error": "session_expired",
                "msg": "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.",
            }), 401

        # Check user active status in DB
        try:
            user_id = int(payload.get("sub"))
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "invalid_access_token",
                "msg": "User ID trong token không hợp lệ.",
            }), 401

        # Enforce that sub in token matches user_id of the session family
        if user_id != session_family.get("user_id"):
            return jsonify({
                "success": False,
                "error": "invalid_access_token",
                "msg": "Token không hợp lệ (thông tin người dùng không khớp).",
            }), 401

        user = db.get_user_by_id(user_id)
        if not user or not user.get("is_active"):
            return jsonify({
                "success": False,
                "error": "account_inactive",
                "msg": "Tài khoản không tồn tại hoặc đã bị khóa.",
            }), 403

        # Populate Flask request globals
        g.current_user = user
        g.access_token = payload

        return view(*args, **kwargs)

    return wrapped
