"""Admin REST API Blueprint for Locket Gold.

Prefix: /api/admin
Authentication: Bearer JWT access token via @admin_token_required.
Database Verification: Checked on every request against users table (role == 'admin').
CSRF: Enforced on mutating methods (POST, PUT, PATCH, DELETE) matching apiClient convention.
Security Headers: 'Cache-Control: private, no-store, must-revalidate'.
Audit Logging: Critical mutations recorded into admin_audit_logs with redaction.
"""

import json
import os
import re
import sqlite3
import time
from functools import wraps
from urllib.parse import urlparse

from flask import Blueprint, current_app, g, jsonify, make_response, request
import requests

from . import db
from . import payment_service
from . import proxies as proxy_pool
from . import site_settings
from .admin_provision import is_seed_admin
from .rotator import AccountRotator
from .token_auth import access_required
from .tokens import tokens_store
from .user_auth import get_client_ip, validate_csrf

admin_api_bp = Blueprint("admin_api", __name__, url_prefix="/api/admin")


@admin_api_bp.before_request
def check_admin_maintenance():
    """Enforce maintenance mode on admin API if allow_admin is disabled."""
    m = site_settings.get_maintenance()
    if m.get("enabled") and not m.get("allow_admin", True):
        # Keep a narrow recovery path available. Route decorators still
        # enforce an authenticated admin and CSRF on state changes.
        recovery_endpoints = {
            "admin_api.maintenance_get",
            "admin_api.maintenance_set",
            "admin_api.site_settings_get_composite",
            "admin_api.site_settings_set_composite",
        }
        if request.endpoint in recovery_endpoints:
            return None
        return jsonify({
            "success": False,
            "maintenance": True,
            "error": "maintenance_mode",
            "msg": m.get("message") or "Hệ thống đang bảo trì toàn diện.",
            "end_at": m.get("end_at") or None,
        }), 503


def make_list_envelope(items: list, total: int, limit: int, offset: int, legacy_key: str = None) -> dict:
    """Produce canonical list envelope with items and pagination, preserving backward-compatibility keys."""
    limit = max(1, min(int(limit), 100))
    offset = max(0, offset)
    page = (offset // limit) + 1
    pages = (total + limit - 1) // limit
    has_more = (offset + len(items)) < total
    envelope = {
        "success": True,
        "items": items,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "page": page,
            "pages": pages,
            "has_more": has_more,
        },
        # Backward compatibility top-level fields
        "total": total,
        "limit": limit,
        "offset": offset,
        "page": page,
        "pages": pages,
        "has_more": has_more,
    }
    if legacy_key:
        envelope[legacy_key] = items
    return envelope


def _parse_pagination(default_limit: int):
    """Parse pagination once and keep DB and response metadata aligned."""
    raw_limit = request.args.get("limit") or request.args.get("page_size") or default_limit
    try:
        limit = max(1, min(int(raw_limit), 100))
    except (ValueError, TypeError):
        limit = default_limit

    raw_offset = request.args.get("offset")
    raw_page = request.args.get("page")
    if raw_page is not None and raw_offset is None:
        try:
            offset = (max(1, int(raw_page)) - 1) * limit
        except (ValueError, TypeError):
            offset = 0
    else:
        try:
            offset = max(0, int(raw_offset or 0))
        except (ValueError, TypeError):
            offset = 0
    return limit, offset


def _json_bool(data: dict, field: str, *, default=None):
    """Parse a strict JSON boolean; strings such as 'false' are invalid."""
    if field not in data:
        return default, None
    value = data[field]
    if not isinstance(value, bool):
        return None, (jsonify({
            "success": False,
            "error": "invalid_boolean",
            "msg": f"Field '{field}' must be a JSON boolean (true/false).",
        }), 400)
    return value, None


def admin_token_required(view):
    """Decorator ensuring request has a valid Bearer JWT and user has role='admin' in DB."""
    @wraps(view)
    @access_required
    def wrapped(*args, **kwargs):
        user = getattr(g, "current_user", None)
        if not user or user.get("role") != "admin":
            return jsonify({
                "success": False,
                "error": "forbidden",
                "msg": "Bạn không có quyền quản trị để truy cập tài nguyên này.",
            }), 403

        # CSRF enforcement on state-changing methods
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if not validate_csrf():
                return jsonify({
                    "success": False,
                    "error": "invalid_csrf_token",
                    "msg": "Mã CSRF quản trị không hợp lệ hoặc đã hết hạn. Vui lòng tải lại trang.",
                }), 403

        return view(*args, **kwargs)

    return wrapped


@admin_api_bp.after_request
def add_admin_headers(response):
    """Prevent any caching of administrative data."""
    response.headers["Cache-Control"] = "private, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


# ---- Helper Functions ----

def _audit(action: str, entity_type: str, entity_id=None, before=None, after=None):
    """Record an audit log for current request."""
    try:
        admin_id = g.current_user["id"] if hasattr(g, "current_user") and g.current_user else 0
        ip = get_client_ip()
        ua = request.headers.get("User-Agent", "")[:255]
        db.record_admin_audit_log(
            admin_user_id=admin_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_data=before,
            after_data=after,
            ip_address=ip,
            user_agent=ua,
        )
    except Exception as exc:
        current_app.logger.error(f"Audit log recording error: {exc}")


def _redact_proxy(url):
    try:
        if "://" not in url:
            return url
        scheme, rest = url.split("://", 1)
        if "@" not in rest:
            return url
        creds, host = rest.rsplit("@", 1)
        if ":" in creds:
            user, _ = creds.split(":", 1)
            return f"{scheme}://{user}:***@{host}"
        return f"{scheme}://{creds}@{host}"
    except Exception:
        return url


# ---- Dashboard & Overview ----

@admin_api_bp.route("/overview", methods=["GET"])
@admin_token_required
def overview():
    """Returns analytics and dashboard stats for given range."""
    range_str = request.args.get("range", "30d").strip()
    if range_str not in ("7d", "30d", "90d"):
        range_str = "30d"

    data = db.get_admin_overview_stats(range_str)

    # Attach live worker counts
    qm = getattr(current_app, "queue_manager", None)
    rotator = getattr(current_app, "rotator", None)
    active_workers = len(qm.workers) if qm and hasattr(qm, "workers") else (rotator.size() if rotator else 0)
    data["cards"]["active_workers"] = active_workers
    data["cards"]["manual_pending_orders"] = db.get_manual_pending_orders_count()

    return jsonify(data)


# ---- User Management ----

@admin_api_bp.route("/users", methods=["GET"])
@admin_token_required
def users_list():
    """List users with pagination, filtering, and search."""
    query = request.args.get("q") or request.args.get("query")
    role = request.args.get("role")
    raw_active = request.args.get("is_active")
    if raw_active is None:
        status_param = request.args.get("status")
        if status_param == "active":
            raw_active = "1"
        elif status_param == "inactive":
            raw_active = "0"

    is_active = (raw_active == "1" or raw_active == "true") if raw_active in ("1", "0", "true", "false") else None

    limit, offset = _parse_pagination(20)

    result = db.list_users_admin(query=query, role=role, is_active=is_active, limit=limit, offset=offset)
    # Ensure items have is_seed_admin flag
    for u in result["items"]:
        u["is_seed_admin"] = is_seed_admin(u)
    return jsonify(make_list_envelope(result["items"], result["total"], limit, offset, legacy_key="users"))


@admin_api_bp.route("/users/<int:user_id>", methods=["GET"])
@admin_token_required
def user_detail(user_id: int):
    """Fetch user profile, wallet details, recent orders, and payments."""
    detail = db.get_user_detail_admin(user_id)
    if not detail:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy người dùng."}), 404
    detail["is_seed_admin"] = is_seed_admin(detail)
    return jsonify({
        "success": True,
        "user": detail,
        # Backward compatibility aliases
        "wallet_transactions": detail.get("wallet_transactions") or detail.get("recent_wallet_transactions") or [],
        "activation_orders": detail.get("recent_orders") or [],
        "payments": detail.get("recent_payments") or [],
        "reviews": [detail.get("review")] if detail.get("review") else [],
    })


@admin_api_bp.route("/users/<int:user_id>/status", methods=["POST"])
@admin_token_required
def user_set_status(user_id: int):
    """Enable or disable user account."""
    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy người dùng."}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" not in data:
        return jsonify({"success": False, "error": "missing_is_active", "msg": "Trường is_active là bắt buộc."}), 400

    new_active, bool_error = _json_bool(data, "is_active")
    if bool_error:
        return bool_error

    # Protect seed admin from being deactivated
    if not new_active and is_seed_admin(target_user):
        return jsonify({
            "success": False,
            "error": "seed_admin_immutable",
            "msg": "Không thể khóa tài khoản quản trị viên gốc (seed admin).",
        }), 400

    old_active = bool(target_user.get("is_active"))
    db.set_user_active(user_id, new_active)

    if not new_active:
        db.revoke_all_user_sessions(user_id, reason="admin_deactivated")

    _audit(
        action="user_status_update",
        entity_type="user",
        entity_id=user_id,
        before={"is_active": old_active, "username": target_user["username"]},
        after={"is_active": new_active, "username": target_user["username"]},
    )

    action_label = "mở khóa" if new_active else "khóa"
    return jsonify({
        "success": True,
        "is_active": new_active,
        "msg": f"Đã {action_label} tài khoản '{target_user['username']}' thành công.",
    })


