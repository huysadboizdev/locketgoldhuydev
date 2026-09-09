import json
import os
import secrets
import time

from flask import current_app, jsonify, make_response, redirect, render_template, request, session

import requests

from .. import db
from .. import payment_service
from .. import proxies as proxy_pool
from .. import site_settings
from ..rotator import AccountRotator
from ..tokens import tokens_store
from . import bp
from .auth import (
    admin_required,
    check_credentials,
    get_admin_csrf_token,
    is_admin_logged_in,
    validate_admin_csrf,
)


def _legacy_admin_audit_context():
    """Resolve the legacy session admin to the provisioned database admin."""
    username = (os.getenv("ADMIN_USERNAME") or "").strip()
    email = (os.getenv("ADMIN_EMAIL") or "").strip()
    admin = db.get_user_by_username(username) if username else None
    if not admin and email:
        admin = db.get_user_by_email(email)
    if not admin or admin.get("role") != "admin":
        return None
    return {
        "admin_user_id": admin["id"],
        "ip_address": request.remote_addr,
        "user_agent": request.headers.get("User-Agent", "")[:255],
    }


@bp.before_request
def enforce_admin_csrf_and_auth():
    """Enforce admin CSRF validation on all mutating API calls under /admin/api/."""
    if request.path.startswith("/admin/api/"):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if not is_admin_logged_in():
                return jsonify({"success": False, "error": "unauthorized"}), 401
            if not validate_admin_csrf():
                return jsonify({
                    "success": False,
                    "error": "invalid_csrf_token",
                    "msg": "Mã CSRF quản trị không hợp lệ hoặc đã hết hạn. Vui lòng tải lại trang.",
                }), 403


@bp.after_request
def add_admin_security_headers(response):
    """Never cache admin panel data."""
    response.headers["Cache-Control"] = "private, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if is_admin_logged_in():
            return redirect("/admin/")
        return render_template("admin_login.html", error=None)

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    if not check_credentials(username, password):
        return render_template("admin_login.html", error="Invalid username or password"), 401
    session.clear()
    session["admin"] = True
    session["admin_csrf_token"] = secrets.token_hex(32)
    return redirect("/admin/")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/admin/login")


@bp.route("/")
@admin_required
def dashboard():
    return render_template("admin.html", admin_csrf_token=get_admin_csrf_token())


# ---- accounts ----


@bp.route("/api/accounts", methods=["GET"])
@admin_required
def accounts_list():
    rotator = current_app.rotator
    if rotator is None:
        return jsonify({"success": False, "error": "rotator not initialized"}), 500
    return jsonify({"success": True, "accounts": rotator.list_accounts()})


@bp.route("/api/accounts", methods=["POST"])
@admin_required
def accounts_add():
    rotator = current_app.rotator
    if rotator is None:
        return jsonify({"success": False, "error": "rotator not initialized"}), 500

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"success": False, "error": "email and password are required"}), 400

    ok, err = rotator.test_login(email, password)
    if not ok:
        return jsonify({"success": False, "error": f"Login failed: {err}"}), 400

    slot_id = rotator.add(email, password)
    current_app.queue_manager.add_worker(slot_id)
    return jsonify({"success": True, "id": slot_id, "email": email})


@bp.route("/api/accounts/<slot_id>", methods=["DELETE"])
@admin_required
def accounts_remove(slot_id):
    rotator = current_app.rotator
    if rotator is None:
        return jsonify({"success": False, "error": "rotator not initialized"}), 500
    if not rotator.has(slot_id):
        return jsonify({"success": False, "error": "not found"}), 404
    if rotator.size() <= 1:
        return jsonify({"success": False, "error": "must keep at least 1 account"}), 400
    current_app.queue_manager.remove_worker(slot_id)
    rotator.remove(slot_id)
    return jsonify({"success": True})


@bp.route("/api/accounts/test", methods=["POST"])
@admin_required
def accounts_test():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"success": False, "error": "email and password are required"}), 400
    ok, err = AccountRotator.test_login(email, password)
    return jsonify({"success": ok, "error": err})


# ---- tokens ----


