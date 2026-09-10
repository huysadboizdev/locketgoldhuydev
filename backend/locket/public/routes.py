import hashlib
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

from flask import (
    current_app, g, jsonify, make_response, redirect, render_template, request, send_file, session,
)

from .. import db, payment_service, site_settings
from ..token_auth import access_required
from ..user_auth import validate_csrf
from . import bp


def _mobileconfig_path():
    env_path = os.getenv("MOBILECONFIG_PATH")
    if env_path:
        return env_path
    vps_path = "/var/lib/locket-gold/downloads/locket.mobileconfig"
    if os.path.exists(vps_path):
        return vps_path
    static_dir = os.path.join(current_app.root_path, "static")
    return os.path.join(static_dir, "locket.mobileconfig")


def _apk_path():
    env_path = os.getenv("ANDROID_APK_PATH")
    if env_path:
        return env_path
    vps_path = "/var/lib/locket-gold/downloads/Locket_v1.200.0-gocmod.com.apk"
    if os.path.exists(vps_path):
        return vps_path
    root_dir = os.path.abspath(os.path.join(current_app.root_path, "..", ".."))
    root_candidate = os.path.join(root_dir, "Locket_v1.200.0-gocmod.com.apk")
    if os.path.exists(root_candidate):
        return root_candidate
    backend_candidate = os.path.abspath(os.path.join(current_app.root_path, "..", "Locket_v1.200.0-gocmod.com.apk"))
    if os.path.exists(backend_candidate):
        return backend_candidate
    return os.path.join(current_app.root_path, "static", "Locket_v1.200.0-gocmod.com.apk")


def _external_apk_url():
    """Return a validated, operator-controlled external APK URL or None."""
    raw = (os.getenv("ANDROID_APK_DOWNLOAD_URL") or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
        allowed = {
            item.strip().lower()
            for item in (os.getenv("ANDROID_APK_ALLOWED_HOSTS") or "mediafire.com,www.mediafire.com").split(",")
            if item.strip()
        }
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname.lower() not in allowed
            or parsed.username
            or parsed.password
        ):
            return None
        return raw
    except (TypeError, ValueError):
        return None


def _normalize_zalo(value):
    raw = str(value or "").strip()
    compact = re.sub(r"[\s.()\-]", "", raw)
    if not re.fullmatch(r"\+?\d{9,15}", compact):
        return None
    return compact


def _normalize_facebook_url(value):
    raw = str(value or "").strip()
    if not raw or len(raw) > 500:
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    allowed_hosts = {"facebook.com", "www.facebook.com", "m.facebook.com"}
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() not in allowed_hosts
        or parsed.username
        or parsed.password
        or not parsed.path
        or parsed.path == "/"
    ):
        return None
    return urlunparse(("https", (parsed.hostname or "").lower(), parsed.path, "", parsed.query, ""))


def _validate_fulfillment_payload(plan, platform, body):
    try:
        mode = db.resolve_plan_fulfillment(plan, platform)
    except ValueError as exc:
        return None, None, None, None, (jsonify({
            "success": False,
            "error": str(exc),
            "msg": "Gói dịch vụ không hỗ trợ luồng xử lý đã chọn.",
        }), 400)

    username = (body.get("username") or body.get("target_username") or "").strip()
    zalo = None
    facebook = None
    if mode == "auto_activation":
        if not username:
            return None, None, None, None, (jsonify({
                "success": False, "error": "username_required",
                "msg": "Vui lòng nhập tài khoản Locket.",
            }), 400)
    elif mode == "manual_contact":
        zalo = _normalize_zalo(body.get("contact_zalo"))
        if not zalo:
            return None, None, None, None, (jsonify({
                "success": False, "error": "invalid_contact_zalo",
                "msg": "Vui lòng nhập số điện thoại Zalo hợp lệ.",
            }), 400)
        facebook = _normalize_facebook_url(body.get("contact_facebook"))
        if not facebook:
            return None, None, None, None, (jsonify({
                "success": False, "error": "invalid_contact_facebook",
                "msg": "Vui lòng nhập liên kết Facebook HTTPS hợp lệ.",
            }), 400)
        username = ""
    elif mode == "apk_download":
        username = ""
    return mode, username, zalo, facebook, None


def _mask_username(name):
    if not name:
        return "—"
    s = str(name)
    return s[0] + "*" * min(4, max(0, len(s) - 1))


def _no_accounts_response():
    return jsonify({
        "success": False,
        "msg": "Chưa có tài khoản Locket nào. Admin hãy thêm qua /admin.",
    }), 503


def _is_request_admin():
    """Check whether the current request is from an authenticated admin via Bearer token or legacy session."""
    if session.get("admin"):
        return True
    user = getattr(g, "current_user", None)
    if user and user.get("role") == "admin":
        return True
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        try:
            from ..token_auth import decode_access_token
            payload = decode_access_token(token)
            if payload.get("type") == "access":
                user_id = int(payload.get("sub"))
                u = db.get_user_by_id(user_id)
                if u and u.get("role") == "admin" and u.get("is_active"):
                    return True
        except Exception:
            pass
    return False


def _maintenance_active():
    m = site_settings.get_maintenance()
    if not m.get("enabled"):
        return None
    if m.get("allow_admin", True) and _is_request_admin():
        return None
    return m


def _maintenance_json_response():
    m = _maintenance_active()
    if m is None:
        return None
    return jsonify({
        "success": False,
        "maintenance": True,
        "msg": m.get("message") or "Hệ thống đang bảo trì.",
        "end_at": m.get("end_at") or None,
    }), 503


GOLD_BLOCK_MSG = (
    "Tài khoản đã mua/dùng Gold — gói này chỉ cho người chưa từng đăng ký. "
    "Vui lòng đổi gói mới."
)
GOLD_UNAVAILABLE_MSG = (
    "Không kiểm tra được Gold lúc này. Vui lòng đổi gói mới."
)


def _resolve_locket_uid_for_check(raw):
    from ..user_resolver import resolve_locket_uid
    uid = resolve_locket_uid(raw)
    if uid:
        return uid
    try:
        info = current_app.queue_manager.call_round_robin("getUserByUsername", raw)
        uid = (info.get("result", {}).get("data") or {}).get("uid")
    except Exception:
        uid = None
    return uid


def _live_gold_status(uid):
    """Read-only live Gold check. Raises on failure (callers fail closed)."""
    from ..queue_manager import SUBSCRIPTION_IDS
    slot = current_app.rotator.list_ids()[0]
    api = current_app.rotator.get(slot)
    sub = api.getSubscriber(uid)
    ent = (sub.get("subscriber", {}).get("entitlements", {}).get("Gold") or {})
    pid = ent.get("product_identifier")
    expires = ent.get("expires_date")
    is_gold = False
    if pid in SUBSCRIPTION_IDS:
        is_gold = True
    elif expires:
        try:
            exp_dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            is_gold = exp_dt > datetime.now(timezone.utc)
        except Exception:
            is_gold = True
    return is_gold, expires, pid


def _gold_check(raw_username):
    """Shared new-user-only precheck. Never uses restorePurchase to check."""
    norm = db.normalize_locket_username(raw_username)
    already, order = db.has_prior_activation_for_locket_username(norm)
    uid = _resolve_locket_uid_for_check(raw_username)
    is_gold, expires, pid = False, None, None
    check = "history"
    if uid:
        try:
            is_gold, expires, pid = _live_gold_status(uid)
            check = "live"
        except Exception:
            return {
                "already_registered": bool(already),
                "order_status": (order or {}).get("status"),
                "uid": uid, "is_gold": False,
                "expires_date": None, "product_id": None,
                "blocked": True, "check": "timeout",
                "error": "gold_check_unavailable",
            }
    return {
        "already_registered": bool(already),
        "order_status": (order or {}).get("status"),
        "uid": uid, "is_gold": is_gold,
        "expires_date": expires, "product_id": pid,
        "blocked": bool(is_gold or already), "check": check,
        "error": None,
    }


def _gold_block_error(raw_username):
    """Return None if purchase may proceed, else (error_code, msg). Fail-closed."""
    result = _gold_check(raw_username)
    if result["error"] == "gold_check_unavailable":
        return ("gold_check_unavailable", GOLD_UNAVAILABLE_MSG)
    if result["is_gold"]:
        return ("already_gold_live", GOLD_BLOCK_MSG)
    if result["already_registered"]:
        return ("already_registered", GOLD_BLOCK_MSG)
    return None


@bp.route("/")
def index():
    m = _maintenance_active()
    if m is not None:
        return render_template("maintenance.html", settings=m), 503
    theme = site_settings.get_theme().get("name", "gold")
    layout = site_settings.get_layout().get("name", "stacked")
    return render_template("index.html", theme=theme, layout=layout)