@admin_api_bp.route("/users/<int:user_id>/role", methods=["POST"])
@admin_token_required
def user_set_role(user_id: int):
    """Update user role (user or admin)."""
    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy người dùng."}), 404

    data = request.get_json(silent=True) or {}
    new_role = (data.get("role") or "").strip().lower()
    if new_role not in ("user", "admin"):
        return jsonify({"success": False, "error": "invalid_role", "msg": "Vai trò chỉ có thể là 'user' hoặc 'admin'."}), 400

    # Protect seed admin from demotion
    if new_role != "admin" and is_seed_admin(target_user):
        return jsonify({
            "success": False,
            "error": "seed_admin_immutable",
            "msg": "Không thể hạ quyền tài khoản quản trị viên gốc (seed admin).",
        }), 400

    old_role = target_user.get("role", "user")
    if old_role != new_role:
        db.update_user_role(user_id, new_role)
        db.revoke_all_user_sessions(user_id, reason="admin_role_changed")
        _audit(
            action="user_role_update",
            entity_type="user",
            entity_id=user_id,
            before={"role": old_role, "username": target_user["username"]},
            after={"role": new_role, "username": target_user["username"]},
        )

    return jsonify({
        "success": True,
        "role": new_role,
        "msg": f"Đã cập nhật vai trò của '{target_user['username']}' thành '{new_role}'.",
    })


@admin_api_bp.route("/users/<int:user_id>/adjust-wallet", methods=["POST"])
@admin_api_bp.route("/users/<int:user_id>/wallet/adjust", methods=["POST"])
@admin_token_required
def user_adjust_wallet(user_id: int):
    """Adjust user Coin balance with atomic ledger and idempotency."""
    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy người dùng."}), 404

    data = request.get_json(silent=True) or {}
    raw_amount = data.get("amount_coin") if data.get("amount_coin") is not None else data.get("delta_coin")
    reason = (data.get("reason") or "").strip()
    idempotency_key = (data.get("idempotency_key") or "").strip() or f"admin_adj_{user_id}_{int(time.time()*1000)}"

    if raw_amount is None:
        return jsonify({"success": False, "error": "missing_amount", "msg": "Số lượng Coin điều chỉnh là bắt buộc."}), 400
    if not reason:
        return jsonify({"success": False, "error": "reason_required", "msg": "Lý do điều chỉnh số dư là bắt buộc."}), 400

    try:
        amount_coin = int(raw_amount)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "invalid_amount", "msg": "Số lượng Coin phải là số nguyên."}), 400

    if amount_coin == 0:
        return jsonify({"success": False, "error": "zero_amount", "msg": "Số lượng Coin điều chỉnh không thể bằng 0."}), 400

    admin_id = g.current_user["id"] if hasattr(g, "current_user") and g.current_user else 1
    ip = get_client_ip()
    ua = request.headers.get("User-Agent", "")[:255]

    status, res = db.admin_adjust_user_wallet_atomic(
        user_id=user_id,
        amount_coin=amount_coin,
        reason=reason,
        admin_user_id=admin_id,
        idempotency_key=idempotency_key,
        ip_address=ip,
        user_agent=ua,
    )

    if status == "insufficient_balance":
        return jsonify({
            "success": False,
            "error": "insufficient_balance",
            "msg": "Số dư người dùng không đủ để trừ số Coin này.",
        }), 400
    if status == "error":
        return jsonify({"success": False, "error": "adjustment_failed", "msg": str(res)}), 400

    tx_data = res.get("transaction", {})
    balance_after = res.get("balance_coin") if "balance_coin" in res else tx_data.get("balance_after", 0)

    return jsonify({
        "success": True,
        "user_id": user_id,
        "balance_coin": balance_after,
        "transaction": tx_data,
        "msg": f"Đã điều chỉnh {amount_coin:+d} Coin cho '{target_user['username']}' thành công.",
    })


# ---- Activation Orders ----

@admin_api_bp.route("/orders", methods=["GET"])
@admin_token_required
def orders_list():
    """List activation orders with filtering and pagination."""
    status = request.args.get("status")
    platform = request.args.get("platform")
    fulfillment_mode = request.args.get("fulfillment_mode")
    query = request.args.get("q") or request.args.get("query")
    limit, offset = _parse_pagination(20)

    res = db.list_activation_orders_admin(
        status=status,
        platform=platform,
        fulfillment_mode=fulfillment_mode,
        query=query,
        limit=limit,
        offset=offset,
    )
    envelope = make_list_envelope(res["items"], res["total"], limit, offset, legacy_key="orders")
    envelope["manual_pending_count"] = db.get_manual_pending_orders_count()
    return jsonify(envelope)


@admin_api_bp.route("/orders/<int:order_id>/start", methods=["POST"])
@admin_api_bp.route("/orders/<int:order_id>/complete", methods=["POST"])
@admin_token_required
def manual_order_transition(order_id: int):
    action = "complete" if request.path.endswith("/complete") else "start"
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()
    status, result = db.admin_transition_manual_order(
        order_id=order_id,
        action=action,
        admin_user_id=g.current_user["id"],
        note=note,
        ip_address=get_client_ip(),
        user_agent=request.headers.get("User-Agent", "")[:255],
    )
    if status == "not_found":
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy đơn."}), 404
    if status in ("invalid_transition", "idempotent"):
        current_st = result.get("status") if isinstance(result, dict) else str(result)
        return jsonify({
            "success": False,
            "error": "invalid_state_transition",
            "msg": f"Không thể thực hiện thao tác '{action}' cho đơn ở trạng thái '{current_st}'.",
        }), 409
    if status == "error":
        messages = {
            "not_manual_contact": "Chỉ có thể xử lý thủ công đơn VPN/Pro có thông tin liên hệ.",
            "admin_note_too_long": "Ghi chú không được vượt quá 500 ký tự.",
        }
        return jsonify({
            "success": False,
            "error": str(result),
            "msg": messages.get(str(result), "Không thể cập nhật đơn."),
        }), 400
    return jsonify({
        "success": True,
        "order": result,
        "msg": "Đã bắt đầu xử lý đơn." if action == "start" else "Đã hoàn thành đơn.",
    })


@admin_api_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@admin_token_required
def manual_order_cancel(order_id: int):
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if len(reason) < 5:
        return jsonify({
            "success": False,
            "error": "invalid_reason",
            "msg": "Vui lòng nhập lý do hủy đơn (tối thiểu 5 ký tự).",
        }), 400
    if len(reason) > 500:
        return jsonify({
            "success": False,
            "error": "reason_too_long",
            "msg": "Lý do hủy đơn không được vượt quá 500 ký tự.",
        }), 400

    status, result = db.admin_cancel_manual_order(
        order_id=order_id,
        reason=reason,
        admin_user_id=g.current_user["id"],
        ip_address=get_client_ip(),
        user_agent=request.headers.get("User-Agent", "")[:255],
    )
    if status == "not_found":
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy đơn."}), 404
    if status == "invalid_state_transition":
        return jsonify({"success": False, "error": "invalid_state_transition", "msg": str(result)}), 409
    if status == "error":
        messages = {
            "not_manual_contact": "Chỉ có thể hủy đơn thủ công có thông tin liên hệ.",
            "invalid_reason": "Lý do hủy đơn không hợp lệ.",
        }
        return jsonify({
            "success": False,
            "error": str(result),
            "msg": messages.get(str(result), str(result)),
        }), 400
    return jsonify({
        "success": True,
        "order": result,
        "msg": "Đã hủy đơn thành công.",
    })