@bp.route("/api/tokens", methods=["GET"])
@admin_required
def tokens_list():
    safe_list = []
    for index, item in enumerate(tokens_store.list()):
        payload = item.get("payload") if isinstance(item, dict) else None
        if not isinstance(payload, dict):
            payload = item if isinstance(item, dict) else {}
        expires_at = payload.get("expires_at") or payload.get("expiration_date_ms")
        if isinstance(expires_at, (int, float)) and expires_at > 10_000_000_000:
            expires_at = expires_at / 1000
        safe_list.append({
            "index": index,
            "product_identifier": payload.get("product_id") or payload.get("product_identifier") or "com.locket.gold",
            "account": payload.get("account") or payload.get("account_id") or f"Token #{index + 1}",
            "expires_at": expires_at,
            "status": "active",
        })
    return jsonify({"success": True, "tokens": safe_list})


@bp.route("/api/tokens", methods=["POST"])
@admin_required
def tokens_add():
    body = request.get_json(silent=True) or {}
    payload = body.get("payload")
    if payload is None:
        # Allow raw JSON in a "raw" string field (UI textarea convenience).
        raw = body.get("raw")
        if not raw:
            return jsonify({"success": False, "error": "missing payload"}), 400
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            return jsonify({"success": False, "error": f"Invalid JSON: {e}"}), 400
    try:
        tokens_store.add(payload)
    except (ValueError, OSError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True})


@bp.route("/api/tokens/<int:index>", methods=["DELETE"])
@admin_required
def tokens_remove(index):
    try:
        tokens_store.remove(index)
    except IndexError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    return jsonify({"success": True})


# ---- queue ----


# ---- popup + maintenance ----


@bp.route("/api/popup", methods=["GET"])
@admin_required
def popup_get():
    return jsonify({"success": True, "popup": site_settings.get_popup()})


@bp.route("/api/popup", methods=["PUT"])
@admin_required
def popup_set():
    body = request.get_json(silent=True) or {}
    try:
        saved = site_settings.set_popup(body)
    except ValueError as exc:
        return jsonify({"success": False, "error": "validation_error", "msg": str(exc)}), 400
    return jsonify({"success": True, "popup": saved})


@bp.route("/api/maintenance", methods=["GET"])
@admin_required
def maintenance_get():
    return jsonify({"success": True, "maintenance": site_settings.get_maintenance()})


@bp.route("/api/maintenance", methods=["PUT"])
@admin_required
def maintenance_set():
    body = request.get_json(silent=True) or {}
    saved = site_settings.set_maintenance(body)
    return jsonify({"success": True, "maintenance": saved})


@bp.route("/api/theme", methods=["GET"])
@admin_required
def theme_get():
    return jsonify({
        "success": True,
        "theme": site_settings.get_theme(),
        "available": list(site_settings.THEMES),
    })


@bp.route("/api/theme", methods=["PUT"])
@admin_required
def theme_set():
    body = request.get_json(silent=True) or {}
    try:
        saved = site_settings.set_theme(body)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "theme": saved})


@bp.route("/api/layout", methods=["GET"])
@admin_required
def layout_get():
    return jsonify({
        "success": True,
        "layout": site_settings.get_layout(),
        "available": list(site_settings.LAYOUTS),
    })


@bp.route("/api/layout", methods=["PUT"])
@admin_required
def layout_set():
    body = request.get_json(silent=True) or {}
    try:
        saved = site_settings.set_layout(body)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "layout": saved})


# ---- proxies ----


def _redact(url):
    # Hide password in user:pass@host
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


@bp.route("/api/proxies", methods=["GET"])
@admin_required
def proxies_list():
    items = []
    for raw_item in proxy_pool.list_all():
        it = dict(raw_item)
        redacted_url = _redact(it.get("url", ""))
        it["url"] = redacted_url
        it["url_redacted"] = redacted_url
        items.append(it)
    return jsonify({
        "success": True,
        "master_enabled": proxy_pool.is_master_on(),
        "items": items,
    })


@bp.route("/api/proxies", methods=["POST"])
@admin_required
def proxies_add():
    body = request.get_json(silent=True) or {}
    raw = body.get("raw") or body.get("url") or ""
    try:
        added = proxy_pool.add_many(raw)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "added": added})


@bp.route("/api/proxies/<int:proxy_id>", methods=["PATCH"])
@admin_required
def proxies_patch(proxy_id):
    body = request.get_json(silent=True) or {}
    if "enabled" in body:
        if not isinstance(body["enabled"], bool):
            return jsonify({"success": False, "error": "invalid_boolean"}), 400
        proxy_pool.set_enabled(proxy_id, body["enabled"])
    return jsonify({"success": True})