@bp.route("/api/mobileconfig/download-ticket", methods=["POST"])
@access_required
def mobileconfig_create_ticket():
    """Generate a single-use download ticket valid for 60 seconds for downloading mobileconfig.
    Requires completed iOS queue request or activation order owned by user.
    """
    data = request.json if request.is_json and isinstance(request.json, dict) else {}
    client_id = (data.get("client_id") or "").strip()
    act_order_id = data.get("activation_order_id")

    if not client_id and not act_order_id:
        return jsonify({
            "success": False,
            "error": "client_id_required",
            "msg": "Cần cung cấp client_id hoặc activation_order_id của yêu cầu nâng cấp đã hoàn thành.",
        }), 400

    user_id = g.current_user["id"]
    conn = db.get_conn()

    if act_order_id:
        act_order = db.get_activation_order_by_id(act_order_id, user_id=user_id)
        if not act_order:
            return jsonify({
                "success": False,
                "error": "order_not_found",
                "msg": "Không tìm thấy yêu cầu nâng cấp phù hợp hoặc bạn không có quyền truy cập.",
            }), 403
        if act_order["status"] != "completed":
            return jsonify({
                "success": False,
                "error": "order_not_completed",
                "msg": "Yêu cầu nâng cấp chưa hoàn thành. Không thể cấp quyền tải cấu hình.",
            }), 403
        if act_order["platform"] != "ios":
            return jsonify({
                "success": False,
                "error": "platform_mismatch",
                "msg": "Cấu hình DNS chỉ áp dụng cho thiết bị iOS.",
            }), 403
        client_id = act_order.get("queue_client_id") or client_id
    else:
        order = conn.execute(
            "SELECT * FROM queue_requests WHERE client_id = ?", (client_id,)
        ).fetchone()

        if not order or order["user_id"] != user_id:
            return jsonify({
                "success": False,
                "error": "order_not_found",
                "msg": "Không tìm thấy yêu cầu nâng cấp phù hợp hoặc bạn không có quyền truy cập.",
            }), 403

        if order["status"] != "completed":
            return jsonify({
                "success": False,
                "error": "order_not_completed",
                "msg": "Yêu cầu nâng cấp chưa hoàn thành. Không thể cấp quyền tải cấu hình.",
            }), 403

        if order["platform"] != "ios":
            return jsonify({
                "success": False,
                "error": "platform_mismatch",
                "msg": "Cấu hình DNS chỉ áp dụng cho thiết bị iOS.",
            }), 403

        act_order_id = order["activation_order_id"] if "activation_order_id" in order.keys() else None

    raw_ticket = secrets.token_urlsafe(32)
    ticket_hash = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
    expires_at = time.time() + 60.0
    conn.execute(
        """INSERT INTO download_tickets
           (ticket_hash, user_id, client_id, artifact_type, created_at, expires_at, activation_order_id)
           VALUES (?, ?, ?, 'mobileconfig', ?, ?, ?)""",
        (ticket_hash, user_id, client_id, time.time(), expires_at, act_order_id),
    )
    download_url = f"/api/mobileconfig?ticket={raw_ticket}"
    return jsonify({
        "success": True,
        "ticket": raw_ticket,
        "download_url": download_url,
        "expires_in": 60,
    })


@bp.route("/api/mobileconfig", methods=["GET"])
def mobileconfig_download():
    """Serve the mobileconfig with the exact headers iOS needs to trigger the
    'Install Profile' system dialog (instead of saving as a regular download).
    Requires a valid single-use ticket or admin session.
    """
    raw_ticket = (request.args.get("ticket") or "").strip()
    is_admin = _is_request_admin()

    if not is_admin:
        if not raw_ticket:
            return jsonify({
                "success": False,
                "error": "missing_ticket",
                "msg": "Cần có download ticket để tải cấu hình. Vui lòng tạo ticket trước.",
            }), 403

        ticket_hash = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
        ticket_row = db.claim_download_ticket(ticket_hash, expected_artifact_type="mobileconfig")
        if not ticket_row:
            return jsonify({
                "success": False,
                "error": "invalid_ticket",
                "msg": "Download ticket không hợp lệ, đã hết hạn hoặc đã được sử dụng.",
            }), 403

    if os.getenv("ENABLE_ACCEL_REDIRECT") == "1":
        resp = make_response("")
        resp.headers["X-Accel-Redirect"] = "/protected_downloads/locket.mobileconfig"
        resp.headers["Content-Type"] = "application/x-apple-aspen-config"
        resp.headers["Content-Disposition"] = 'inline; filename="locket.mobileconfig"'
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp

    path = _mobileconfig_path()
    if not os.path.exists(path):
        return jsonify({"success": False, "msg": "Profile not configured"}), 404
    resp = send_file(
        path,
        mimetype="application/x-apple-aspen-config",
        as_attachment=False,
        download_name="locket.mobileconfig",
    )
    resp.headers["Content-Disposition"] = 'inline; filename="locket.mobileconfig"'
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@bp.route("/api/apk/download-ticket", methods=["POST"])
@access_required
def apk_create_ticket():
    """Generate a single-use download ticket valid for 300 seconds for downloading Android APK.
    Requires completed Android queue request or activation order owned by user.
    """
    data = request.json if request.is_json and isinstance(request.json, dict) else {}
    client_id = (data.get("client_id") or "").strip()
    act_order_id = data.get("activation_order_id")

    if not client_id and not act_order_id:
        return jsonify({
            "success": False,
            "error": "client_id_required",
            "msg": "Cần cung cấp client_id hoặc activation_order_id của yêu cầu nâng cấp đã hoàn thành.",
        }), 400

    user_id = g.current_user["id"]
    conn = db.get_conn()

    if act_order_id:
        act_order = db.get_activation_order_by_id(act_order_id, user_id=user_id)
        if not act_order:
            return jsonify({
                "success": False,
                "error": "order_not_found",
                "msg": "Không tìm thấy yêu cầu nâng cấp phù hợp hoặc bạn không có quyền truy cập.",
            }), 403
        if act_order["status"] != "completed":
            return jsonify({
                "success": False,
                "error": "order_not_completed",
                "msg": "Yêu cầu nâng cấp chưa hoàn thành. Không thể cấp quyền tải file APK.",
            }), 403
        if act_order["platform"] != "android":
            return jsonify({
                "success": False,
                "error": "platform_mismatch",
                "msg": "File cài đặt APK chỉ áp dụng cho thiết bị Android.",
            }), 403
        if act_order.get("fulfillment_mode_snapshot") != "apk_download":
            return jsonify({
                "success": False,
                "error": "fulfillment_mismatch",
                "msg": "Đơn này không thuộc luồng cấp file APK.",
            }), 403
        client_id = act_order.get("queue_client_id") or client_id
    else:
        order = conn.execute(
            "SELECT * FROM queue_requests WHERE client_id = ?", (client_id,)
        ).fetchone()

        if not order or order["user_id"] != user_id:
            return jsonify({
                "success": False,
                "error": "order_not_found",
                "msg": "Không tìm thấy yêu cầu nâng cấp phù hợp hoặc bạn không có quyền truy cập.",
            }), 403

        if order["status"] != "completed":
            return jsonify({
                "success": False,
                "error": "order_not_completed",
                "msg": "Yêu cầu nâng cấp chưa hoàn thành. Không thể cấp quyền tải file APK.",
            }), 403

        if order["platform"] != "android":
            return jsonify({
                "success": False,
                "error": "platform_mismatch",
                "msg": "File cài đặt APK chỉ áp dụng cho thiết bị Android.",
            }), 403

        act_order_id = order["activation_order_id"] if "activation_order_id" in order.keys() else None
        if not act_order_id:
            return jsonify({
                "success": False,
                "error": "paid_order_required",
                "msg": "Yêu cầu tải APK phải liên kết với một đơn gói Android đã thanh toán.",
            }), 403
        linked_order = db.get_activation_order_by_id(act_order_id, user_id=user_id)
        if not linked_order:
            return jsonify({
                "success": False,
                "error": "order_not_found",
                "msg": "Không tìm thấy đơn gói Android đã thanh toán thuộc tài khoản này.",
            }), 403
        if linked_order.get("status") != "completed":
            return jsonify({
                "success": False,
                "error": "order_not_completed",
                "msg": "Đơn gói Android chưa hoàn thành nên chưa thể tải APK.",
            }), 403
        if (
            linked_order.get("platform") != "android"
            or linked_order.get("fulfillment_mode_snapshot") != "apk_download"
        ):
            return jsonify({
                "success": False,
                "error": "fulfillment_mismatch",
                "msg": "Đơn này không thuộc luồng cấp file APK.",
            }), 403

    raw_ticket = secrets.token_urlsafe(32)
    ticket_hash = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
    expires_at = time.time() + 300.0
    conn.execute(
        """INSERT INTO download_tickets
           (ticket_hash, user_id, client_id, artifact_type, created_at, expires_at, activation_order_id)
           VALUES (?, ?, ?, 'apk', ?, ?, ?)""",
        (ticket_hash, user_id, client_id, time.time(), expires_at, act_order_id),
    )
    download_url = f"/api/apk?ticket={raw_ticket}"
    return jsonify({
        "success": True,
        "ticket": raw_ticket,
        "download_url": download_url,
        "expires_in": 300,
    })