@admin_api_bp.route("/orders/<int:order_id>/refund", methods=["POST"])
@admin_token_required
def manual_order_refund(order_id: int):
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    confirmed = bool(data.get("confirmed_external_refund") or data.get("confirmed"))
    ref = (data.get("refund_reference") or data.get("refund_tx_ref") or "").strip()

    if len(reason) < 5:
        return jsonify({
            "success": False,
            "error": "invalid_reason",
            "msg": "Vui lòng nhập lý do hoàn tiền (tối thiểu 5 ký tự).",
        }), 400
    if len(reason) > 500:
        return jsonify({
            "success": False,
            "error": "reason_too_long",
            "msg": "Lý do hoàn tiền không được vượt quá 500 ký tự.",
        }), 400

    status, result = db.admin_refund_manual_order(
        order_id=order_id,
        reason=reason,
        admin_user_id=g.current_user["id"],
        confirmed_external_refund=confirmed,
        refund_reference=ref,
        ip_address=get_client_ip(),
        user_agent=request.headers.get("User-Agent", "")[:255],
    )
    if status == "not_found":
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy đơn."}), 404
    if status == "invalid_state_transition":
        return jsonify({"success": False, "error": "invalid_state_transition", "msg": str(result)}), 409
    if status == "already_refunded":
        return jsonify({"success": False, "error": "already_refunded", "msg": str(result)}), 409
    if status == "error":
        messages = {
            "external_refund_confirmation_required": "Cần xác nhận đã chuyển khoản hoàn tiền bên ngoài cho khách hàng.",
            "refund_reference_required": "Vui lòng nhập mã giao dịch hoàn tiền ngân hàng.",
            "invalid_reason": "Lý do hoàn tiền không hợp lệ.",
            "unsupported_payment_method": "Phương thức thanh toán không hỗ trợ hoàn tiền qua hệ thống.",
        }
        return jsonify({
            "success": False,
            "error": str(result),
            "msg": messages.get(str(result), str(result)),
        }), 400
    return jsonify({
        "success": True,
        "order": result,
        "msg": "Đã hoàn tiền đơn thành công.",
    })



# ---- Plans Management ----

@admin_api_bp.route("/plans", methods=["GET"])
@admin_token_required
def plans_list():
    plans = db.list_all_plans_admin()
    limit = max(1, len(plans))
    return jsonify(make_list_envelope(plans, len(plans), limit, 0, legacy_key="plans"))