@bp.route("/api/proxies/<int:proxy_id>", methods=["DELETE"])
@admin_required
def proxies_remove(proxy_id):
    proxy_pool.remove(proxy_id)
    return jsonify({"success": True})


@bp.route("/api/proxies/<int:proxy_id>/test", methods=["POST"])
@admin_required
def proxies_test_one(proxy_id):
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
        current_app.logger.warning("Legacy proxy test failed for id %s: %s", proxy_id, type(e).__name__)
        return jsonify({"success": False, "error": "proxy_test_failed"}), 502


@bp.route("/api/proxies/master", methods=["PUT"])
@admin_required
def proxies_master():
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("enabled"), bool):
        return jsonify({"success": False, "error": "invalid_boolean"}), 400
    proxy_pool.set_master(body["enabled"])
    return jsonify({"success": True, "master_enabled": proxy_pool.is_master_on()})


# ---- mobileconfig upload ----


MAX_MOBILECONFIG_BYTES = 5 * 1024 * 1024  # 5 MB ceiling
MOBILECONFIG_HISTORY_LIMIT = 20


def _mobileconfig_path():
    static_dir = os.path.join(current_app.root_path, "static")
    return os.path.join(static_dir, "locket.mobileconfig")


def _record_mobileconfig_history(action, filename=None, size=None, signed=None):
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO mobileconfig_history (action, filename, size, signed, created_at) "
        "VALUES (?,?,?,?,?)",
        (
            action,
            filename,
            int(size) if size is not None else None,
            1 if signed else 0,
            time.time(),
        ),
    )
    # Trim to most-recent N rows so the log doesn't grow unbounded.
    conn.execute(
        "DELETE FROM mobileconfig_history WHERE id NOT IN ("
        "SELECT id FROM mobileconfig_history ORDER BY id DESC LIMIT ?)",
        (MOBILECONFIG_HISTORY_LIMIT,),
    )


def _looks_like_mobileconfig(blob):
    """Accept either a plain XML plist or a CMS/PKCS7-signed .mobileconfig.
    Plain plists start with "<?xml". Signed ones are DER bags whose payload
    contains '<plist' somewhere in the first 4KB."""
    if not blob:
        return False
    head = blob[:4096]
    if head.lstrip().startswith(b"<?xml") or b"<plist" in head:
        return True
    # PKCS7 / signed mobileconfig: DER seq starts with 0x30 0x82 (or 0x30 0x80)
    if blob[:1] == b"\x30":
        return b"<plist" in blob[:8192] or b"-//Apple//DTD PLIST" in blob[:8192]
    return False


@bp.route("/api/mobileconfig", methods=["GET"])
@admin_required
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


@bp.route("/api/mobileconfig", methods=["POST"])
@admin_required
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
    st = os.stat(target)
    signed = blob[:1] == b"\x30"
    _record_mobileconfig_history(
        "upload",
        filename=f.filename,
        size=st.st_size,
        signed=signed,
    )
    return jsonify({
        "success": True,
        "size": st.st_size,
        "modified_at": st.st_mtime,
    })


@bp.route("/api/mobileconfig", methods=["DELETE"])
@admin_required
def mobileconfig_remove():
    path = _mobileconfig_path()
    existed = os.path.exists(path)
    if existed:
        os.remove(path)
        _record_mobileconfig_history("delete")
    return jsonify({"success": True})


@bp.route("/api/mobileconfig/history", methods=["GET"])
@admin_required
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


@bp.route("/api/queue", methods=["GET"])
@admin_required
def queue_snapshot():
    qm = current_app.queue_manager
    rotator = current_app.rotator
    snap = qm.admin_snapshot()
    worker_emails = {}
    for slot_id in list(qm.workers.keys()):
        try:
            worker_emails[slot_id] = rotator.email(slot_id) if rotator else "<no rotator>"
        except KeyError:
            worker_emails[slot_id] = "<removed>"
    return jsonify({"success": True, "workers": worker_emails, **snap})



# ---- Reviews Moderation ----

@bp.route("/api/reviews", methods=["GET"])
@admin_required
def admin_reviews_list():
    status = request.args.get("status", "all")
    reviews = db.list_reviews_admin(status=status, limit=200)
    for r in reviews:
        for img in r.get("images", []):
            img["url"] = f"/admin/api/reviews/images/{img['storage_name']}"
    resp = make_response(jsonify({"success": True, "reviews": reviews}))
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@bp.route("/api/reviews/<int:review_id>/status", methods=["POST", "PATCH"])
@admin_required
def admin_review_set_status(review_id):
    # Compatibility tombstone for the retired moderation workflow.
    return jsonify({
        "success": False,
        "error": "review_moderation_disabled",
        "msg": "Đánh giá được đăng tự động; quản trị viên chỉ có thể xem hoặc xóa.",
    }), 410