@bp.route("/api/apk", methods=["GET"])
def apk_download():
    """Serve the Android APK securely with single-use ticket or admin session.
    Supports X-Accel-Redirect for production Nginx or send_file for local dev.
    """
    raw_ticket = (request.args.get("ticket") or "").strip()
    is_admin = _is_request_admin()
    ticket_row = None

    if not is_admin:
        if not raw_ticket:
            return jsonify({
                "success": False,
                "error": "missing_ticket",
                "msg": "Cần có download ticket để tải APK. Vui lòng tạo ticket trước.",
            }), 403

        ticket_hash = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
        ticket_row = db.claim_download_ticket(ticket_hash, expected_artifact_type="apk")
        if not ticket_row:
            return jsonify({
                "success": False,
                "error": "invalid_ticket",
                "msg": "Download ticket không hợp lệ, đã hết hạn hoặc đã được sử dụng.",
            }), 403

    if ticket_row and ticket_row.get("activation_order_id"):
        db.get_conn().execute(
            "UPDATE activation_orders SET download_accessed_at = ?, updated_at = ? WHERE id = ?",
            (time.time(), time.time(), ticket_row["activation_order_id"]),
        )

    external_url = None if current_app.config.get("TESTING") else _external_apk_url()
    if external_url:
        resp = redirect(external_url, code=302)
        resp.headers["Cache-Control"] = "private, no-store, max-age=0"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    if os.getenv("ENABLE_ACCEL_REDIRECT") == "1":
        resp = make_response("")
        resp.headers["X-Accel-Redirect"] = "/protected_downloads/Locket_v1.200.0-gocmod.com.apk"
        resp.headers["Content-Type"] = "application/vnd.android.package-archive"
        resp.headers["Content-Disposition"] = 'attachment; filename="Locket_Gold_v1.200.0.apk"'
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp

    apk_path = _apk_path()
    if not os.path.exists(apk_path):
        return jsonify({"success": False, "msg": "File APK không tồn tại trên máy chủ."}), 404

    resp = send_file(
        apk_path,
        mimetype="application/vnd.android.package-archive",
        as_attachment=True,
        download_name="Locket_Gold_v1.200.0.apk",
    )
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@bp.route("/api/site-settings", methods=["GET"])
@bp.route("/api/site/settings", methods=["GET"])
def site_settings_public():
    payload = site_settings.public_view()
    # Whether the current visitor is actually under maintenance (after admin
    # bypass). FE uses this to decide whether to redirect to the maintenance
    # page — `maintenance.enabled` alone would loop admins.
    payload["maintenance_active"] = _maintenance_active() is not None
    return jsonify({"success": True, **payload})


@bp.route("/api/get-user-info", methods=["POST"])
@access_required
def get_user_info():
    blocked = _maintenance_json_response()
    if blocked is not None:
        return blocked
    rotator = current_app.rotator
    qm = current_app.queue_manager
    if rotator is None or rotator.size() == 0:
        return _no_accounts_response()

    data = request.json or {}
    username = data.get("username")
    if not username:
        return jsonify({"success": False, "msg": "Username is required"}), 400

    try:
        print(f"Looking up user: {username}")
        user_data = None
        try:
            account_info = qm.call_round_robin("getUserByUsername", username)
            if account_info and "result" in account_info:
                user_data = account_info.get("result", {}).get("data")
        except Exception as e:
            print(f"call_round_robin getUserByUsername failed: {e}")

        if not user_data:
            from ..user_resolver import resolve_locket_uid
            resolved_uid = resolve_locket_uid(username)
            if resolved_uid:
                clean_name = username.split("/")[-1].split("?")[0]
                user_data = {
                    "uid": resolved_uid,
                    "username": clean_name if len(clean_name) < 25 else "Locket User",
                    "first_name": "Locket",
                    "last_name": "User",
                    "profile_picture_url": "",
                }

        if not user_data:
            return jsonify({"success": False, "msg": "Không tìm thấy thông tin tài khoản Locket. Vui lòng kiểm tra lại."}), 404

        return jsonify({
            "success": True,
            "data": {
                "uid": user_data.get("uid"),
                "username": user_data.get("username"),
                "first_name": user_data.get("first_name", ""),
                "last_name": user_data.get("last_name", ""),
                "profile_picture_url": user_data.get("profile_picture_url", ""),
            },
        })

    except Exception as e:
        print(f"Error in get user info: {e}")
        return jsonify({"success": False, "msg": "Đã xảy ra lỗi khi tìm kiếm tài khoản Locket."}), 500


@bp.route("/api/check-gold", methods=["POST"])
@access_required
def check_gold():
    """New-user-only precheck: history DB + live RevenueCap Gold (read-only)."""
    blocked = _maintenance_json_response()
    if blocked is not None:
        return blocked
    rotator = current_app.rotator
    if rotator is None or rotator.size() == 0:
        return _no_accounts_response()

    data = request.get_json(silent=True) or {}
    raw = (data.get("username") or "").strip()
    if not raw:
        return jsonify({"success": False, "error": "username_required"}), 400

    result = _gold_check(raw)
    if result["error"] == "gold_check_unavailable":
        return jsonify({
            "success": False,
            "error": "gold_check_unavailable",
            "msg": GOLD_UNAVAILABLE_MSG,
            "already_registered": result["already_registered"],
        }), 409
    return jsonify({
        "success": True,
        "uid": result["uid"],
        "is_gold": result["is_gold"],
        "expires_date": result["expires_date"],
        "product_id": result["product_id"],
        "already_registered": result["already_registered"],
        "order_status": result["order_status"],
        "blocked": result["blocked"],
        "check": result["check"],
    })


@bp.route("/api/restore", methods=["POST"])
@access_required
def restore_purchase():
    """Add a request to the queue bound to the logged-in user and platform. Returns client_id for polling."""
    blocked = _maintenance_json_response()
    if blocked is not None:
        return blocked

    rotator = current_app.rotator
    qm = current_app.queue_manager
    if rotator is None or rotator.size() == 0:
        return _no_accounts_response()

    if not request.is_json or not isinstance(request.json, dict):
        return jsonify({"success": False, "error": "invalid_payload", "msg": "Dữ liệu yêu cầu không hợp lệ."}), 400

    data = request.json or {}
    platform = data.get("platform")
    if not platform or platform not in ("ios", "android"):
        return jsonify({
            "success": False,
            "error": "invalid_platform",
            "msg": "Vui lòng chọn nền tảng thiết bị hợp lệ (iOS hoặc Android).",
        }), 400

    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"success": False, "msg": "Username is required"}), 400

    gold_block = _gold_block_error(username)
    if gold_block is not None:
        code, msg = gold_block
        return jsonify({"success": False, "error": code, "msg": msg}), 409

    user_id = g.current_user["id"]

    try:
        client_id = qm.add_to_queue(username, user_id=user_id, platform=platform)
        if client_id is None:
            return jsonify({"success": False, "msg": "Queue is full, please try again later."}), 503

        status = qm.get_status(client_id, user_id=user_id)
        return jsonify({
            "success": True,
            "client_id": client_id,
            "platform": platform,
            "position": status["position"],
            "total_queue": status["total_queue"],
            "estimated_time": status["estimated_time"],
        })
    except Exception as e:
        print(f"Error adding to queue: {e}")
        return jsonify({"success": False, "msg": f"An error occurred: {str(e)}"}), 500


@bp.route("/api/recent-history", methods=["GET"])
def recent_history():
    """Public-safe recent history. Username is masked (a**** style); slot_id
    and error details are stripped. Returns up to 30 newest entries."""
    cutoff = __import__("time").time() - 24 * 3600
    rows = db.get_conn().execute(
        "SELECT username, status, duration, completed_at "
        "FROM recent_log WHERE completed_at >= ? "
        "ORDER BY id DESC LIMIT 30",
        (cutoff,),
    ).fetchall()
    items = []
    for r in rows:
        completed_at = None
        if r["completed_at"] is not None:
            completed_at = datetime.fromtimestamp(
                r["completed_at"], tz=timezone.utc
            ).isoformat()
        items.append({
            "username": _mask_username(r["username"]),
            "status": r["status"],
            "duration": r["duration"],
            "completed_at": completed_at,
        })
    return jsonify({"success": True, "items": items})