@admin_api_bp.route("/plans", methods=["POST"])
@admin_token_required
def plans_create():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or data.get("code") or "").strip().lower()
    short_desc = (data.get("short_description") or data.get("description") or "").strip()
    product_id = (data.get("product_id") or slug or "").strip()
    raw_duration = data.get("duration_days", 30)
    raw_price = data.get("price_vnd")
    features = data.get("features", [])
    platforms = data.get("supported_platforms") or data.get("platform") or "all"
    is_active, bool_error = _json_bool(data, "is_active", default=True)
    if bool_error:
        return bool_error
    is_popular, bool_error = _json_bool(data, "is_popular", default=False)
    if bool_error:
        return bool_error
    inventory_status = data.get("inventory_status", "in_stock")
    ios_fulfillment_mode = data.get("ios_fulfillment_mode")
    android_fulfillment_mode = data.get("android_fulfillment_mode")

    if not name or not slug or not product_id:
        return jsonify({"success": False, "error": "validation_error", "msg": "Tên, slug và product ID là bắt buộc."}), 400

    try:
        if raw_price is None and "price_coin" in data:
            raw_price = int(data["price_coin"]) * 1000
        duration_days = int(raw_duration)
        price_vnd = int(raw_price)
        sort_order = int(data.get("sort_order", 0))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "validation_error", "msg": "Thời hạn và giá VNĐ phải là số nguyên."}), 400

    if price_vnd <= 0 or price_vnd % 1000 != 0:
        return jsonify({"success": False, "error": "invalid_price", "msg": "Giá VNĐ phải là số nguyên dương chia hết cho 1.000."}), 400

    if platforms not in ("all", "ios", "android"):
        return jsonify({"success": False, "error": "invalid_platform", "msg": "Nền tảng hỗ trợ phải là all, ios hoặc android."}), 400

    try:
        plan_id = db.create_plan(
            name=name,
            slug=slug,
            short_description=short_desc,
            duration_days=duration_days,
            price_vnd=price_vnd,
            product_id=product_id,
            features=features,
            supported_platforms=platforms,
            is_active=is_active,
            is_popular=is_popular,
            sort_order=sort_order,
            inventory_status=inventory_status,
            ios_fulfillment_mode=ios_fulfillment_mode,
            android_fulfillment_mode=android_fulfillment_mode,
        )
        created = db.get_plan_by_id(plan_id, public=False)
        _audit("plan_create", "plan", plan_id, before=None, after=created)
        return jsonify({"success": True, "plan": created, "msg": "Tạo gói cước thành công."}), 201
    except ValueError as e:
        return jsonify({"success": False, "error": "validation_error", "msg": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Admin plan creation failed")
        return jsonify({"success": False, "error": "plan_create_failed", "msg": "Không thể tạo gói."}), 400


@admin_api_bp.route("/plans/<int:plan_id>", methods=["PUT"])
@admin_token_required
def plans_update(plan_id: int):
    old_plan = db.get_plan_by_id(plan_id, public=False)
    if not old_plan:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy gói cần cập nhật."}), 404

    data = request.get_json(silent=True) or {}
    for field in ("is_active", "is_popular"):
        _, bool_error = _json_bool(data, field)
        if bool_error:
            return bool_error
    try:
        ok = db.update_plan(plan_id, **data)
        if not ok:
            return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy gói."}), 404
        updated = db.get_plan_by_id(plan_id, public=False)
        _audit("plan_update", "plan", plan_id, before=old_plan, after=updated)
        return jsonify({"success": True, "plan": updated, "msg": "Cập nhật gói cước thành công."})
    except ValueError as e:
        return jsonify({"success": False, "error": "validation_error", "msg": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Admin plan update failed for plan %s", plan_id)
        return jsonify({"success": False, "error": "plan_update_failed", "msg": "Không thể cập nhật gói."}), 400


@admin_api_bp.route("/plans/<int:plan_id>/toggle", methods=["POST", "PATCH"])
@admin_token_required
def plans_toggle(plan_id: int):
    old_plan = db.get_plan_by_id(plan_id, public=False)
    if not old_plan:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy gói."}), 404
    data = request.get_json(silent=True) or {}
    new_active, bool_error = _json_bool(
        data, "is_active", default=not bool(old_plan.get("is_active"))
    )
    if bool_error:
        return bool_error
    ok = db.update_plan(plan_id, is_active=1 if new_active else 0)
    if not ok:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy gói."}), 404
    updated = db.get_plan_by_id(plan_id, public=False)
    _audit("plan_toggle", "plan", plan_id, before=old_plan, after=updated)
    return jsonify({"success": True, "plan": updated, "msg": "Cập nhật trạng thái gói thành công."})


@admin_api_bp.route("/plans/<int:plan_id>", methods=["DELETE"])
@admin_token_required
def plans_delete(plan_id: int):
    old_plan = db.get_plan_by_id(plan_id, public=False)
    if not old_plan:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy gói cần xóa."}), 404

    ok = db.delete_plan(plan_id)
    if not ok:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy gói."}), 404

    _audit("plan_delete", "plan", plan_id, before=old_plan, after=None)
    return jsonify({"success": True, "msg": "Đã xóa gói cước thành công."})


# ---- Payments Management ----

@admin_api_bp.route("/payments", methods=["GET"])
@admin_token_required
def payments_list():
    status = request.args.get("status")
    purpose = request.args.get("purpose")
    query = request.args.get("q") or request.args.get("query")
    limit, offset = _parse_pagination(50)

    res = db.list_payment_orders_admin(status=status, query=query, limit=limit, offset=offset, return_meta=True, purpose=purpose)
    return jsonify(make_list_envelope(res["items"], res["total"], limit, offset, legacy_key="payments"))


@admin_api_bp.route("/payments/<payment_ref>/confirm", methods=["POST"])
@admin_token_required
def payment_confirm(payment_ref):
    data = request.get_json(silent=True) or {}
    bank_tx_id = (data.get("bank_transaction_id") or "").strip()
    target_id_or_ref = int(payment_ref) if str(payment_ref).isdigit() else payment_ref

    status, res = payment_service.confirm_payment(
        payment_id_or_ref=target_id_or_ref,
        bank_transaction_id=bank_tx_id,
        current_app_instance=current_app._get_current_object(),
        audit_context={
            "admin_user_id": g.current_user["id"],
            "ip_address": get_client_ip(),
            "user_agent": request.headers.get("User-Agent", "")[:255],
        },
    )
    if status == "already_paid":
        return jsonify({"success": False, "error": "already_paid", "msg": "Đơn thanh toán này đã được xác nhận trước đó."}), 400
    if status == "expired":
        return jsonify({"success": False, "error": "payment_expired", "msg": "Mã thanh toán đã hết hạn, không thể xác nhận."}), 400
    if status == "not_found":
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy giao dịch thanh toán."}), 404
    if status != "ok":
        return jsonify({"success": False, "error": "confirm_failed", "msg": f"Xác nhận thất bại: {res}"}), 400

    pay_order = res
    return jsonify({
        "success": True,
        "payment": pay_order,
        "activation_order_id": pay_order.get("activation_order_id"),
        "msg": "Đã xác nhận thanh toán thành công!",
    })


@admin_api_bp.route("/payments/<payment_ref>/manual-confirm", methods=["POST"])
@admin_token_required
def payment_manual_confirm(payment_ref):
    """Manually settle a payment when bank automation is unavailable.

    This explicit override can recover expired/underpaid/review-needed orders,
    but never an already-paid or administrator-cancelled order.
    """
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    bank_tx_id = (data.get("bank_transaction_id") or "").strip()
    if len(reason) < 5:
        return jsonify({
            "success": False,
            "error": "manual_reason_required",
            "msg": "Vui lòng nhập lý do xác nhận thủ công (tối thiểu 5 ký tự).",
        }), 400
    if len(reason) > 500:
        return jsonify({
            "success": False,
            "error": "manual_reason_too_long",
            "msg": "Lý do xác nhận thủ công không được vượt quá 500 ký tự.",
        }), 400

    target_id_or_ref = int(payment_ref) if str(payment_ref).isdigit() else payment_ref
    status, res = payment_service.confirm_payment(
        payment_id_or_ref=target_id_or_ref,
        bank_transaction_id=bank_tx_id,
        current_app_instance=current_app._get_current_object(),
        audit_context={
            "admin_user_id": g.current_user["id"],
            "ip_address": get_client_ip(),
            "user_agent": request.headers.get("User-Agent", "")[:255],
        },
        manual_override=True,
        manual_reason=reason,
    )
    if status == "already_paid":
        return jsonify({"success": False, "error": "already_paid", "msg": "Giao dịch đã được xác nhận trước đó."}), 409
    if status == "not_found":
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy giao dịch thanh toán."}), 404
    if status != "ok":
        return jsonify({
            "success": False,
            "error": "manual_confirm_failed",
            "msg": f"Không thể xác nhận thủ công: {res}",
        }), 400

    pay_order = res
    return jsonify({
        "success": True,
        "manual": True,
        "payment": pay_order,
        "activation_order_id": pay_order.get("activation_order_id"),
        "msg": "Đã xác nhận thủ công và cập nhật quyền lợi thành công.",
    })


@admin_api_bp.route("/payments/<payment_ref>/reject", methods=["POST"])
@admin_token_required
def payment_reject(payment_ref):
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    target_id_or_ref = int(payment_ref) if str(payment_ref).isdigit() else payment_ref
    status, res = payment_service.reject_payment(
        payment_id_or_ref=target_id_or_ref,
        status="cancelled",
        note=reason or None,
        audit_context={
            "admin_user_id": g.current_user["id"],
            "ip_address": get_client_ip(),
            "user_agent": request.headers.get("User-Agent", "")[:255],
        },
    )
    if status == "not_found":
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy giao dịch thanh toán."}), 404
    if status != "ok":
        return jsonify({"success": False, "error": "reject_failed", "msg": f"Từ chối thất bại: {res}"}), 400

    return jsonify({"success": True, "msg": "Đã từ chối đơn thanh toán."})


# ---- Reviews Moderation ----

@admin_api_bp.route("/reviews", methods=["GET"])
@admin_token_required
def reviews_list():
    status = request.args.get("status", "all")
    query = request.args.get("q") or request.args.get("query")
    limit, offset = _parse_pagination(50)

    res = db.list_reviews_admin(status=status, limit=limit, offset=offset, query=query, return_meta=True)
    for r in res["items"]:
        for img in r.get("images", []):
            img["url"] = f"/api/admin/reviews/images/{img['storage_name']}"
    return jsonify(make_list_envelope(res["items"], res["total"], limit, offset, legacy_key="reviews"))


@admin_api_bp.route("/reviews/<int:review_id>/status", methods=["POST", "PATCH"])
@admin_api_bp.route("/reviews/<int:review_id>/moderate", methods=["POST"])
@admin_token_required
def review_set_status(review_id: int):
    # Reviews are published automatically. Keep the former route as an explicit
    # tombstone so stale clients cannot silently re-enable moderation.
    return jsonify({
        "success": False,
        "error": "review_moderation_disabled",
        "msg": "Đánh giá được đăng tự động; quản trị viên chỉ có thể xem hoặc xóa.",
    }), 410


@admin_api_bp.route("/reviews/<int:review_id>", methods=["DELETE"])
@admin_token_required
def review_delete(review_id: int):
    from .image_storage import delete_stored_image
    from .reviews import get_storage_root, invalidate_reviews_cache
    storage_root = get_storage_root()
    storage_names = db.delete_review(review_id)
    if storage_names is None:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy đánh giá cần xóa."}), 404

    for name in storage_names:
        delete_stored_image(name, storage_root, "review")

    invalidate_reviews_cache()
    _audit("review_delete", "review", review_id, before=None, after=None)
    return jsonify({"success": True, "msg": "Đã xóa đánh giá thành công."})


@admin_api_bp.route("/reviews/images/<storage_name>", methods=["GET"])
@admin_token_required
def review_image(storage_name: str):
    from flask import abort
    from .image_storage import serve_stored_image
    from .reviews import SAFE_FILENAME_REGEX, get_storage_root

    if not SAFE_FILENAME_REGEX.match(storage_name):
        abort(404)

    img_row = db.get_review_image_by_storage_name(storage_name)
    if not img_row:
        abort(404)

    resp = serve_stored_image(
        storage_name,
        get_storage_root(),
        "review",
        "private, no-store",
    )
    if resp is None:
        abort(404)
    return resp


# ---- TikTok Creators / KOL ----

_TIKTOK_HANDLE_RE = re.compile(r"^[a-zA-Z0-9._]{2,24}$")


def _creator_form_bool(field, default=False):
    raw = request.form.get(field)
    if raw is None:
        return default, None
    value = raw.strip().lower()
    if value in ("true", "1"):
        return True, None
    if value in ("false", "0"):
        return False, None
    return None, (jsonify({
        "success": False,
        "error": "invalid_boolean",
        "msg": f"Trường '{field}' phải là true hoặc false.",
    }), 400)


def _validate_creator_identity():
    handle = (request.form.get("tiktok_handle") or "").strip().lstrip("@").lower()
    url = (request.form.get("tiktok_url") or "").strip()
    if not _TIKTOK_HANDLE_RE.fullmatch(handle):
        return None, None, (jsonify({
            "success": False, "error": "invalid_tiktok_handle",
            "msg": "TikTok handle phải có 2–24 ký tự chữ, số, dấu chấm hoặc gạch dưới.",
        }), 400)
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        expected_path = f"/@{handle}"
        if parsed.scheme != "https" or host not in ("tiktok.com", "www.tiktok.com"):
            raise ValueError
        if parsed.path.rstrip("/").lower() != expected_path.lower():
            raise ValueError
        url = f"https://www.tiktok.com/@{handle}"
    except (TypeError, ValueError):
        return None, None, (jsonify({
            "success": False, "error": "invalid_tiktok_url",
            "msg": f"URL phải đúng dạng https://www.tiktok.com/@{handle}.",
        }), 400)
    return handle, url, None


def _parse_creator_numbers():
    follower_raw = (request.form.get("follower_count") or "").strip()
    sort_raw = (request.form.get("sort_order") or "0").strip()
    crop_raw = (request.form.get("crop_percent") or "24").strip()
    try:
        follower_count = None if follower_raw == "" else int(follower_raw)
        sort_order = int(sort_raw)
        crop_percent = int(crop_raw)
        if follower_count is not None and not 0 <= follower_count <= 2_000_000_000:
            raise ValueError
        if not -10_000 <= sort_order <= 10_000 or not 12 <= crop_percent <= 45:
            raise ValueError
    except (TypeError, ValueError):
        return None, None, None, (jsonify({
            "success": False, "error": "invalid_creator_numbers",
            "msg": "Follower, thứ tự hoặc tỷ lệ crop không hợp lệ.",
        }), 400)
    return follower_count, sort_order, crop_percent, None


def _format_admin_creator(item):
    item = dict(item)
    item["is_featured"] = bool(item.get("is_featured"))
    item["is_active"] = bool(item.get("is_active"))
    item["require_review"] = bool(item.get("require_review"))
    item["user_is_active"] = bool(item.get("user_is_active"))
    item["screenshot_url"] = f"/api/admin/creators/images/{item['screenshot_name']}"
    return item


@admin_api_bp.route("/creators", methods=["GET"])
@admin_token_required
def creators_list():
    limit, offset = _parse_pagination(50)
    result = db.list_creators_admin(request.args.get("q"), limit, offset)
    items = [_format_admin_creator(item) for item in result["items"]]
    return jsonify(make_list_envelope(items, result["total"], limit, offset, legacy_key="creators"))


@admin_api_bp.route("/creators", methods=["POST"])
@admin_token_required
def creator_create():
    from .creators import delete_creator_image, process_creator_screenshot

    email = (request.form.get("email") or "").strip().lower()
    user = db.get_user_by_email(email) if email else None
    if not user:
        return jsonify({"success": False, "error": "user_not_found", "msg": "Không tìm thấy tài khoản với email này."}), 404
    if not user.get("is_active"):
        return jsonify({"success": False, "error": "user_inactive", "msg": "Tài khoản đang bị khóa."}), 409
    handle, url, error = _validate_creator_identity()
    if error:
        return error
    display_name = (request.form.get("display_name") or user.get("display_name") or handle).strip()
    if not display_name or len(display_name) > 50:
        return jsonify({"success": False, "error": "invalid_display_name", "msg": "Tên hiển thị KOL phải có từ 1 đến 50 ký tự."}), 400
    follower_count, sort_order, crop_percent, error = _parse_creator_numbers()
    if error:
        return error
    is_featured, error = _creator_form_bool("is_featured")
    if error:
        return error
    is_active, error = _creator_form_bool("is_active", True)
    if error:
        return error
    require_review, error = _creator_form_bool("require_review")
    if error:
        return error

    screenshot = request.files.get("screenshot")
    if not screenshot or not screenshot.filename:
        return jsonify({"success": False, "error": "screenshot_required", "msg": "Vui lòng chọn ảnh chụp trang TikTok."}), 400
    image_meta, image_error = process_creator_screenshot(screenshot, crop_percent)
    if image_error:
        return jsonify({"success": False, "error": "invalid_screenshot", "msg": image_error}), 400

    try:
        creator_id = db.create_creator_profile(
            user["id"], display_name, handle, url, image_meta["storage_name"], follower_count,
            is_featured, is_active, require_review, sort_order,
        )
    except sqlite3.IntegrityError:
        delete_creator_image(image_meta["storage_name"])
        return jsonify({
            "success": False, "error": "creator_conflict",
            "msg": "Tài khoản hoặc TikTok handle này đã được nâng thành KOL.",
        }), 409

    creator = _format_admin_creator(db.get_creator_by_id(creator_id))
    _audit("creator_create", "creator", creator_id, before=None, after=creator)
    return jsonify({"success": True, "creator": creator, "msg": "Đã nâng tài khoản thành TikTok KOL."}), 201


@admin_api_bp.route("/creators/<int:creator_id>", methods=["PUT"])
@admin_token_required
def creator_update(creator_id):
    from .creators import delete_creator_image, process_creator_screenshot

    old = db.get_creator_by_id(creator_id)
    if not old:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy hồ sơ KOL."}), 404
    handle, url, error = _validate_creator_identity()
    if error:
        return error
    display_name = (request.form.get("display_name") or old.get("display_name") or handle).strip()
    if not display_name or len(display_name) > 50:
        return jsonify({"success": False, "error": "invalid_display_name", "msg": "Tên hiển thị KOL phải có từ 1 đến 50 ký tự."}), 400
    follower_count, sort_order, crop_percent, error = _parse_creator_numbers()
    if error:
        return error
    is_featured, error = _creator_form_bool("is_featured", bool(old["is_featured"]))
    if error:
        return error
    is_active, error = _creator_form_bool("is_active", bool(old["is_active"]))
    if error:
        return error
    require_review, error = _creator_form_bool("require_review", bool(old["require_review"]))
    if error:
        return error

    screenshot_name = old["screenshot_name"]
    new_image_name = None
    screenshot = request.files.get("screenshot")
    if screenshot and screenshot.filename:
        image_meta, image_error = process_creator_screenshot(screenshot, crop_percent)
        if image_error:
            return jsonify({"success": False, "error": "invalid_screenshot", "msg": image_error}), 400
        screenshot_name = image_meta["storage_name"]
        new_image_name = screenshot_name

    try:
        db.update_creator_profile(
            creator_id, display_name, handle, url, screenshot_name, follower_count,
            is_featured, is_active, require_review, sort_order,
        )
    except sqlite3.IntegrityError:
        if new_image_name:
            delete_creator_image(new_image_name)
        return jsonify({"success": False, "error": "creator_conflict", "msg": "TikTok handle này đã được sử dụng."}), 409

    if new_image_name:
        delete_creator_image(old["screenshot_name"])
    updated = _format_admin_creator(db.get_creator_by_id(creator_id))
    _audit("creator_update", "creator", creator_id, before=old, after=updated)
    return jsonify({"success": True, "creator": updated, "msg": "Đã cập nhật hồ sơ TikTok KOL."})


@admin_api_bp.route("/creators/<int:creator_id>", methods=["DELETE"])
@admin_token_required
def creator_delete(creator_id):
    from .creators import delete_creator_image

    old = db.get_creator_by_id(creator_id)
    if not old:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy hồ sơ KOL."}), 404
    storage_name = db.delete_creator_profile(creator_id)
    delete_creator_image(storage_name)
    _audit("creator_delete", "creator", creator_id, before=old, after=None)
    return jsonify({"success": True, "msg": "Đã xóa hồ sơ KOL; tài khoản và feedback vẫn được giữ nguyên."})


@admin_api_bp.route("/creators/images/<storage_name>", methods=["GET"])
@admin_token_required
def creator_admin_image(storage_name):
    from flask import abort
    from .creators import (
        SAFE_CREATOR_FILENAME,
        get_creator_storage_root,
    )
    from .image_storage import serve_stored_image

    if not SAFE_CREATOR_FILENAME.fullmatch(storage_name) or not db.get_creator_by_storage_name(storage_name):
        abort(404)
    response = serve_stored_image(
        storage_name,
        get_creator_storage_root(),
        "creator",
        "private, no-store",
    )
    if response is None:
        abort(404)
    return response


# ---- Queue & Worker Pool ----

@admin_api_bp.route("/queue", methods=["GET"])
@admin_token_required
def queue_snapshot():
    qm = getattr(current_app, "queue_manager", None)
    rotator = getattr(current_app, "rotator", None)
    snap = qm.admin_snapshot() if qm else {}
    worker_emails = {}
    active_workers_count = 0
    if qm and hasattr(qm, "workers"):
        active_workers_count = len(qm.workers)
        for slot_id in list(qm.workers.keys()):
            try:
                worker_emails[slot_id] = rotator.email(slot_id) if rotator else "<no rotator>"
            except KeyError:
                worker_emails[slot_id] = "<removed>"
    elif rotator:
        active_workers_count = rotator.size()

    waiting = snap.get("waiting", [])
    processing = snap.get("processing", [])
    recent = snap.get("recent", [])
    total_in_queue = snap.get("total_in_queue", len(waiting) + len(processing))
    combined_items = processing + waiting

    return jsonify({
        "success": True,
        "active_workers": active_workers_count,
        "total_in_queue": total_in_queue,
        "workers": worker_emails,
        "waiting": waiting,
        "processing": processing,
        "recent": recent,
        "items": combined_items,
        "snapshot": {
            "active_workers": active_workers_count,
            "total_in_queue": total_in_queue,
            "items": combined_items,
            "waiting": waiting,
            "processing": processing,
            "recent": recent,
        }
    })


# ---- Accounts (Rotator) ----

@admin_api_bp.route("/accounts", methods=["GET"])
@admin_token_required
def accounts_list():
    rotator = getattr(current_app, "rotator", None)
    if rotator is None:
        return jsonify({"success": False, "error": "rotator not initialized"}), 500
    raw_accounts = rotator.list_accounts()
    accounts = []
    for acc in raw_accounts:
        sid = acc.get("slot_id") or acc.get("id")
        email = acc.get("email") or ""
        accounts.append({
            "slot_id": sid,
            "id": sid,
            "email": email,
            "username": email,
        })
    rotator_summary = {
        "total_accounts": len(accounts),
        "active_slots": rotator.size(),
    }
    return jsonify({
        "success": True,
        "accounts": accounts,
        "rotator_summary": rotator_summary,
    })


@admin_api_bp.route("/accounts", methods=["POST"])
@admin_token_required
def accounts_add():
    rotator = getattr(current_app, "rotator", None)
    qm = getattr(current_app, "queue_manager", None)
    if rotator is None or qm is None:
        return jsonify({"success": False, "error": "system not initialized"}), 500

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or body.get("username") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"success": False, "error": "email and password are required"}), 400

    if not current_app.config.get("TESTING") and not os.environ.get("SKIP_AUTH_TEST"):
        ok, err = rotator.test_login(email, password)
        if not ok:
            return jsonify({"success": False, "error": f"Login failed: {err}"}), 400

    slot_id = rotator.add(email, password)
    qm.add_worker(slot_id)
    _audit("account_add", "account", slot_id, before=None, after={"email": email})
    return jsonify({
        "success": True,
        "id": slot_id,
        "slot_id": slot_id,
        "email": email,
        "username": email,
    })


@admin_api_bp.route("/accounts/<slot_id>", methods=["DELETE"])
@admin_token_required
def accounts_remove(slot_id: str):
    rotator = getattr(current_app, "rotator", None)
    qm = getattr(current_app, "queue_manager", None)
    if rotator is None or qm is None:
        return jsonify({"success": False, "error": "system not initialized"}), 500

    actual_slot_id = slot_id
    if not rotator.has(actual_slot_id):
        for sid in rotator.list_ids():
            try:
                if rotator.email(sid).lower() == slot_id.lower():
                    actual_slot_id = sid
                    break
            except KeyError:
                continue

    if not rotator.has(actual_slot_id):
        return jsonify({"success": False, "error": "not found"}), 404
    if rotator.size() <= 1:
        return jsonify({"success": False, "error": "must keep at least 1 account"}), 400

    email = rotator.email(actual_slot_id)
    qm.remove_worker(actual_slot_id)
    rotator.remove(actual_slot_id)
    _audit("account_remove", "account", actual_slot_id, before={"email": email}, after=None)
    return jsonify({"success": True, "msg": f"Đã xóa tài khoản '{email}' khỏi pool."})


@admin_api_bp.route("/accounts/test", methods=["POST"])
@admin_token_required
def accounts_test():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or body.get("username") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"success": False, "error": "email and password are required"}), 400
    ok, err = AccountRotator.test_login(email, password)
    return jsonify({"success": ok, "error": err})