@bp.route("/api/reviews/<int:review_id>", methods=["DELETE"])
@admin_required
def admin_review_delete(review_id):
    from ..image_storage import delete_stored_image
    from ..reviews import get_storage_root, invalidate_reviews_cache
    storage_root = get_storage_root()
    storage_names = db.delete_review(review_id)
    if storage_names is None:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy đánh giá cần xóa."}), 404

    for name in storage_names:
        delete_stored_image(name, storage_root, "review")

    invalidate_reviews_cache()
    return jsonify({"success": True, "msg": "Đã xóa đánh giá thành công."})


@bp.route("/api/reviews/images/<storage_name>", methods=["GET"])
@admin_required
def admin_review_image(storage_name):
    from flask import abort
    from ..image_storage import serve_stored_image
    from ..reviews import SAFE_FILENAME_REGEX, get_storage_root

    if not SAFE_FILENAME_REGEX.match(storage_name):
        abort(404)

    # Strictly check that the image record exists in the database
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


# ---- Plans Management ----

@bp.route("/api/plans", methods=["GET"])
@admin_required
def admin_plans_list():
    """List all plans for admin management."""
    plans = db.list_all_plans_admin()
    return jsonify({"success": True, "plans": plans})


@bp.route("/api/plans", methods=["POST"])
@admin_required
def admin_plans_create():
    """Create a new service plan."""
    data = request.json or {}
    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip().lower()
    short_description = (data.get("short_description") or data.get("description") or "").strip()
    product_id = (data.get("product_id") or slug or "").strip()
    raw_duration = data.get("duration_days", 30)
    raw_price = data.get("price_vnd")
    if raw_price is None and "price_coin" in data:
        raw_price = int(data["price_coin"]) * 1000
    features = data.get("features", [])
    supported_platforms = data.get("supported_platforms") or data.get("platform") or "all"
    is_active = data.get("is_active", 1)
    is_popular = data.get("is_popular", 0)
    sort_order = data.get("sort_order", 0)
    inventory_status = data.get("inventory_status", "in_stock")

    if not name or not slug or not product_id:
        return jsonify({"success": False, "error": "validation_error", "msg": "Tên, slug và product ID là bắt buộc."}), 400

    try:
        duration_days = int(raw_duration)
        price_vnd = int(raw_price)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "validation_error", "msg": "Thời hạn và giá VNĐ phải là số nguyên."}), 400

    if price_vnd <= 0 or price_vnd % 1000 != 0:
        return jsonify({"success": False, "error": "chia hết cho 1.000", "msg": "Giá VNĐ phải là số nguyên dương chia hết cho 1.000."}), 400

    if supported_platforms not in ("all", "ios", "android"):
        return jsonify({"success": False, "error": "Nền tảng không hợp lệ", "msg": "Nền tảng hỗ trợ phải là all, ios hoặc android."}), 400

    try:
        plan_id = db.create_plan(
            name=name,
            slug=slug,
            short_description=short_description,
            duration_days=duration_days,
            price_vnd=price_vnd,
            product_id=product_id,
            features=features,
            supported_platforms=supported_platforms,
            is_active=1 if is_active else 0,
            is_popular=1 if is_popular else 0,
            sort_order=int(sort_order),
            inventory_status=inventory_status,
        )
        created = db.get_plan_by_id(plan_id, public=False)
        return jsonify({"success": True, "plan": created})
    except Exception as e:
        current_app.logger.exception("Legacy admin plan creation failed")
        return jsonify({"success": False, "error": "plan_create_failed", "msg": "Không thể tạo gói."}), 400


