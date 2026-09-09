"""Customer authentication endpoints for Locket Gold.

Implements:
- Access Token (JWT HS256) returned in JSON payload
- Refresh Token stored strictly in HttpOnly cookie
- Token rotation & replay detection
- Strict CSRF protection on state-changing cookie endpoints
- Independent rate limiting keyed by IP and identifier/family
- Session family revocation on logout & replay
- Absolute isolation from Flask admin session
"""

import hmac
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque

import jwt
from flask import Blueprint, jsonify, make_response, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .token_auth import (
    ACCESS_TOKEN_TTL_SECONDS,
    access_required,
    add_no_store_headers,
    clear_refresh_cookie,
    create_access_token,
    create_token_family,
    decode_access_token,
    get_refresh_cookie,
    revoke_token_family,
    rotate_refresh_token,
    set_refresh_cookie,
)
from .google_auth import get_google_client_id, verify_google_token

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Input regex patterns
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,20}$")

# Rate limiting storage: key -> deque of timestamps
_rate_limits = defaultdict(deque)
_rate_lock = threading.Lock()


def is_rate_limited(key: str, max_requests: int, window_seconds: int) -> bool:
    """Sliding-window in-memory rate limiter."""
    now = time.time()
    cutoff = now - window_seconds
    with _rate_lock:
        dq = _rate_limits[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= max_requests:
            return True
        dq.append(now)
        # Periodically clean empty keys to bound memory
        if len(_rate_limits) > 5000:
            stale = [k for k, v in _rate_limits.items() if not v or v[-1] < cutoff]
            for sk in stale:
                _rate_limits.pop(sk, None)
        return False


def reset_rate_limits():
    """Helper for testing to reset rate limit state."""
    with _rate_lock:
        _rate_limits.clear()


def get_client_ip() -> str:
    """Return client IP address from remote_addr (safe after ProxyFix)."""
    return request.remote_addr or "127.0.0.1"


def get_csrf_token() -> str:
    """Ensure a CSRF token exists in the Flask session and return it."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    return token


def validate_csrf() -> bool:
    """Validate CSRF token sent via X-CSRF-Token header, JSON body, or form data against session."""
    session_token = session.get("csrf_token")
    if not session_token:
        return False
    request_token = request.headers.get("X-CSRF-Token")
    if not request_token and request.is_json and request.json:
        request_token = request.json.get("csrf_token")
    if not request_token and request.form:
        request_token = request.form.get("csrf_token")
    if not request_token:
        return False
    return hmac.compare_digest(str(session_token), str(request_token))



# ---- Auth Endpoints ----

@auth_bp.route("/csrf", methods=["GET"])
def csrf_token_endpoint():
    """Returns the current CSRF token, generating one if absent."""
    resp = make_response(jsonify({
        "success": True,
        "csrf_token": get_csrf_token(),
    }))
    return add_no_store_headers(resp)


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new customer account, create token family, and return access token."""
    # Check maintenance mode: registration is disabled during maintenance
    from . import site_settings
    m = site_settings.get_maintenance()
    if m.get("enabled"):
        resp = make_response(jsonify({
            "success": False,
            "maintenance": True,
            "error": "maintenance_mode",
            "msg": m.get("message") or "Hệ thống đang bảo trì, chức năng đăng ký tạm thời đóng.",
            "end_at": m.get("end_at") or None,
        }), 503)
        return add_no_store_headers(resp)

    ip = get_client_ip()
    if is_rate_limited(f"reg:{ip}", max_requests=10, window_seconds=300):
        resp = make_response(jsonify({
            "success": False,
            "error": "rate_limited",
            "msg": "Bạn đã thực hiện quá nhiều thao tác đăng ký. Vui lòng thử lại sau vài phút.",
        }), 429)
        return add_no_store_headers(resp)

    # CSRF check
    if not validate_csrf():
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF không hợp lệ. Vui lòng tải lại trang.",
        }), 403)
        return add_no_store_headers(resp)

    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    username = (data.get("username") or "").strip().lower()
    display_name = (data.get("display_name") or "").strip()
    password = data.get("password") or ""

    # Field validations
    if not email or not EMAIL_REGEX.match(email) or len(email) > 100:
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_email",
            "msg": "Địa chỉ email không đúng định dạng hoặc vượt quá độ dài cho phép.",
        }), 400)
        return add_no_store_headers(resp)

    if not username or not USERNAME_REGEX.match(username):
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_username",
            "msg": "Username phải có độ dài 3-20 ký tự, chỉ gồm chữ cái, chữ số và gạch dưới.",
        }), 400)
        return add_no_store_headers(resp)

    if not password or len(password) < 10 or len(password) > 128:
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_password",
            "msg": "Mật khẩu phải có độ dài tối thiểu 10 ký tự và tối đa 128 ký tự.",
        }), 400)
        return add_no_store_headers(resp)

    if not display_name:
        display_name = username
    elif len(display_name) > 50:
        display_name = display_name[:50]

    # Duplicate checks
    if db.get_user_by_email(email):
        resp = make_response(jsonify({
            "success": False,
            "error": "email_exists",
            "msg": "Địa chỉ email này đã được sử dụng. Vui lòng đăng nhập hoặc dùng email khác.",
        }), 409)
        return add_no_store_headers(resp)

    if db.get_user_by_username(username):
        resp = make_response(jsonify({
            "success": False,
            "error": "username_exists",
            "msg": "Username này đã được sử dụng. Vui lòng chọn username khác.",
        }), 409)
        return add_no_store_headers(resp)

    # Hash password securely
    password_hash = generate_password_hash(password)

    try:
        user_id = db.create_user(
            email=email,
            username=username,
            display_name=display_name,
            password_hash=password_hash,
        )
    except Exception as e:
        print(f"Error creating user: {e}")
        resp = make_response(jsonify({
            "success": False,
            "error": "database_error",
            "msg": "Lỗi khi lưu tài khoản vào cơ sở dữ liệu.",
        }), 500)
        return add_no_store_headers(resp)

    # Create token family & access token (No session["user_id"]!)
    family_id, raw_refresh_token, session_ttl = create_token_family(user_id, remember_me=True)
    access_token = create_access_token(user_id, family_id)

    resp = make_response(jsonify({
        "success": True,
        "msg": "Đăng ký tài khoản thành công!",
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "user": {
            "id": user_id,
            "email": email,
            "username": username,
            "display_name": display_name,
            "role": "user",
        },
        "csrf_token": get_csrf_token(),
    }), 201)

    set_refresh_cookie(resp, raw_refresh_token, remember_me=True, max_age=session_ttl)
    return add_no_store_headers(resp)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate user, create new token family, set refresh cookie, and return access token."""
    ip = get_client_ip()

    data = request.json or {}
    identifier = (data.get("identifier") or "").strip().lower()
    password = data.get("password") or ""
    remember_me = bool(data.get("remember_me", False))

    # Rate limiting by IP + normalized identifier
    rate_key = f"login:{ip}:{identifier}"
    if is_rate_limited(rate_key, max_requests=15, window_seconds=60):
        resp = make_response(jsonify({
            "success": False,
            "error": "rate_limited",
            "msg": "Bạn đã thử đăng nhập quá nhiều lần. Vui lòng chờ 1 phút.",
        }), 429)
        return add_no_store_headers(resp)

    # CSRF check
    if not validate_csrf():
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF không hợp lệ. Vui lòng tải lại trang.",
        }), 403)
        return add_no_store_headers(resp)

    if not identifier or not password:
        resp = make_response(jsonify({
            "success": False,
            "error": "missing_fields",
            "msg": "Vui lòng nhập đầy đủ tài khoản và mật khẩu.",
        }), 400)
        return add_no_store_headers(resp)

    user = db.get_user_by_identifier(identifier)
    if not user:
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_credentials",
            "msg": "Tài khoản hoặc mật khẩu không chính xác.",
        }), 401)
        return add_no_store_headers(resp)

    if not user.get("is_active"):
        resp = make_response(jsonify({
            "success": False,
            "error": "account_inactive",
            "msg": "Tài khoản của bạn tạm thời bị khóa. Vui lòng liên hệ hỗ trợ.",
        }), 403)
        return add_no_store_headers(resp)

    if not check_password_hash(user["password_hash"], password):
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_credentials",
            "msg": "Tài khoản hoặc mật khẩu không chính xác.",
        }), 401)
        return add_no_store_headers(resp)

    # Create new session family & tokens (Preserves session["admin"] untouched!)
    family_id, raw_refresh_token, session_ttl = create_token_family(user["id"], remember_me=remember_me)
    access_token = create_access_token(user["id"], family_id)

    db.update_user_last_login(user["id"])

    resp = make_response(jsonify({
        "success": True,
        "msg": "Đăng nhập thành công!",
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "display_name": user["display_name"],
            "avatar_url": user.get("avatar_url"),
            "role": user.get("role", "user"),
        },
        "csrf_token": get_csrf_token(),
    }))

    set_refresh_cookie(resp, raw_refresh_token, remember_me=remember_me, max_age=session_ttl)
    return add_no_store_headers(resp)


@auth_bp.route("/google", methods=["POST"])
def google_auth():
    """Authenticate or register user via verified Google ID Token."""
    ip = get_client_ip()
    if is_rate_limited(f"google:{ip}", max_requests=20, window_seconds=60):
        resp = make_response(jsonify({
            "success": False,
            "error": "rate_limited",
            "msg": "Bạn đã thực hiện quá nhiều yêu cầu đăng nhập. Vui lòng thử lại sau 1 phút.",
        }), 429)
        return add_no_store_headers(resp)

    # This endpoint creates a refresh-token cookie, so CSRF is mandatory.
    if not validate_csrf():
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF không hợp lệ. Vui lòng tải lại trang.",
        }), 403)
        return add_no_store_headers(resp)

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    credential = (data.get("credential") or data.get("id_token") or "").strip()
    if not credential:
        resp = make_response(jsonify({
            "success": False,
            "error": "missing_credential",
            "msg": "Vui lòng cung cấp mã xác thực Google (credential).",
        }), 400)
        return add_no_store_headers(resp)

    if not get_google_client_id():
        resp = make_response(jsonify({
            "success": False,
            "error": "google_not_configured",
            "msg": "Google Sign-In chưa được cấu hình trên máy chủ.",
        }), 503)
        return add_no_store_headers(resp)

    # Verify ID token with Google
    is_valid, google_data, err_msg = verify_google_token(credential)
    if not is_valid or not google_data:
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_google_token",
            "msg": err_msg or "Xác thực tài khoản Google thất bại.",
        }), 401)
        return add_no_store_headers(resp)

    email = (google_data.get("email") or "").strip().lower()
    name = (google_data.get("name") or "").strip()
    google_id = str(google_data.get("sub") or "").strip()
    avatar_url = google_data.get("picture")

    if not email or not EMAIL_REGEX.match(email):
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_email",
            "msg": "Tài khoản Google không có email hợp lệ.",
        }), 400)
        return add_no_store_headers(resp)

    if not google_id:
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_google_subject",
            "msg": "Tài khoản Google không có mã định danh hợp lệ.",
        }), 401)
        return add_no_store_headers(resp)

    # Prefer Google's immutable subject. Email is only used for first-time
    # linking because a managed-domain address can later be reassigned.
    matched_by_google_id = False
    user = db.get_user_by_google_id(google_id)
    if user:
        matched_by_google_id = True
    else:
        user = db.get_user_by_email(email)
        if user and user.get("google_id") and user["google_id"] != google_id:
            resp = make_response(jsonify({
                "success": False,
                "error": "google_account_mismatch",
                "msg": "Email này đã liên kết với một tài khoản Google khác.",
            }), 409)
            return add_no_store_headers(resp)

    if user:
        # Security: Check admin restrictions for Google login
        if user.get("role") == "admin":
            import os
            allow_admin_google = os.getenv("ADMIN_ALLOW_GOOGLE_LOGIN") == "1"
            if not allow_admin_google:
                resp = make_response(jsonify({
                    "success": False,
                    "error": "admin_google_disabled",
                    "msg": "Tài khoản quản trị không hỗ trợ đăng nhập qua Google.",
                }), 403)
                return add_no_store_headers(resp)
            # Even if opt-in, reject auto-linking admin accounts solely by email matching
            if not matched_by_google_id:
                resp = make_response(jsonify({
                    "success": False,
                    "error": "google_link_forbidden",
                    "msg": "Tài khoản quản trị chỉ có thể đăng nhập bằng tài khoản Google đã liên kết xác thực.",
                }), 403)
                return add_no_store_headers(resp)
    if user:
        if not user.get("is_active"):
            resp = make_response(jsonify({
                "success": False,
                "error": "account_inactive",
                "msg": "Tài khoản của bạn tạm thời bị khóa. Vui lòng liên hệ hỗ trợ.",
            }), 403)
            return add_no_store_headers(resp)

        user_id = user["id"]
        try:
            db.update_user_google_info(user_id, google_id=google_id, avatar_url=avatar_url)
        except Exception as exc:
            print(f"Error linking Google user: {type(exc).__name__}")
            resp = make_response(jsonify({
                "success": False,
                "error": "google_account_conflict",
                "msg": "Tài khoản Google này đã liên kết với tài khoản khác.",
            }), 409)
            return add_no_store_headers(resp)
        db.update_user_last_login(user_id)
        display_name = user["display_name"]
        username = user["username"]
        email = user["email"]
        user_avatar = avatar_url or user.get("avatar_url")
    else:
        # Create brand-new user for this Google account
        email_prefix = email.split("@")[0]
        clean_base = re.sub(r"[^a-zA-Z0-9_]", "", email_prefix)[:14]
        if len(clean_base) < 3:
            clean_base = f"user_{clean_base}" if clean_base else "user_gg"
        username = clean_base[:20]
        while db.get_user_by_username(username):
            rand_suffix = f"{secrets.randbelow(9000) + 1000}"
            username = f"{clean_base[:15]}_{rand_suffix}"[:20]

        display_name = name or email_prefix
        if len(display_name) > 50:
            display_name = display_name[:50]

        pwd_hash = generate_password_hash(secrets.token_urlsafe(32))
        try:
            user_id = db.create_user(
                email=email,
                username=username,
                display_name=display_name,
                password_hash=pwd_hash,
                google_id=google_id,
                avatar_url=avatar_url,
            )
        except sqlite3.IntegrityError:
            # A simultaneous request may have created the same Google account
            # after our lookup. Reuse only that exact immutable Google subject.
            concurrent_user = db.get_user_by_google_id(google_id)
            if not concurrent_user or not concurrent_user.get("is_active"):
                resp = make_response(jsonify({
                    "success": False,
                    "error": "google_account_conflict",
                    "msg": "Không thể liên kết tài khoản Google. Vui lòng thử lại.",
                }), 409)
                return add_no_store_headers(resp)
            user_id = concurrent_user["id"]
            email = concurrent_user["email"]
            username = concurrent_user["username"]
            display_name = concurrent_user["display_name"]
            user_avatar = concurrent_user.get("avatar_url")
            db.update_user_last_login(user_id)
        except Exception as exc:
            print(f"Error creating Google user: {type(exc).__name__}")
            resp = make_response(jsonify({
                "success": False,
                "error": "database_error",
                "msg": "Lỗi lưu tài khoản Google vào cơ sở dữ liệu.",
            }), 500)
            return add_no_store_headers(resp)
        else:
            user_avatar = avatar_url

    # Issue token family and access token
    family_id, raw_refresh_token, session_ttl = create_token_family(user_id, remember_me=True)
    access_token = create_access_token(user_id, family_id)

    resp = make_response(jsonify({
        "success": True,
        "msg": "Đăng nhập Google thành công!",
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "user": {
            "id": user_id,
            "email": email,
            "username": username,
            "display_name": display_name,
            "avatar_url": user_avatar,
            "role": user.get("role", "user") if user else "user",
        },
        "csrf_token": get_csrf_token(),
    }))

    set_refresh_cookie(resp, raw_refresh_token, remember_me=True, max_age=session_ttl)
    return add_no_store_headers(resp)


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """Rotate refresh token from HttpOnly cookie and return fresh access token."""
    ip = get_client_ip()
    if is_rate_limited(f"refresh:{ip}", max_requests=30, window_seconds=60):
        resp = make_response(jsonify({
            "success": False,
            "error": "rate_limited",
            "msg": "Bạn đã gửi quá nhiều yêu cầu refresh token.",
        }), 429)
        return add_no_store_headers(resp)

    # CSRF check
    if not validate_csrf():
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF không hợp lệ. Vui lòng tải lại trang.",
        }), 403)
        return add_no_store_headers(resp)

    raw_token = get_refresh_cookie()
    if not raw_token:
        resp = make_response(jsonify({
            "success": False,
            "error": "missing_refresh_token",
            "msg": "Không tìm thấy refresh token trong cookie.",
        }), 401)
        clear_refresh_cookie(resp)
        return add_no_store_headers(resp)

    # Rotate token with atomic transaction & replay detection
    status, new_raw_token, new_access_token, user, family_id, remember_me, remaining_ttl = rotate_refresh_token(raw_token)

    if status == "replay_detected":
        resp = make_response(jsonify({
            "success": False,
            "error": "replay_detected",
            "msg": "Phát hiện hành vi sử dụng lại token cũ. Toàn bộ phiên làm việc đã bị thu hồi vì lý do an toàn.",
        }), 401)
        clear_refresh_cookie(resp)
        return add_no_store_headers(resp)

    if status != "ok":
        resp = make_response(jsonify({
            "success": False,
            "error": status,
            "msg": "Refresh token không hợp lệ hoặc đã hết hạn.",
        }), 401)
        clear_refresh_cookie(resp)
        return add_no_store_headers(resp)

    # Rotation succeeded
    resp = make_response(jsonify({
        "success": True,
        "access_token": new_access_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "display_name": user["display_name"],
            "avatar_url": user.get("avatar_url"),
            "role": user.get("role", "user"),
        },
        "csrf_token": get_csrf_token(),
    }))

    set_refresh_cookie(resp, new_raw_token, remember_me=remember_me, max_age=remaining_ttl if remember_me else None)
    return add_no_store_headers(resp)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Revoke token family, clear refresh cookie, without touching admin session."""
    if not validate_csrf():
        resp = make_response(jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "CSRF không hợp lệ.",
        }), 403)
        return add_no_store_headers(resp)

    family_id_to_revoke = None

    # 1. Prefer reading family_id from refresh token cookie (tamper-proof peppered HMAC in DB)
    raw_token = get_refresh_cookie()
    if raw_token:
        from .token_auth import hash_refresh_token
        rec = db.get_refresh_token_by_hash(hash_refresh_token(raw_token))
        if rec:
            family_id_to_revoke = rec.get("family_id")

    # 2. If cookie was absent, try reading family_id from verified Bearer token (allowing expired tokens)
    if not family_id_to_revoke:
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            try:
                from .token_auth import JWT_AUDIENCE, JWT_ISSUER, JWT_SECRET
                # Strictly verify signature and issuer/audience/type using HS256, disabling only expiration check
                payload = jwt.decode(
                    token,
                    JWT_SECRET,
                    algorithms=["HS256"],
                    issuer=JWT_ISSUER,
                    audience=JWT_AUDIENCE,
                    options={
                        "require": ["sub", "sid", "type"],
                        "verify_exp": False,
                        "verify_iat": False,
                        "verify_iss": True,
                        "verify_aud": True,
                    },
                )
                if payload.get("type") == "access":
                    family_id_to_revoke = payload.get("sid")
            except jwt.InvalidTokenError:
                # Untrusted or forged token - reject and do not use its sid
                pass
            except Exception:
                pass

    # Revoke family in DB if resolved
    if family_id_to_revoke:
        revoke_token_family(family_id_to_revoke, "user_logout")

    resp = make_response(jsonify({
        "success": True,
        "msg": "Đã đăng xuất thành công.",
        "csrf_token": get_csrf_token(),
    }))

    clear_refresh_cookie(resp)
    return add_no_store_headers(resp)


@auth_bp.route("/me", methods=["GET"])
@access_required
def me():
    """Returns the authenticated customer profile from g.current_user (Bearer JWT)."""
    from flask import g
    user = g.current_user
    resp = make_response(jsonify({
        "success": True,
        "authenticated": True,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "display_name": user["display_name"],
            "avatar_url": user.get("avatar_url"),
            "created_at": user.get("created_at"),
            "role": user.get("role", "user"),
        },
        "csrf_token": get_csrf_token(),
    }))
    return add_no_store_headers(resp)