# ---- Tokens Store ----

@admin_api_bp.route("/tokens", methods=["GET"])
@admin_token_required
def tokens_list():
    raw_list = tokens_store.list()
    # STRICT REDACTION: Never return fetch_token, receipts, credentials, or private secrets
    safe_list = []
    for idx, item in enumerate(raw_list):
        payload = item.get("payload") if isinstance(item, dict) else {}
        if payload is None and isinstance(item, dict):
            payload = item
        if not isinstance(payload, dict):
            payload = {}
        prod_id = payload.get("product_id") or payload.get("product_identifier") or "com.locket.gold"
        account = payload.get("account") or payload.get("account_id") or item.get("account") or f"Token #{idx + 1}"
        exp = payload.get("expires_at") or payload.get("expiration_date_ms") or item.get("added_at")
        if isinstance(exp, (int, float)) and exp > 10_000_000_000:
            exp = exp / 1000

        safe_entry = {
            "index": idx,
            "product_identifier": prod_id,
            "account": account,
            "expires_at": exp,
            "added_at": item.get("added_at"),
            "status": "active",
        }
        safe_list.append(safe_entry)
    return jsonify({"success": True, "tokens": safe_list, "items": safe_list})


@admin_api_bp.route("/tokens", methods=["POST"])
@admin_token_required
def tokens_add():
    body = request.get_json(silent=True) or {}
    payload = body.get("payload")
    if payload is None:
        raw = body.get("raw")
        if not raw:
            return jsonify({"success": False, "error": "missing payload"}), 400
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            return jsonify({"success": False, "error": f"Invalid JSON: {e}"}), 400
    try:
        tokens_store.add(payload)
        _audit("token_add", "token", None, before=None, after={"added": True})
    except (ValueError, OSError) as e:
        current_app.logger.warning("Admin token add rejected: %s", type(e).__name__)
        return jsonify({"success": False, "error": "invalid_token_payload"}), 400
    return jsonify({"success": True})