@bp.route("/api/mobileconfig/history", methods=["GET"])
def mobileconfig_history_public():
    """Public-safe profile update history. Filenames are stripped (admins only
    see those); we expose action + size + signed flag + timestamp so users
    know when the profile was last refreshed."""
    rows = db.get_conn().execute(
        "SELECT action, size, signed, created_at "
        "FROM mobileconfig_history ORDER BY id DESC LIMIT 10"
    ).fetchall()
    items = [
        {
            "action": r["action"],
            "size": r["size"],
            "signed": bool(r["signed"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return jsonify({"success": True, "items": items})


@bp.route("/api/queue/global-status", methods=["GET"])
def global_queue_status():
    """Aggregate queue stats — no client_id required."""
    return jsonify({"success": True, **current_app.queue_manager.get_global_status()})


@bp.route("/api/queue/status", methods=["POST"])
@access_required
def queue_status():
    """Per-client polling endpoint. Requires access token.
    Validates that client_id belongs to the logged in user.
    """
    data = request.json or {}
    client_id = data.get("client_id")
    if not client_id:
        return jsonify({"success": False, "msg": "client_id is required"}), 400
    user_id = g.current_user["id"]
    conn = db.get_conn()
    row = conn.execute(
        "SELECT user_id FROM queue_requests WHERE client_id = ?", (client_id,)
    ).fetchone()
    if not row or row["user_id"] != user_id:
        return jsonify({
            "success": False,
            "status": "not_found",
            "error": "not_found",
            "msg": "Yêu cầu không tồn tại hoặc không thuộc quyền sở hữu của bạn.",
        }), 404
    return jsonify({"success": True, **current_app.queue_manager.get_status(client_id, user_id=user_id)})


@bp.route("/api/queue/my-active", methods=["GET"])
@access_required
def my_active_queue():
    """Return the current user's active in-flight request if any."""
    user_id = g.current_user["id"]
    conn = db.get_conn()
    row = conn.execute(
        "SELECT client_id, username, status, added_at, platform FROM queue_requests "
        "WHERE user_id = ? AND status IN ('waiting', 'processing') "
        "ORDER BY added_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if not row:
        return jsonify({"success": True, "active": None})
    status = current_app.queue_manager.get_status(row["client_id"], user_id=user_id)
    return jsonify({
        "success": True,
        "active": {
            "client_id": row["client_id"],
            "username": row["username"],
            **status,
            "platform": row["platform"],
        },
    })


# ---- Plans Endpoints ----

@bp.route("/api/plans", methods=["GET"])
def list_plans():
    """Return list of active plans."""
    plans = db.list_active_plans()
    return jsonify({"success": True, "plans": plans})


# ---- Wallet Endpoints ----

@bp.route("/api/wallet", methods=["GET"])
@access_required
def get_wallet():
    """Get current user's coin balance."""
    user_id = g.current_user["id"]
    balance = db.get_wallet_balance(user_id)
    return jsonify({"success": True, "balance_coin": balance})


@bp.route("/api/wallet/transactions", methods=["GET"])
@access_required
def get_wallet_txs():
    """Get paginated ledger of wallet transactions."""
    user_id = g.current_user["id"]
    limit = request.args.get("limit", 20)
    offset = request.args.get("offset", 0)
    data = db.get_wallet_transactions(user_id, limit=limit, offset=offset)
    return jsonify({"success": True, **data})


# ---- Payment Orders Endpoints ----

_renew_rate_limits = {}

def reset_renew_rate_limits():
    _renew_rate_limits.clear()

def _check_renew_rate_limit(user_id: int) -> bool:
    now = time.time()
    win = int(now // 60)
    key = (user_id, win)
    count = _renew_rate_limits.get(key, 0)
    if count >= 5:
        return False
    _renew_rate_limits[key] = count + 1
    if len(_renew_rate_limits) > 500:
        cutoff = win - 2
        for k in list(_renew_rate_limits.keys()):
            if k[1] < cutoff:
                _renew_rate_limits.pop(k, None)
    return True


@bp.route("/api/payments/topup", methods=["POST"])
@access_required
def create_topup_payment():
    """Create a pending VietQR payment order for wallet top-up."""
    if not validate_csrf():
        return jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF token không hợp lệ. Vui lòng tải lại trang.",
        }), 403
    if not request.is_json or not isinstance(request.json, dict):
        return jsonify({"success": False, "error": "invalid_payload", "msg": "Dữ liệu yêu cầu không hợp lệ."}), 400
    body = request.json or {}
    raw_amount = body.get("amount_vnd")
    if raw_amount is None and "amount_coin" in body:
        try:
            c = int(body["amount_coin"])
            raw_amount = c * 1000
        except (TypeError, ValueError):
            raw_amount = None
    try:
        amount_vnd = int(raw_amount)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "invalid_amount", "msg": "Số tiền nạp phải là số nguyên VNĐ."}), 400

    if amount_vnd <= 0 or amount_vnd % 1000 != 0:
        return jsonify({"success": False, "error": "invalid_amount", "msg": "Số tiền nạp phải là bội số của 1.000 VNĐ."}), 400

    user_id = g.current_user["id"]
    idempotency_key = str(body.get("idempotency_key") or "").strip()
    if len(idempotency_key) > 200:
        return jsonify({
            "success": False,
            "error": "invalid_idempotency_key",
            "msg": "Khóa chống trùng giao dịch không hợp lệ.",
        }), 400

    # Idempotency check: same user and idempotency key
    if idempotency_key:
        existing = db.get_payment_order_by_idempotency(user_id, idempotency_key)
        if existing:
            if existing["purpose"] == "wallet_topup" and existing["amount_vnd"] == amount_vnd:
                now = time.time()
                transfer_code = existing.get("transfer_code") or existing["payment_code"]
                qr_url = existing.get("qr_payload") or payment_service.build_vietqr_url(existing["amount_vnd"], transfer_code)
                return jsonify({
                    "success": True,
                    "payment_id": existing["id"],
                    "payment_code": existing["payment_code"],
                    "payment_ref": existing["payment_code"],
                    "transfer_code": transfer_code,
                    "purpose": "wallet_topup",
                    "amount_vnd": existing["amount_vnd"],
                    "amount_coin": existing["coin_amount"],
                    "coin_amount": existing["coin_amount"],
                    "qr_url": qr_url,
                    "status": existing["status"],
                    "created_at": existing["created_at"],
                    "expires_at": existing["expires_at"],
                    "expires_in": max(0, int(existing["expires_at"] - now)),
                    "server_time": now,
                    "bank_config": payment_service.get_bank_config(),
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "idempotency_conflict",
                    "msg": "Khóa xử lý trùng lặp nhưng nội dung yêu cầu khác nhau.",
                }), 409

    conn = db.get_conn()
    now = time.time()
    ttl = payment_service.get_payment_config()["ttl"]
    key_to_store = idempotency_key or f"topup_{user_id}_{secrets.token_hex(8)}"
    idempotency_hash = hashlib.sha256(f"topup:{amount_vnd}".encode()).hexdigest()

    try:
        conn.execute("BEGIN IMMEDIATE")
        payment_code = payment_service.generate_internal_payment_code("PAY")
        transfer_code = payment_service.allocate_transfer_code(conn, now)
        qr_url = payment_service.build_vietqr_url(amount_vnd, transfer_code)
        bank_cfg = payment_service.get_bank_config()

        cursor = conn.execute(
            """INSERT INTO payment_orders
               (payment_code, transfer_code, idempotency_hash, user_id, purpose, plan_id,
                amount_vnd, coin_amount, provider, status, qr_payload, idempotency_key,
                expires_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'wallet_topup', NULL, ?, ?, 'vietqr', 'pending', ?, ?, ?, ?, ?)""",
            (
                payment_code,
                transfer_code,
                idempotency_hash,
                user_id,
                amount_vnd,
                amount_vnd // 1000,
                qr_url,
                key_to_store,
                now + ttl,
                now,
                now,
            ),
        )
        pay_id = cursor.lastrowid
        conn.execute("COMMIT")
    except payment_service.PaymentCodePoolExhaustedError:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return jsonify({
            "success": False,
            "error": "payment_code_pool_exhausted",
            "msg": "Hệ thống đang quá tải mã chuyển khoản. Vui lòng thử lại sau ít phút.",
        }), 503
    except sqlite3.IntegrityError:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        if idempotency_key:
            existing = db.get_payment_order_by_idempotency(user_id, idempotency_key)
            if existing and existing["purpose"] == "wallet_topup" and existing["amount_vnd"] == amount_vnd:
                now = time.time()
                transfer_code = existing.get("transfer_code") or existing["payment_code"]
                qr_url = existing.get("qr_payload") or payment_service.build_vietqr_url(existing["amount_vnd"], transfer_code)
                return jsonify({
                    "success": True,
                    "payment_id": existing["id"],
                    "payment_code": existing["payment_code"],
                    "payment_ref": existing["payment_code"],
                    "transfer_code": transfer_code,
                    "purpose": "wallet_topup",
                    "amount_vnd": existing["amount_vnd"],
                    "amount_coin": existing["coin_amount"],
                    "coin_amount": existing["coin_amount"],
                    "qr_url": qr_url,
                    "status": existing["status"],
                    "created_at": existing["created_at"],
                    "expires_at": existing["expires_at"],
                    "expires_in": max(0, int(existing["expires_at"] - now)),
                    "server_time": now,
                    "bank_config": payment_service.get_bank_config(),
                })
            return jsonify({
                "success": False,
                "error": "idempotency_conflict",
                "msg": "Khóa xử lý trùng lặp nhưng nội dung yêu cầu khác nhau.",
            }), 409
        raise

    coin_amount = amount_vnd // 1000
    return jsonify({
        "success": True,
        "payment_id": pay_id,
        "payment_code": payment_code,
        "payment_ref": payment_code,
        "transfer_code": transfer_code,
        "purpose": "wallet_topup",
        "amount_vnd": amount_vnd,
        "amount_coin": coin_amount,
        "coin_amount": coin_amount,
        "qr_url": qr_url,
        "status": "pending",
        "created_at": now,
        "expires_at": now + ttl,
        "expires_in": ttl,
        "server_time": now,
        "bank_config": bank_cfg,
    })


@bp.route("/api/payments/plan", methods=["POST"])
@access_required
def create_plan_payment():
    """Create a pending VietQR payment order directly for a plan purchase."""
    if not validate_csrf():
        return jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF token không hợp lệ. Vui lòng tải lại trang.",
        }), 403
    if not request.is_json or not isinstance(request.json, dict):
        return jsonify({"success": False, "error": "invalid_payload", "msg": "Dữ liệu yêu cầu không hợp lệ."}), 400
    body = request.json or {}
    plan_id = body.get("plan_id")
    platform = (body.get("platform") or "").strip().lower()

    if not plan_id:
        return jsonify({"success": False, "error": "plan_id_required", "msg": "Vui lòng chọn gói dịch vụ."}), 400
    if platform not in ("ios", "android"):
        return jsonify({"success": False, "error": "invalid_platform", "msg": "Vui lòng chọn nền tảng hợp lệ (ios hoặc android)."}), 400
    plan = db.get_plan_by_id(plan_id, public=False)
    if not plan or not plan["is_active"]:
        return jsonify({"success": False, "error": "plan_unavailable", "msg": "Gói dịch vụ không khả dụng hoặc đã bị ẩn."}), 400
    if plan.get("inventory_status") == "out_of_stock":
        return jsonify({"success": False, "error": "out_of_stock", "msg": "Gói dịch vụ tạm hết hàng."}), 400
    if plan["supported_platforms"] != "all" and plan["supported_platforms"] != platform:
        return jsonify({"success": False, "error": "platform_not_supported", "msg": f"Gói này chỉ hỗ trợ {plan['supported_platforms']}."}), 400

    mode, username, contact_zalo, contact_facebook, validation_error = _validate_fulfillment_payload(
        plan, platform, body
    )
    if validation_error:
        return validation_error

    if username:
        gold_block = _gold_block_error(username)
        if gold_block is not None:
            code, msg = gold_block
            return jsonify({"success": False, "error": code, "msg": msg}), 409

    user_id = g.current_user["id"]
    idempotency_key = str(body.get("idempotency_key") or "").strip()
    if len(idempotency_key) > 200:
        return jsonify({
            "success": False,
            "error": "invalid_idempotency_key",
            "msg": "Khóa chống trùng giao dịch không hợp lệ.",
        }), 400

    raw_coupon_code = str(body.get("coupon_code") or "").strip()
    coupon_code = ""
    if raw_coupon_code:
        from .. import coupon_service
        try:
            coupon_code = coupon_service.normalize_code(raw_coupon_code)
        except ValueError as exc:
            return jsonify({
                "success": False,
                "error": "invalid_code_format",
                "msg": str(exc),
            }), 400

    # Idempotency check
    if idempotency_key:
        existing = db.get_payment_order_by_idempotency(user_id, idempotency_key)
        if existing:
            if (existing["purpose"] == "plan_purchase"
                    and existing["plan_id"] == plan_id
                    and (existing.get("coupon_code_snapshot") or "") == coupon_code):
                conn = db.get_conn()
                act_row = conn.execute("SELECT * FROM activation_orders WHERE payment_order_id = ?", (existing["id"],)).fetchone()
                if (act_row and act_row["platform"] == platform
                        and act_row["locket_username"] == username
                        and act_row["fulfillment_mode_snapshot"] == mode
                        and (act_row["contact_zalo"] or "") == (contact_zalo or "")
                        and (act_row["contact_facebook"] or "") == (contact_facebook or "")):
                    now = time.time()
                    transfer_code = existing.get("transfer_code") or existing["payment_code"]
                    qr_url = existing.get("qr_payload") or payment_service.build_vietqr_url(existing["amount_vnd"], transfer_code)
                    return jsonify({
                        "success": True,
                        "payment_id": existing["id"],
                        "payment_code": existing["payment_code"],
                        "payment_ref": existing["payment_code"],
                        "transfer_code": transfer_code,
                        "activation_order_id": act_row["id"],
                        "fulfillment_mode": mode,
                        "purpose": "plan_purchase",
                        "amount_vnd": existing["amount_vnd"],
                        "coin_amount": existing["coin_amount"],
                        "qr_url": qr_url,
                        "status": existing["status"],
                        "created_at": existing["created_at"],
                        "expires_at": existing["expires_at"],
                        "expires_in": max(0, int(existing["expires_at"] - now)),
                        "server_time": now,
                        "bank_config": payment_service.get_bank_config(),
                    })
            return jsonify({
                "success": False,
                "error": "idempotency_conflict",
                "msg": "Khóa xử lý trùng lặp nhưng nội dung yêu cầu khác nhau.",
            }), 409

    conn = db.get_conn()
    now = time.time()
    ttl = payment_service.get_payment_config()["ttl"]
    key_to_store = idempotency_key or f"planpay_{user_id}_{secrets.token_hex(8)}"
    idempotency_hash = hashlib.sha256(
        f"plan:{plan_id}:{platform}:{mode}:{username}:{contact_zalo or ''}:{contact_facebook or ''}:{coupon_code}".encode()
    ).hexdigest()

    try:
        conn.execute("BEGIN IMMEDIATE")

        coupon_info = None
        quote = None
        if coupon_code:
            from .. import coupon_service
            is_valid, c_dict, q_dict, err_code, err_msg = coupon_service.validate_and_quote_coupon(
                conn, coupon_code, plan_id, user_id, now=now
            )
            if not is_valid:
                conn.execute("ROLLBACK")
                return jsonify({"success": False, "error": err_code, "msg": err_msg}), 400
            coupon_info = c_dict
            quote = q_dict

        amount_vnd = quote["final_vnd"] if quote else plan["price_vnd"]
        coin_amount = quote["final_coin"] if quote else plan["price_coin"]
        orig_vnd = quote["original_vnd"] if quote else plan["price_vnd"]
        orig_coin = quote["original_coin"] if quote else plan["price_coin"]
        disc_vnd = quote["discount_vnd"] if quote else 0
        disc_coin = quote["discount_coin"] if quote else 0
        coupon_id = coupon_info["id"] if coupon_info else None
        coupon_code_snapshot = coupon_info["code"] if coupon_info else None

        payment_code = payment_service.generate_internal_payment_code("PAY")
        transfer_code = payment_service.allocate_transfer_code(conn, now)
        qr_url = payment_service.build_vietqr_url(amount_vnd, transfer_code)
        bank_cfg = payment_service.get_bank_config()

        cursor = conn.execute(
            """INSERT INTO payment_orders
               (payment_code, transfer_code, idempotency_hash, user_id, purpose, plan_id,
                amount_vnd, coin_amount, provider, status, qr_payload, idempotency_key,
                expires_at, created_at, updated_at,
                original_price_vnd_snapshot, discount_vnd_snapshot, coupon_id, coupon_code_snapshot)
               VALUES (?, ?, ?, ?, 'plan_purchase', ?, ?, ?, 'vietqr', 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payment_code,
                transfer_code,
                idempotency_hash,
                user_id,
                plan_id,
                amount_vnd,
                coin_amount,
                qr_url,
                key_to_store,
                now + ttl,
                now,
                now,
                orig_vnd,
                disc_vnd,
                coupon_id,
                coupon_code_snapshot,
            ),
        )
        pay_id = cursor.lastrowid

        act_cursor = conn.execute(
            """INSERT INTO activation_orders
               (user_id, plan_id, plan_name_snapshot, product_id_snapshot, duration_days_snapshot,
                price_vnd_snapshot, price_coin_snapshot, payment_method, payment_order_id,
                platform, locket_username, fulfillment_mode_snapshot, contact_zalo,
                contact_facebook, status, created_at, updated_at,
                original_price_vnd_snapshot, original_price_coin_snapshot,
                discount_vnd_snapshot, discount_coin_snapshot, coupon_id, coupon_code_snapshot)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'qr', ?, ?, ?, ?, ?, ?, 'awaiting_payment', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                plan_id,
                plan["name"],
                plan.get("product_id") or "",
                plan["duration_days"],
                amount_vnd,
                coin_amount,
                pay_id,
                platform,
                username,
                mode,
                contact_zalo,
                contact_facebook,
                now,
                now,
                orig_vnd,
                orig_coin,
                disc_vnd,
                disc_coin,
                coupon_id,
                coupon_code_snapshot,
            ),
        )
        act_id = act_cursor.lastrowid

        if coupon_info:
            from .. import coupon_service
            coupon_service.reserve_coupon_for_payment(
                conn=conn,
                coupon_id=coupon_id,
                user_id=user_id,
                payment_order_id=pay_id,
                activation_order_id=act_id,
                original_vnd=orig_vnd,
                discount_vnd=disc_vnd,
                final_vnd=amount_vnd,
                ttl_seconds=ttl,
                idempotency_key=f"qr_res_{pay_id}",
                now=now,
            )

        conn.execute("COMMIT")
    except payment_service.PaymentCodePoolExhaustedError:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return jsonify({
            "success": False,
            "error": "payment_code_pool_exhausted",
            "msg": "Hệ thống đang quá tải mã chuyển khoản. Vui lòng thử lại sau ít phút.",
        }), 503
    except sqlite3.IntegrityError:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        if idempotency_key:
            existing = db.get_payment_order_by_idempotency(user_id, idempotency_key)
            if (existing and existing["purpose"] == "plan_purchase"
                    and existing["plan_id"] == plan_id
                    and (existing.get("coupon_code_snapshot") or "") == coupon_code):
                act_row = conn.execute("SELECT * FROM activation_orders WHERE payment_order_id = ?", (existing["id"],)).fetchone()
                if (act_row and act_row["platform"] == platform
                        and act_row["locket_username"] == username
                        and act_row["fulfillment_mode_snapshot"] == mode
                        and (act_row["contact_zalo"] or "") == (contact_zalo or "")
                        and (act_row["contact_facebook"] or "") == (contact_facebook or "")):
                    now = time.time()
                    transfer_code = existing.get("transfer_code") or existing["payment_code"]
                    qr_url = existing.get("qr_payload") or payment_service.build_vietqr_url(existing["amount_vnd"], transfer_code)
                    return jsonify({
                        "success": True,
                        "payment_id": existing["id"],
                        "payment_code": existing["payment_code"],
                        "payment_ref": existing["payment_code"],
                        "transfer_code": transfer_code,
                        "activation_order_id": act_row["id"],
                        "fulfillment_mode": mode,
                        "purpose": "plan_purchase",
                        "amount_vnd": existing["amount_vnd"],
                        "coin_amount": existing["coin_amount"],
                        "qr_url": qr_url,
                        "status": existing["status"],
                        "created_at": existing["created_at"],
                        "expires_at": existing["expires_at"],
                        "expires_in": max(0, int(existing["expires_at"] - now)),
                        "server_time": now,
                        "bank_config": payment_service.get_bank_config(),
                    })
            return jsonify({
                "success": False,
                "error": "idempotency_conflict",
                "msg": "Khóa xử lý trùng lặp nhưng nội dung yêu cầu khác nhau.",
            }), 409
        raise

    return jsonify({
        "success": True,
        "payment_id": pay_id,
        "payment_code": payment_code,
        "payment_ref": payment_code,
        "transfer_code": transfer_code,
        "activation_order_id": act_id,
        "fulfillment_mode": mode,
        "purpose": "plan_purchase",
        "amount_vnd": amount_vnd,
        "coin_amount": coin_amount,
        "qr_url": qr_url,
        "status": "pending",
        "created_at": now,
        "expires_at": now + ttl,
        "expires_in": ttl,
        "server_time": now,
        "bank_config": bank_cfg,
    })