@bp.route("/api/plans/<int:plan_id>", methods=["PUT"])
@admin_required
def admin_plans_update(plan_id):
    """Update plan attributes."""
    data = request.json or {}
    try:
        ok = db.update_plan(plan_id, **data)
        if not ok:
            return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy gói cần cập nhật."}), 404
        updated = db.get_plan_by_id(plan_id, public=False)
        return jsonify({"success": True, "plan": updated})
    except ValueError as e:
        return jsonify({"success": False, "error": "validation_error", "msg": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Legacy admin plan update failed for plan %s", plan_id)
        return jsonify({"success": False, "error": "plan_update_failed", "msg": "Không thể cập nhật gói."}), 400


@bp.route("/api/plans/<int:plan_id>", methods=["DELETE"])
@admin_required
def admin_plans_delete(plan_id):
    """Delete a plan."""
    ok = db.delete_plan(plan_id)
    if not ok:
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy gói cần xóa."}), 404
    return jsonify({"success": True, "msg": "Đã xóa gói thành công."})


# ---- Payments Management ----

@bp.route("/api/payments", methods=["GET"])
@admin_required
def admin_payments_list():
    """List payment orders with optional filtering."""
    status = request.args.get("status")
    query = request.args.get("query")
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)
    payments = db.list_payment_orders_admin(status=status, query=query, limit=limit, offset=offset)
    return jsonify({"success": True, "payments": payments})


@bp.route("/api/payments/<payment_ref>/confirm", methods=["POST"])
@admin_required
def admin_payment_confirm(payment_ref):
    """Confirm a pending payment with bank transaction ID."""
    data = request.get_json(silent=True) or {}
    bank_tx_id = (data.get("bank_transaction_id") or "").strip()
    target_id_or_ref = int(payment_ref) if str(payment_ref).isdigit() else payment_ref

    status, res = payment_service.confirm_payment(
        payment_id_or_ref=target_id_or_ref,
        bank_transaction_id=bank_tx_id,
        current_app_instance=current_app._get_current_object(),
        audit_context=_legacy_admin_audit_context(),
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
        "msg": "Đã xác nhận thanh toán thành công!"
    })


@bp.route("/api/payments/<payment_ref>/reject", methods=["POST"])
@admin_required
def admin_payment_reject(payment_ref):
    """Reject a pending payment (mark cancelled)."""
    target_id_or_ref = int(payment_ref) if str(payment_ref).isdigit() else payment_ref
    status, res = payment_service.reject_payment(
        payment_id_or_ref=target_id_or_ref,
        status="cancelled",
        audit_context=_legacy_admin_audit_context(),
    )
    if status == "not_found":
        return jsonify({"success": False, "error": "not_found", "msg": "Không tìm thấy giao dịch thanh toán."}), 404
    if status != "ok":
        return jsonify({"success": False, "error": "reject_failed", "msg": f"Từ chối thất bại: {res}"}), 400

    return jsonify({"success": True, "msg": "Đã từ chối đơn thanh toán."})


# ---- Wallets Adjustment ----

@bp.route("/api/wallets/adjust", methods=["POST"])
@admin_required
def admin_wallet_adjust():
    """Manually adjust a user's Coin balance with audit ledger."""
    data = request.json or {}
    raw_user_id = data.get("user_id")
    raw_amount = data.get("amount_coin")
    reason = (data.get("reason") or "").strip()

    if not raw_user_id or raw_amount is None:
        return jsonify({"success": False, "error": "validation_error", "msg": "user_id và amount_coin là bắt buộc."}), 400
    if not reason:
        return jsonify({"success": False, "error": "reason_required", "msg": "Lý do điều chỉnh số dư là bắt buộc để ghi audit log."}), 400

    try:
        user_id = int(raw_user_id)
        amount_coin = int(raw_amount)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "validation_error", "msg": "user_id và amount_coin phải là số nguyên."}), 400

    audit_context = _legacy_admin_audit_context()
    if not audit_context:
        return jsonify({"success": False, "error": "admin_identity_unavailable"}), 500

    idempotency_key = f"admin_adj_{user_id}_{int(time.time()*1000)}"
    status, res = db.admin_adjust_user_wallet_atomic(
        user_id=user_id,
        amount_coin=amount_coin,
        reason=reason,
        admin_user_id=audit_context["admin_user_id"],
        idempotency_key=idempotency_key,
        ip_address=audit_context.get("ip_address"),
        user_agent=audit_context.get("user_agent"),
    )

    if status == "insufficient_balance":
        return jsonify({"success": False, "error": "insufficient_balance", "msg": "Số dư không đủ để trừ số Coin này."}), 400
    if status == "error":
        return jsonify({"success": False, "error": "adjustment_failed", "msg": str(res)}), 400

    return jsonify({"success": True, "transaction": res, "msg": "Đã điều chỉnh số dư ví thành công."})