@admin_api_bp.route("/tokens/<int:index>", methods=["DELETE"])
@admin_token_required
def tokens_remove(index: int):
    try:
        tokens_store.remove(index)
        _audit("token_remove", "token", index, before=None, after=None)
    except IndexError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    return jsonify({"success": True})


# ---- Proxies Pool ----

@admin_api_bp.route("/proxies", methods=["GET"])
@admin_token_required
def proxies_list():
    items = []
    for raw_item in proxy_pool.list_all():
        it = dict(raw_item)
        redacted_url = _redact_proxy(it.get("url", ""))
        it["url"] = redacted_url
        it["url_redacted"] = redacted_url
        items.append(it)
    return jsonify({
        "success": True,
        "master_enabled": proxy_pool.is_master_on(),
        "proxies": items,
        "items": items,
    })


@admin_api_bp.route("/proxies", methods=["POST"])
@admin_token_required
def proxies_add():
    body = request.get_json(silent=True) or {}
    raw = body.get("raw") or body.get("url") or body.get("proxy_url") or ""
    try:
        added = proxy_pool.add_many(raw)
        _audit("proxies_add", "proxy", None, before=None, after={"added": added})
    except ValueError as e:
        return jsonify({"success": False, "error": "invalid_proxy", "msg": "Proxy không hợp lệ."}), 400
    return jsonify({"success": True, "added": added})


@admin_api_bp.route("/proxies/<int:proxy_id>", methods=["PATCH"])
@admin_token_required
def proxies_patch(proxy_id: int):
    body = request.get_json(silent=True) or {}
    if "enabled" in body:
        enabled, bool_error = _json_bool(body, "enabled")
        if bool_error:
            return bool_error
        proxy_pool.set_enabled(proxy_id, enabled)
        _audit("proxy_toggle", "proxy", proxy_id, before=None, after={"enabled": enabled})
    return jsonify({"success": True})


@admin_api_bp.route("/proxies/<int:proxy_id>", methods=["DELETE"])
@admin_api_bp.route("/proxies/<path:proxy_ref>", methods=["DELETE"])
@admin_token_required
def proxies_remove(proxy_ref=None, proxy_id=None):
    ref = proxy_id if proxy_id is not None else proxy_ref
    if str(ref).isdigit():
        target_id = int(ref)
    else:
        # Search by url or redacted url
        all_p = proxy_pool.list_all()
        matching = [p for p in all_p if p["url"] == ref or _redact_proxy(p["url"]) == ref]
        if not matching:
            return jsonify({"success": False, "error": "not_found"}), 404
        target_id = matching[0]["id"]

    proxy_pool.remove(target_id)
    _audit("proxy_remove", "proxy", target_id, before=None, after=None)
    return jsonify({"success": True, "msg": "Đã xóa proxy thành công."})


@admin_api_bp.route("/proxies/<int:proxy_id>/test", methods=["POST"])
@admin_token_required
def proxies_test_one(proxy_id: int):
    rows = [r for r in proxy_pool.list_all() if r["id"] == proxy_id]
    if not rows:
        return jsonify({"success": False, "error": "not found"}), 404
    url = rows[0]["url"]
    try:
        resp = requests.post(
            "https://api.locketcamera.com/getUserByUsername",
            json={"data": {"username": "locket"}},
            proxies={"http": url, "https": url},
            timeout=15,
        )
        ok = resp.status_code < 500
        if ok:
            proxy_pool.mark_ok(proxy_id)
        else:
            proxy_pool.mark_err(proxy_id, f"HTTP {resp.status_code}")
        return jsonify({"success": ok, "status": resp.status_code})
    except Exception as e:
        proxy_pool.mark_err(proxy_id, type(e).__name__)
        current_app.logger.warning("Proxy test failed for proxy id %s: %s", proxy_id, type(e).__name__)
        return jsonify({"success": False, "error": "proxy_test_failed"}), 502


@admin_api_bp.route("/proxies/master", methods=["PUT"])
@admin_token_required
def proxies_master():
    body = request.get_json(silent=True) or {}
    if "enabled" not in body:
        return jsonify({"success": False, "error": "missing_enabled"}), 400
    enabled, bool_error = _json_bool(body, "enabled")
    if bool_error:
        return bool_error
    proxy_pool.set_master(enabled)
    _audit("proxy_master_toggle", "proxy", None, before=None, after={"master_enabled": enabled})
    return jsonify({"success": True, "master_enabled": proxy_pool.is_master_on()})



# ---- Mobileconfig Management ----

MAX_MOBILECONFIG_BYTES = 5 * 1024 * 1024
MOBILECONFIG_HISTORY_LIMIT = 20


def _mobileconfig_path():
    env_path = (os.getenv("MOBILECONFIG_PATH") or "").strip()
    if env_path:
        return env_path
    return "/var/lib/locket-gold/downloads/locket.mobileconfig"


def _record_mobileconfig_history(action, filename=None, size=None, signed=None):
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO mobileconfig_history (action, filename, size, signed, created_at) "
        "VALUES (?,?,?,?,?)",
        (action, filename, int(size) if size is not None else None, 1 if signed else 0, time.time()),
    )
    conn.execute(
        "DELETE FROM mobileconfig_history WHERE id NOT IN ("
        "SELECT id FROM mobileconfig_history ORDER BY id DESC LIMIT ?)",
        (MOBILECONFIG_HISTORY_LIMIT,),
    )