@bp.route("/api/payments/<payment_code>", methods=["GET"])
@access_required
def get_payment_status(payment_code):
    """Check status of a payment order."""
    pay = db.get_payment_order_by_code(payment_code)
    if not pay:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy giao dịch."}), 404
    if pay["user_id"] != g.current_user["id"] and not _is_request_admin():
        return jsonify({"success": False, "error": "forbidden", "msg": "Bạn không có quyền xem giao dịch này."}), 403

    now = time.time()
    if pay["status"] == "pending" and pay["expires_at"] < now:
        expire_result, expire_error = db.reject_payment_order_tx(pay["id"], status="expired")
        refreshed_pay = db.get_payment_order_by_id(pay["id"])
        if refreshed_pay:
            pay = refreshed_pay
        if expire_result != "ok" and pay["status"] == "pending":
            current_app.logger.warning(
                "Unable to expire payment %s during status lookup: %s",
                pay["id"],
                expire_error,
            )
            return jsonify({
                "success": False,
                "error": "payment_status_update_failed",
                "msg": "Chưa thể cập nhật trạng thái giao dịch. Vui lòng thử lại.",
            }), 503

    act_info = None
    if pay["purpose"] == "plan_purchase":
        conn = db.get_conn()
        act_row = conn.execute("SELECT * FROM activation_orders WHERE payment_order_id = ?", (pay["id"],)).fetchone()
        if act_row:
            act_info = dict(act_row)

    transfer_code = pay.get("transfer_code") or pay["payment_code"]
    qr_url = pay.get("qr_payload") or payment_service.build_vietqr_url(pay["amount_vnd"], transfer_code)
    bank_cfg = payment_service.get_bank_config()

    pay_data = {
        **pay,
        "payment_ref": pay["payment_code"],
        "transfer_code": transfer_code,
        "qr_url": qr_url,
        "server_time": now,
        "expires_in": max(0, int(pay["expires_at"] - now)),
        "bank_config": bank_cfg,
    }

    return jsonify({
        "success": True,
        "payment": pay_data,
        "activation_order": act_info,
        "server_time": now,
    })