def _looks_like_mobileconfig(blob):
    if not blob:
        return False
    head = blob[:4096]
    if head.lstrip().startswith(b"<?xml") or b"<plist" in head:
        return True
    if blob[:1] == b"\x30":
        return b"<plist" in blob[:8192] or b"-//Apple//DTD PLIST" in blob[:8192]
    return False


@admin_api_bp.route("/mobileconfig", methods=["GET"])
@admin_token_required
def mobileconfig_info():
    path = _mobileconfig_path()
    if not os.path.exists(path):
        return jsonify({"success": True, "exists": False})
    st = os.stat(path)
    with open(path, "rb") as f:
        blob = f.read(8192)
    return jsonify({
        "success": True,
        "exists": True,
        "size": st.st_size,
        "modified_at": st.st_mtime,
        "signed": blob[:1] == b"\x30",
    })


@admin_api_bp.route("/mobileconfig", methods=["POST"])
@admin_token_required
def mobileconfig_upload():
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"success": False, "error": "Missing file"}), 400

    blob = f.read(MAX_MOBILECONFIG_BYTES + 1)
    if len(blob) == 0:
        return jsonify({"success": False, "error": "Empty file"}), 400
    if len(blob) > MAX_MOBILECONFIG_BYTES:
        return jsonify({"success": False, "error": "File too large (max 5 MB)"}), 400
    if not _looks_like_mobileconfig(blob):
        return jsonify({
            "success": False,
            "error": "File doesn't look like a .mobileconfig (no <plist> found)",
        }), 400

    target = _mobileconfig_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "wb") as out:
        out.write(blob)
    os.replace(tmp, target)
    os.chmod(target, 0o640)
    st = os.stat(target)
    signed = blob[:1] == b"\x30"
    _record_mobileconfig_history("upload", filename=f.filename, size=st.st_size, signed=signed)
    _audit("mobileconfig_upload", "mobileconfig", None, before=None, after={"filename": f.filename, "size": st.st_size})

    return jsonify({
        "success": True,
        "size": st.st_size,
        "modified_at": st.st_mtime,
    })


@admin_api_bp.route("/mobileconfig", methods=["DELETE"])
@admin_token_required
def mobileconfig_remove():
    path = _mobileconfig_path()
    existed = os.path.exists(path)
    if existed:
        os.remove(path)
        _record_mobileconfig_history("delete")
        _audit("mobileconfig_delete", "mobileconfig", None, before=None, after=None)
    return jsonify({"success": True})


@admin_api_bp.route("/mobileconfig/history", methods=["GET"])
@admin_token_required
def mobileconfig_history():
    rows = db.get_conn().execute(
        "SELECT id, action, filename, size, signed, created_at "
        "FROM mobileconfig_history ORDER BY id DESC LIMIT ?",
        (MOBILECONFIG_HISTORY_LIMIT,),
    ).fetchall()
    items = [
        {
            "id": r["id"],
            "action": r["action"],
            "filename": r["filename"],
            "size": r["size"],
            "signed": bool(r["signed"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return jsonify({"success": True, "items": items})


# ---- System Site Settings ----

@admin_api_bp.route("/popup", methods=["GET"])
@admin_token_required
def popup_get():
    return jsonify({"success": True, "popup": site_settings.get_popup()})


@admin_api_bp.route("/popup", methods=["PUT"])
@admin_token_required
def popup_set():
    body = request.get_json(silent=True) or {}
    old_popup = site_settings.get_popup()
    try:
        saved = site_settings.set_popup(body)
    except ValueError as exc:
        return jsonify({"success": False, "error": "validation_error", "msg": str(exc)}), 400
    _audit("popup_update", "setting", "popup", before=old_popup, after=saved)
    return jsonify({"success": True, "popup": saved})


@admin_api_bp.route("/maintenance", methods=["GET"])
@admin_token_required
def maintenance_get():
    return jsonify({"success": True, "maintenance": site_settings.get_maintenance()})


@admin_api_bp.route("/maintenance", methods=["PUT"])
@admin_token_required
def maintenance_set():
    body = request.get_json(silent=True) or {}
    for field in ("enabled", "allow_admin"):
        _, bool_error = _json_bool(body, field)
        if bool_error:
            return bool_error
    old_m = site_settings.get_maintenance()
    saved = site_settings.set_maintenance(body)
    _audit("maintenance_update", "setting", "maintenance", before=old_m, after=saved)
    return jsonify({"success": True, "maintenance": saved})


@admin_api_bp.route("/theme", methods=["GET"])
@admin_token_required
def theme_get():
    return jsonify({
        "success": True,
        "theme": site_settings.get_theme(),
        "available": list(site_settings.THEMES),
    })


@admin_api_bp.route("/theme", methods=["PUT"])
@admin_token_required
def theme_set():
    body = request.get_json(silent=True) or {}
    try:
        old_theme = site_settings.get_theme()
        saved = site_settings.set_theme(body)
        _audit("theme_update", "setting", "theme", before=old_theme, after=saved)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "theme": saved})


@admin_api_bp.route("/layout", methods=["GET"])
@admin_token_required
def layout_get():
    return jsonify({
        "success": True,
        "layout": site_settings.get_layout(),
        "available": list(site_settings.LAYOUTS),
    })


@admin_api_bp.route("/layout", methods=["PUT"])
@admin_token_required
def layout_set():
    body = request.get_json(silent=True) or {}
    try:
        old_layout = site_settings.get_layout()
        saved = site_settings.set_layout(body)
        _audit("layout_update", "setting", "layout", before=old_layout, after=saved)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "layout": saved})


# ---- Composite Site Settings API ----

@admin_api_bp.route("/site-settings", methods=["GET"])
@admin_token_required
def site_settings_get_composite():
    """Return all site settings (maintenance, popup, theme, layout) in a single response."""
    settings = {
        "maintenance": site_settings.get_maintenance(),
        "popup": site_settings.get_popup(),
        "theme": site_settings.get_theme(),
        "layout": site_settings.get_layout(),
    }
    return jsonify({"success": True, "settings": settings})


@admin_api_bp.route("/site-settings", methods=["POST", "PUT"])
@admin_token_required
def site_settings_set_composite():
    """Update multiple site settings sections in a single call."""
    data = request.get_json(silent=True) or {}
    updated = {}

    maint_payload = data.get("maintenance")
    if maint_payload is None and ("maintenance_mode" in data or "maintenance_enabled" in data or "enabled" in data):
        current_m = site_settings.get_maintenance()
        is_en = data.get("maintenance_mode") if "maintenance_mode" in data else (data.get("maintenance_enabled") if "maintenance_enabled" in data else data.get("enabled"))
        allow_adm = data.get("maintenance_allow_admin") if "maintenance_allow_admin" in data else current_m.get("allow_admin", True)
        msg = data.get("maintenance_message") or data.get("message") or current_m.get("message", "")
        maint_payload = dict(current_m)
        if not isinstance(is_en, bool) or not isinstance(allow_adm, bool):
            return jsonify({
                "success": False,
                "error": "invalid_boolean",
                "msg": "Maintenance flags must be JSON booleans (true/false).",
            }), 400
        maint_payload.update({
            "enabled": is_en,
            "allow_admin": allow_adm,
            "message": msg,
        })

    if maint_payload is not None:
        if not isinstance(maint_payload, dict):
            return jsonify({"success": False, "error": "invalid_maintenance"}), 400
        for field in ("enabled", "allow_admin"):
            _, bool_error = _json_bool(maint_payload, field)
            if bool_error:
                return bool_error
        old_m = site_settings.get_maintenance()
        saved_m = site_settings.set_maintenance(maint_payload)
        _audit("maintenance_update", "setting", "maintenance", before=old_m, after=saved_m)
        updated["maintenance"] = saved_m
    else:
        updated["maintenance"] = site_settings.get_maintenance()

    if "popup" in data:
        old_p = site_settings.get_popup()
        try:
            saved_p = site_settings.set_popup(data["popup"])
        except ValueError as exc:
            return jsonify({"success": False, "error": "validation_error", "msg": str(exc)}), 400
        _audit("popup_update", "setting", "popup", before=old_p, after=saved_p)
        updated["popup"] = saved_p
    else:
        updated["popup"] = site_settings.get_popup()

    if "theme" in data:
        old_t = site_settings.get_theme()
        saved_t = site_settings.set_theme(data["theme"])
        _audit("theme_update", "setting", "theme", before=old_t, after=saved_t)
        updated["theme"] = saved_t
    else:
        updated["theme"] = site_settings.get_theme()

    if "layout" in data:
        old_l = site_settings.get_layout()
        saved_l = site_settings.set_layout(data["layout"])
        _audit("layout_update", "setting", "layout", before=old_l, after=saved_l)
        updated["layout"] = saved_l
    else:
        updated["layout"] = site_settings.get_layout()

    return jsonify({"success": True, "settings": updated, "msg": "Đã lưu cài đặt hệ thống thành công."})