@bp.route("/api/payments/<payment_code>/cancel", methods=["POST"])
@access_required
def cancel_payment(payment_code):
    """Cancel the current user's unpaid QR and release coupon quota atomically."""
    if not validate_csrf():
        return jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF token không hợp lệ. Vui lòng tải lại trang.",
        }), 403

    pay = db.get_payment_order_by_code(payment_code)
    if not pay:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy giao dịch."}), 404
    if pay["user_id"] != g.current_user["id"]:
        return jsonify({"success": False, "error": "forbidden", "msg": "Bạn không có quyền hủy giao dịch này."}), 403

    if pay["status"] in ("cancelled", "expired"):
        return jsonify({"success": True, "payment": pay, "msg": "Giao dịch đã được đóng trước đó."})
    if pay["status"] == "paid":
        return jsonify({"success": False, "error": "already_paid", "msg": "Giao dịch đã được thanh toán, không thể hủy."}), 409
    if pay["status"] != "pending":
        return jsonify({"success": False, "error": "invalid_status", "msg": "Giao dịch đang được đối soát và không thể tự hủy."}), 409

    status, result = db.reject_payment_order_tx(pay["id"], status="cancelled")
    if status != "ok":
        return jsonify({"success": False, "error": "cancel_failed", "msg": str(result)}), 409
    return jsonify({"success": True, "payment": result, "msg": "Đã hủy mã QR và hoàn lại lượt mã giảm giá."})


@bp.route("/api/payments/<payment_code>/renew", methods=["POST"])
@access_required
def renew_payment(payment_code):
    """Renew an expired or cancelled payment order by issuing fresh transfer code and QR."""
    if not validate_csrf():
        return jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF token không hợp lệ. Vui lòng tải lại trang.",
        }), 403

    user_id = g.current_user["id"]
    if not _check_renew_rate_limit(user_id):
        return jsonify({"success": False, "error": "rate_limited", "msg": "Bạn đang thao tác quá nhanh. Vui lòng thử lại sau 1 phút."}), 429

    pay = db.get_payment_order_by_code(payment_code)
    if not pay:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy giao dịch."}), 404
    if pay["user_id"] != user_id and not _is_request_admin():
        return jsonify({"success": False, "error": "forbidden", "msg": "Bạn không có quyền thao tác trên đơn này."}), 403

    def _renew_success_response(payment, message="Đã tạo mã thanh toán mới thành công."):
        response_now = time.time()
        transfer = payment.get("transfer_code") or payment["payment_code"]
        qr_url = payment.get("qr_payload") or payment_service.build_vietqr_url(
            payment["amount_vnd"], transfer
        )
        activation = db.get_activation_order_by_payment_code(payment["payment_code"])
        enriched = {
            **payment,
            "payment_ref": payment["payment_code"],
            "transfer_code": transfer,
            "qr_url": qr_url,
            "server_time": response_now,
            "expires_in": max(0, int(payment["expires_at"] - response_now)),
            "bank_config": payment_service.get_bank_config(),
        }
        return jsonify({
            "success": True,
            "payment": enriched,
            "payment_id": payment["id"],
            "payment_code": payment["payment_code"],
            "payment_ref": payment["payment_code"],
            "transfer_code": transfer,
            "amount_vnd": payment["amount_vnd"],
            "amount_coin": payment["coin_amount"],
            "coin_amount": payment["coin_amount"],
            "qr_url": qr_url,
            "status": payment["status"],
            "created_at": payment["created_at"],
            "expires_at": payment["expires_at"],
            "expires_in": enriched["expires_in"],
            "server_time": response_now,
            "bank_config": enriched["bank_config"],
            "activation_order": activation,
            "msg": message,
        })

    existing_renewal_row = db.get_conn().execute(
        "SELECT id FROM payment_orders WHERE renewed_from_payment_id = ?",
        (pay["id"],),
    ).fetchone()
    if existing_renewal_row:
        existing_renewal = db.get_payment_order_by_id(existing_renewal_row["id"])
        return _renew_success_response(
            existing_renewal,
            "Mã thanh toán này đã được tạo lại trước đó.",
        )

    now = time.time()
    if pay["status"] == "paid":
        return jsonify({"success": False, "error": "cannot_renew_paid", "msg": "Giao dịch đã thanh toán thành công, không thể tạo lại mã."}), 400
    if pay["status"] in ("underpaid", "review_needed"):
        return jsonify({"success": False, "error": "invalid_status_for_renew", "msg": f"Giao dịch ở trạng thái '{pay['status']}' không thể tự động tạo lại mã."}), 400

    # A still-active payment is returned as-is. An overdue pending payment is
    # transitioned and renewed later in the same write transaction so its
    # coupon reservation is never temporarily released to another customer.
    if pay["status"] == "pending":
        if pay["expires_at"] >= now:
            return _renew_success_response(pay, "Mã thanh toán hiện tại vẫn còn hiệu lực.")

    if pay["status"] not in ("pending", "expired", "cancelled"):
        return jsonify({"success": False, "error": "invalid_status_for_renew", "msg": f"Không thể tạo lại mã cho giao dịch ở trạng thái '{pay['status']}'."}), 400

    conn = db.get_conn()
    ttl = payment_service.get_payment_config()["ttl"]
    try:
        conn.execute("BEGIN IMMEDIATE")
        fresh = conn.execute(
            "SELECT * FROM payment_orders WHERE id = ?", (pay["id"],)
        ).fetchone()
        if not fresh or (fresh["user_id"] != user_id and not _is_request_admin()):
            conn.execute("ROLLBACK")
            return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy giao dịch."}), 404
        owner_user_id = fresh["user_id"]

        already_renewed = conn.execute(
            "SELECT id FROM payment_orders WHERE renewed_from_payment_id = ?",
            (pay["id"],),
        ).fetchone()
        if already_renewed:
            conn.execute("ROLLBACK")
            replacement = db.get_payment_order_by_id(already_renewed["id"])
            return _renew_success_response(
                replacement,
                "Mã thanh toán này đã được tạo lại trước đó.",
            )

        if fresh["status"] == "paid":
            conn.execute("ROLLBACK")
            return jsonify({"success": False, "error": "cannot_renew_paid", "msg": "Giao dịch vừa được xác nhận thành công, không thể tạo lại mã."}), 409
        if fresh["status"] == "pending" and fresh["expires_at"] >= now:
            conn.execute("ROLLBACK")
            current_payment = db.get_payment_order_by_id(fresh["id"])
            return _renew_success_response(current_payment, "Mã thanh toán hiện tại vẫn còn hiệu lực.")
        if fresh["status"] not in ("pending", "expired", "cancelled"):
            conn.execute("ROLLBACK")
            return jsonify({"success": False, "error": "invalid_status_for_renew", "msg": f"Không thể tạo lại mã cho giao dịch ở trạng thái '{fresh['status']}'."}), 400

        if fresh["status"] == "pending":
            conn.execute(
                "UPDATE payment_orders SET status = 'expired', updated_at = ? WHERE id = ?",
                (now, fresh["id"]),
            )

        redemption = conn.execute(
            "SELECT * FROM coupon_redemptions WHERE payment_order_id = ? ORDER BY id DESC LIMIT 1",
            (fresh["id"],),
        ).fetchone()
        if fresh["coupon_id"] is not None:
            if not redemption or redemption["status"] == "redeemed":
                conn.execute("ROLLBACK")
                return jsonify({
                    "success": False,
                    "error": "coupon_reservation_unavailable",
                    "msg": "Lượt giữ chỗ của mã giảm giá không còn hợp lệ.",
                }), 409
            if redemption["status"] == "released":
                from .. import coupon_service
                coupon_service.sweep_expired_reservations(conn, now)
                coupon = conn.execute(
                    "SELECT usage_limit_total, usage_limit_per_user FROM coupons WHERE id = ?",
                    (fresh["coupon_id"],),
                ).fetchone()
                if not coupon:
                    conn.execute("ROLLBACK")
                    return jsonify({"success": False, "error": "coupon_not_found", "msg": "Mã giảm giá không còn tồn tại."}), 409
                total_in_use = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM coupon_redemptions "
                    "WHERE coupon_id = ? AND id != ? AND status IN ('reserved', 'redeemed')",
                    (fresh["coupon_id"], redemption["id"]),
                ).fetchone()["cnt"]
                user_in_use = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM coupon_redemptions "
                    "WHERE coupon_id = ? AND user_id = ? AND id != ? "
                    "AND status IN ('reserved', 'redeemed')",
                    (fresh["coupon_id"], owner_user_id, redemption["id"]),
                ).fetchone()["cnt"]
                if (coupon["usage_limit_total"] is not None
                        and total_in_use >= coupon["usage_limit_total"]):
                    conn.execute("ROLLBACK")
                    return jsonify({"success": False, "error": "coupon_exhausted", "msg": "Mã giảm giá đã hết lượt sử dụng; không thể tạo lại QR với giá cũ."}), 409
                if (coupon["usage_limit_per_user"] is not None
                        and user_in_use >= coupon["usage_limit_per_user"]):
                    conn.execute("ROLLBACK")
                    return jsonify({"success": False, "error": "user_limit_reached", "msg": "Bạn đã dùng hết lượt của mã giảm giá; không thể tạo lại QR."}), 409

        new_payment_code = payment_service.generate_internal_payment_code("PAY")
        old_transfer_code = fresh["transfer_code"] or fresh["payment_code"]
        new_transfer_code = payment_service.allocate_transfer_code(conn, now, exclude_code=old_transfer_code)
        new_qr_url = payment_service.build_vietqr_url(fresh["amount_vnd"], new_transfer_code)
        bank_cfg = payment_service.get_bank_config()

        cursor = conn.execute(
            """INSERT INTO payment_orders
               (payment_code, transfer_code, idempotency_hash, user_id, purpose, plan_id,
                amount_vnd, coin_amount, provider, status, qr_payload, idempotency_key,
                expires_at, created_at, updated_at,
                original_price_vnd_snapshot, discount_vnd_snapshot, coupon_id, coupon_code_snapshot,
                renewed_from_payment_id)
               VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 'vietqr', 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_payment_code,
                new_transfer_code,
                owner_user_id,
                fresh["purpose"],
                fresh["plan_id"],
                fresh["amount_vnd"],
                fresh["coin_amount"],
                new_qr_url,
                f"renew_{fresh['id']}_{secrets.token_hex(6)}",
                now + ttl,
                now,
                now,
                fresh["original_price_vnd_snapshot"] or fresh["amount_vnd"],
                fresh["discount_vnd_snapshot"] or 0,
                fresh["coupon_id"],
                fresh["coupon_code_snapshot"],
                fresh["id"],
            ),
        )
        new_pay_id = cursor.lastrowid

        # Transfer existing coupon redemption to new payment order
        if redemption:
            conn.execute(
                """UPDATE coupon_redemptions
                   SET payment_order_id = ?, status = 'reserved', expires_at = ?, released_at = NULL
                   WHERE id = ?""",
                (new_pay_id, now + ttl, redemption["id"]),
            )

        act_info = None
        if fresh["purpose"] == "plan_purchase":
            act = conn.execute(
                "SELECT * FROM activation_orders WHERE payment_order_id = ? ORDER BY id DESC LIMIT 1",
                (fresh["id"],),
            ).fetchone()
            if not act:
                conn.execute("ROLLBACK")
                return jsonify({"success": False, "error": "activation_order_missing", "msg": "Đơn kích hoạt liên kết không còn tồn tại."}), 409
            conn.execute(
                "UPDATE activation_orders SET payment_order_id = ?, status = 'awaiting_payment', updated_at = ? WHERE id = ?",
                (new_pay_id, now, act["id"]),
            )
            act_row = conn.execute("SELECT * FROM activation_orders WHERE id = ?", (act["id"],)).fetchone()
            act_info = dict(act_row) if act_row else None

        conn.execute("COMMIT")
        new_pay = db.get_payment_order_by_id(new_pay_id)
        new_pay["payment_ref"] = new_payment_code
        new_pay["transfer_code"] = new_transfer_code
        new_pay["qr_url"] = new_qr_url
        new_pay["server_time"] = now
        new_pay["expires_in"] = ttl
        new_pay["bank_config"] = bank_cfg

        return _renew_success_response(new_pay)
    except payment_service.PaymentCodePoolExhaustedError:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return jsonify({
            "success": False,
            "error": "payment_code_pool_exhausted",
            "msg": "Hệ thống đang quá tải mã chuyển khoản. Vui lòng thử lại sau ít phút.",
        }), 503
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return jsonify({"success": False, "error": "renew_failed", "msg": f"Không thể tạo lại mã: {e}"}), 500


# ---- Direct Coin Purchase Endpoints ----

@bp.route("/api/coupons/validate", methods=["POST"])
@access_required
def coupon_validate():
    """Validate coupon code and return quotation for specified plan."""
    if not validate_csrf():
        return jsonify({
            "success": False,
            "error": "invalid_csrf_token",
            "msg": "Phiên làm việc đã hết hạn hoặc CSRF token không hợp lệ. Vui lòng tải lại trang.",
        }), 403

    if not request.is_json or not isinstance(request.json, dict):
        return jsonify({"success": False, "error": "invalid_payload", "msg": "Dữ liệu yêu cầu không hợp lệ."}), 400

    body = request.json or {}
    raw_code = str(body.get("code") or "").strip()
    plan_id = body.get("plan_id")

    if not raw_code:
        return jsonify({"success": False, "valid": False, "error": "code_required", "msg": "Vui lòng nhập mã giảm giá."}), 400
    if not plan_id:
        return jsonify({"success": False, "valid": False, "error": "plan_id_required", "msg": "Vui lòng chọn gói dịch vụ."}), 400

    user_id = g.current_user["id"]
    from .. import coupon_service
    conn = db.get_conn()
    is_valid, coupon, quote, err_code, err_msg = coupon_service.validate_and_quote_coupon(
        conn, raw_code, plan_id, user_id
    )

    if not is_valid:
        return jsonify({
            "success": False,
            "valid": False,
            "error": err_code,
            "msg": err_msg,
        }), 400

    return jsonify({
        "success": True,
        "valid": True,
        "code": coupon["code"],
        "normalized_code": coupon["normalized_code"],
        "coupon_name": coupon["name"],
        "discount_type": coupon["discount_type"],
        "discount_value": coupon["discount_value"],
        "original_vnd": quote["original_vnd"],
        "original_coin": quote["original_coin"],
        "discount_vnd": quote["discount_vnd"],
        "discount_coin": quote["discount_coin"],
        "final_vnd": quote["final_vnd"],
        "final_coin": quote["final_coin"],
        "quote": quote,
        "message": "Áp dụng mã giảm giá thành công.",
    })


@bp.route("/api/orders/coin", methods=["POST"])
@access_required
def purchase_plan_coin():
    """Purchase and activate a plan using existing coin balance."""
    if not request.is_json or not isinstance(request.json, dict):
        return jsonify({"success": False, "error": "invalid_payload", "msg": "Dữ liệu yêu cầu không hợp lệ."}), 400
    body = request.json or {}
    plan_id = body.get("plan_id")
    platform = (body.get("platform") or "").strip().lower()
    username = (body.get("username") or body.get("target_username") or "").strip()

    if not plan_id:
        return jsonify({"success": False, "error": "plan_id_required", "msg": "Vui lòng chọn gói dịch vụ."}), 400

    plan = db.get_plan_by_id(plan_id, public=False)
    if not plan or not plan["is_active"]:
        return jsonify({"success": False, "error": "Gói dịch vụ không khả dụng", "msg": "Gói dịch vụ không khả dụng hoặc đã bị ẩn."}), 400
    if plan.get("inventory_status") == "out_of_stock":
        return jsonify({"success": False, "error": "out_of_stock", "msg": "Gói dịch vụ tạm hết hàng."}), 400

    if platform == "all":
        platform = "ios" if plan["supported_platforms"] in ("all", "ios") else "android"

    if plan["supported_platforms"] != "all" and plan["supported_platforms"] != platform:
        return jsonify({"success": False, "error": "Gói dịch vụ không hỗ trợ nền tảng", "msg": f"Gói này chỉ hỗ trợ {plan['supported_platforms']}."}), 400

    if platform not in ("ios", "android"):
        return jsonify({"success": False, "error": "invalid_platform", "msg": "Vui lòng chọn nền tảng hợp lệ (ios hoặc android)."}), 400
    mode, username, contact_zalo, contact_facebook, fulfillment_error = (
        _validate_fulfillment_payload(plan, platform, body)
    )
    if fulfillment_error:
        return fulfillment_error

    if username:
        gold_block = _gold_block_error(username)
        if gold_block is not None:
            code, msg = gold_block
            return jsonify({"success": False, "error": code, "msg": msg}), 409

    user_id = g.current_user["id"]
    price_coin = plan["price_coin"]
    client_idem = str(body.get("idempotency_key") or "").strip()
    if len(client_idem) > 200:
        return jsonify({
            "success": False,
            "error": "invalid_idempotency_key",
            "msg": "Khóa chống trùng giao dịch không hợp lệ.",
        }), 400
    coupon_code = str(body.get("coupon_code") or "").strip()
    idempotency_key = client_idem or f"coin_order_{user_id}_{plan_id}_{secrets.token_hex(12)}"
    tx_status, tx_res = db.purchase_plan_with_coin_atomic(
        user_id=user_id,
        plan_id=plan_id,
        platform=platform,
        fulfillment_mode=mode,
        locket_username=username,
        contact_zalo=contact_zalo,
        contact_facebook=contact_facebook,
        idempotency_key=idempotency_key,
        coupon_code=coupon_code if coupon_code else None,
    )

    if tx_status == "coupon_error":
        return jsonify({
            "success": False,
            "error": tx_res["error"],
            "msg": tx_res["msg"],
        }), 400

    if tx_status == "insufficient_balance":
        return jsonify({
            "success": False,
            "error": "insufficient_coins",
            **tx_res,
            "msg": "Số dư Coin không đủ.",
        }), 400
    if tx_status == "idempotency_conflict":
        return jsonify({
            "success": False,
            "error": "idempotency_conflict",
            "msg": "Khóa giao dịch đã được dùng cho một yêu cầu khác.",
        }), 409
    if tx_status == "error":
        return jsonify({
            "success": False,
            "error": "transaction_error",
            "msg": f"Lỗi giao dịch ví: {tx_res}",
        }), 500

    order = tx_res["order"]
    act_id = order["id"]
    disp_status, disp_res = payment_service.dispatch_paid_activation_order(
        act_id, app=current_app._get_current_object()
    )
    dispatched = disp_res.get("order", {}) if disp_status == "queue_error" else disp_res
    if isinstance(dispatched, dict):
        order.update(dispatched)
    client_id = order.get("queue_client_id")
    status = order.get("status")

    # Only the transaction that created and charged the order may announce it.
    # Idempotent client retries reuse the response without sending duplicates.
    if tx_status == "ok":
        try:
            from ..notifications import notify_paid_order

            notify_paid_order(act_id)
        except Exception as exc:
            current_app.logger.warning(
                "Unable to schedule Telegram order notification (%s)",
                type(exc).__name__,
            )

    messages = {
        "auto_activation": (
            "Thanh toán thành công! Đơn đã được đưa vào hàng đợi kích hoạt."
            if client_id else
            "Thanh toán thành công! Hàng đợi đang bận; đơn sẽ được xử lý khi có lượt."
        ),
        "manual_contact": "Thanh toán thành công! Thông tin liên hệ đã được gửi tới Admin.",
        "apk_download": "Thanh toán thành công! Bạn có thể tải file APK ngay bây giờ.",
    }
    return jsonify({
        "success": True,
        "activation_order_id": act_id,
        "order": order,
        "client_id": client_id,
        "status": status,
        "fulfillment_mode": mode,
        "idempotent": tx_status == "idempotent",
        "msg": messages[mode],
        "remaining_balance": tx_res["remaining_balance"],
    })


# ---- User Activation Orders Endpoints ----

@bp.route("/api/orders", methods=["GET"])
@access_required
def list_user_orders():
    """List current user's activation orders."""
    user_id = g.current_user["id"]
    limit = request.args.get("limit", 20)
    offset = request.args.get("offset", 0)
    data = db.list_activation_orders_by_user(user_id, limit=limit, offset=offset)
    for item in data.get("items", []):
        if item.get("contact_zalo"):
            item["contact_zalo"] = db.mask_zalo(item["contact_zalo"])
        if not item.get("locket_username"):
            item["locket_username"] = ""
    return jsonify({"success": True, **data})


@bp.route("/api/orders/<int:order_id>", methods=["GET"])
@access_required
def get_user_order(order_id):
    """Get details of an activation order."""
    user_id = g.current_user["id"]
    order = db.get_activation_order_by_id(order_id, user_id=user_id)
    if not order:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy đơn kích hoạt."}), 404
    if order.get("contact_zalo"):
        order["contact_zalo"] = db.mask_zalo(order["contact_zalo"])
    if not order.get("locket_username"):
        order["locket_username"] = ""
    queue_info = None
    if order.get("queue_client_id"):
        qm = current_app.queue_manager
        queue_info = qm.get_status(order["queue_client_id"], user_id=user_id)
    return jsonify({"success": True, "order": order, "queue": queue_info})


# ---- Platform & DNS Configuration Endpoint ----

@bp.route("/api/platform-config", methods=["GET"])
def platform_config():
    """Public-safe platform, DNS, and file availability configuration."""
    dns_info = site_settings.get_public_dns_config()
    ext_url = _external_apk_url()
    local_apk = os.path.exists(_apk_path())
    apk_exists = bool(ext_url) or local_apk
    apk_delivery = "external" if ext_url else ("local" if local_apk else "unavailable")
    mobileconfig_exists = os.path.exists(_mobileconfig_path())
    bank_cfg = payment_service.get_bank_config()
    payload = {
        "success": True,
        "dns": dns_info,
        "supported_platforms": ["ios", "android"],
        "apk_available": apk_exists,
        "apk_delivery": apk_delivery,
        "mobileconfig_available": mobileconfig_exists,
        "bank_configured": bank_cfg["is_configured"],
    }
    apk_version = os.getenv("ANDROID_APK_VERSION")
    if apk_version:
        payload["apk_version"] = apk_version.strip()
    apk_sha256 = os.getenv("ANDROID_APK_SHA256")
    if apk_sha256:
        payload["apk_sha256"] = apk_sha256.strip()
    return jsonify(payload)