# ---- Audit Logs Query Endpoint ----

@admin_api_bp.route("/audit-logs", methods=["GET"])
@admin_token_required
def audit_logs_list():
    """List administrative audit logs with pagination and filters."""
    admin_id = request.args.get("admin_user_id") or request.args.get("admin_id")
    action = request.args.get("action")
    entity_type = request.args.get("entity_type")
    limit, offset = _parse_pagination(30)

    try:
        admin_id_int = int(admin_id) if admin_id else None
    except (ValueError, TypeError):
        admin_id_int = None

    logs = db.list_admin_audit_logs(
        admin_user_id=admin_id_int,
        action=action,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )

    return jsonify(make_list_envelope(logs["items"], logs["total"], limit, offset, legacy_key="logs"))


# ---- Coupons Management ----

@admin_api_bp.route("/coupons", methods=["GET"])
@admin_token_required
def coupons_list():
    search = request.args.get("search")
    status_filter = request.args.get("status")
    limit, offset = _parse_pagination(20)
    coupons, total = db.list_coupons(search=search, status_filter=status_filter, limit=limit, offset=offset)
    return jsonify(make_list_envelope(coupons, total, limit, offset, legacy_key="coupons"))


@admin_api_bp.route("/coupons", methods=["POST"])
@admin_token_required
def coupons_create():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    desc = (data.get("description") or "").strip()
    discount_type = (data.get("discount_type") or "").strip()
    raw_val = data.get("discount_value")
    raw_max = data.get("max_discount_vnd")
    raw_min = data.get("min_order_vnd", 0)
    raw_total_lim = data.get("usage_limit_total")
    raw_user_lim = data.get("usage_limit_per_user")
    starts_at = data.get("starts_at")
    ends_at = data.get("ends_at")
    is_active, bool_err = _json_bool(data, "is_active", default=True)
    if bool_err:
        return bool_err
    plan_ids = data.get("plan_ids") if "plan_ids" in data else data.get("applicable_plan_ids", [])

    starts_at_ts = None
    if starts_at:
        try:
            starts_at_ts = datetime.fromisoformat(str(starts_at).replace("Z", "+00:00")).timestamp()
        except Exception:
            try:
                starts_at_ts = float(starts_at)
            except Exception:
                return jsonify({"success": False, "error": "invalid_date", "msg": "Ngày bắt đầu không hợp lệ."}), 400

    ends_at_ts = None
    if ends_at:
        try:
            ends_at_ts = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00")).timestamp()
        except Exception:
            try:
                ends_at_ts = float(ends_at)
            except Exception:
                return jsonify({"success": False, "error": "invalid_date", "msg": "Ngày kết thúc không hợp lệ."}), 400

    admin_user_id = g.current_user["id"] if getattr(g, "current_user", None) else None
    try:
        created = db.create_coupon(
            code=code,
            name=name,
            discount_type=discount_type,
            discount_value=raw_val,
            description=desc,
            max_discount_vnd=raw_max,
            min_order_vnd=raw_min,
            usage_limit_total=raw_total_lim,
            usage_limit_per_user=raw_user_lim,
            starts_at=starts_at_ts,
            ends_at=ends_at_ts,
            is_active=is_active,
            plan_ids=plan_ids,
            admin_user_id=admin_user_id,
        )
        _audit("coupon_create", "coupon", created["id"], before=None, after=created)
        return jsonify({"success": True, "coupon": created, "msg": "Tạo mã giảm giá thành công."}), 201
    except ValueError as exc:
        return jsonify({"success": False, "error": "validation_error", "msg": str(exc)}), 400


@admin_api_bp.route("/coupons/<int:coupon_id>", methods=["GET"])
@admin_token_required
def coupons_get(coupon_id):
    coupon = db.get_coupon_by_id(coupon_id)
    if not coupon:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy mã giảm giá."}), 404
    return jsonify({"success": True, "coupon": coupon})


@admin_api_bp.route("/coupons/<int:coupon_id>", methods=["PUT"])
@admin_token_required
def coupons_update(coupon_id):
    current = db.get_coupon_by_id(coupon_id)
    if not current:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy mã giảm giá."}), 404

    data = request.get_json(silent=True) or {}
    name = data.get("name")
    desc = data.get("description")
    discount_type = data.get("discount_type")
    raw_val = data.get("discount_value")
    raw_max = data.get("max_discount_vnd")
    raw_min = data.get("min_order_vnd")
    raw_total_lim = data.get("usage_limit_total")
    raw_user_lim = data.get("usage_limit_per_user")
    starts_at = data.get("starts_at")
    ends_at = data.get("ends_at")
    is_active = None
    if "is_active" in data:
        is_active, bool_err = _json_bool(data, "is_active")
        if bool_err:
            return bool_err
    plan_ids = data.get("plan_ids") if "plan_ids" in data else (data.get("applicable_plan_ids") if "applicable_plan_ids" in data else None)

    starts_at_ts = None
    if starts_at is not None:
        if starts_at:
            try:
                starts_at_ts = datetime.fromisoformat(str(starts_at).replace("Z", "+00:00")).timestamp()
            except Exception:
                try:
                    starts_at_ts = float(starts_at)
                except Exception:
                    return jsonify({"success": False, "error": "invalid_date", "msg": "Ngày bắt đầu không hợp lệ."}), 400
        else:
            starts_at_ts = None

    ends_at_ts = None
    if ends_at is not None:
        if ends_at:
            try:
                ends_at_ts = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00")).timestamp()
            except Exception:
                try:
                    ends_at_ts = float(ends_at)
                except Exception:
                    return jsonify({"success": False, "error": "invalid_date", "msg": "Ngày kết thúc không hợp lệ."}), 400
        else:
            ends_at_ts = None

    try:
        updated = db.update_coupon(
            coupon_id=coupon_id,
            name=name,
            description=desc,
            discount_type=discount_type,
            discount_value=raw_val,
            max_discount_vnd=raw_max if "max_discount_vnd" in data else current["max_discount_vnd"],
            min_order_vnd=raw_min if "min_order_vnd" in data else current["min_order_vnd"],
            usage_limit_total=raw_total_lim if "usage_limit_total" in data else current["usage_limit_total"],
            usage_limit_per_user=raw_user_lim if "usage_limit_per_user" in data else current["usage_limit_per_user"],
            starts_at=starts_at_ts if starts_at is not None else current["starts_at"],
            ends_at=ends_at_ts if ends_at is not None else current["ends_at"],
            is_active=is_active,
            plan_ids=plan_ids,
        )
        _audit("coupon_update", "coupon", coupon_id, before=current, after=updated)
        return jsonify({"success": True, "coupon": updated, "msg": "Cập nhật mã giảm giá thành công."})
    except ValueError as exc:
        return jsonify({"success": False, "error": "validation_error", "msg": str(exc)}), 400


@admin_api_bp.route("/coupons/<int:coupon_id>/toggle", methods=["POST", "PATCH"])
@admin_token_required
def coupons_toggle(coupon_id):
    current = db.get_coupon_by_id(coupon_id)
    if not current:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy mã giảm giá."}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        is_active, bool_err = _json_bool(data, "is_active")
        if bool_err:
            return bool_err
    else:
        is_active = not bool(current["is_active"])

    updated = db.toggle_coupon_active(coupon_id, is_active)
    action = "coupon_enable" if is_active else "coupon_disable"
    _audit(action, "coupon", coupon_id, before=current, after=updated)
    return jsonify({"success": True, "coupon": updated, "is_active": bool(updated["is_active"]), "msg": f"Đã {'kích hoạt' if is_active else 'vô hiệu hóa'} mã giảm giá."})


@admin_api_bp.route("/coupons/<int:coupon_id>", methods=["DELETE"])
@admin_token_required
def coupons_delete(coupon_id):
    current = db.get_coupon_by_id(coupon_id)
    if not current:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy mã giảm giá."}), 404

    status, err_msg = db.delete_coupon(coupon_id)
    if status != "ok":
        return jsonify({"success": False, "error": status, "msg": err_msg}), 400

    _audit("coupon_delete", "coupon", coupon_id, before=current, after=None)
    return jsonify({"success": True, "msg": "Đã xóa mã giảm giá."})


@admin_api_bp.route("/coupons/<int:coupon_id>/stats", methods=["GET"])
@admin_token_required
def coupons_stats(coupon_id):
    stats = db.get_coupon_stats(coupon_id)
    if not stats:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy mã giảm giá."}), 404
    return jsonify({"success": True, "stats": stats, **stats})
