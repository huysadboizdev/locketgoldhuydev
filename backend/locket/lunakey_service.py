"""LunaKey business orchestration.

This module owns the glue between the HTTP layer, the durable ``provider_jobs``
outbox and the LunaKey client. It deliberately contains no Flask imports so it
can be unit tested directly.

Money state, order state and provider-job state are three separate concepts:

- money state  -> ``payment_orders.status`` / ``wallet_transactions``
- order state  -> ``activation_orders.status`` (CHECK-constrained, unchanged)
- job state    -> ``provider_jobs.status`` (pending/leased/succeeded/failed/
                  awaiting_reconciliation/cancelled)

The order state machine is never extended with provider-specific statuses.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import secrets
import time

from . import db
from .providers import lunakey

PROVIDER_LUNAKEY = "lunakey"
PROVIDER_LEGACY = "legacy_locket"

LOOKUP_TOKEN_TTL_SECONDS = 15 * 60
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_LEASE_SECONDS = 120
BASE_BACKOFF_SECONDS = 15
MAX_BACKOFF_SECONDS = 15 * 60

# site_settings key holding the operator-controlled pause switch.
STATE_KEY = "lunakey_state"


class ProviderError(Exception):
    """Normalized provider-facing error with a customer-safe message."""

    def __init__(self, code, message, *, http_status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def plan_provider(plan):
    return (plan or {}).get("activation_provider") or PROVIDER_LEGACY


def idempotency_window_seconds():
    """Confirmed provider idempotency window, or 0 when it is not confirmed.

    0 means "unknown": an unclear outcome must NOT be automatically replayed;
    it goes to reconciliation instead.
    """
    raw = (os.getenv("LUNAKEY_IDEMPOTENCY_WINDOW_SECONDS") or "").strip()
    try:
        value = int(raw) if raw else 0
    except (TypeError, ValueError):
        value = 0
    return max(0, min(value, 30 * 24 * 3600))


def plan_readiness(plan, client=None):
    """Return a list of reasons a plan cannot be sold yet (empty = sellable)."""
    issues = []
    if plan_provider(plan) != PROVIDER_LUNAKEY:
        return issues
    if not plan.get("provider_category"):
        issues.append("provider_category_missing")
    if plan.get("warranty_months") and not plan.get("warranty_policy"):
        issues.append("warranty_policy_missing")
    if not lunakey.is_configured():
        issues.append("api_key_missing")
    elif not lunakey.is_enabled():
        issues.append("provider_disabled")
    elif is_provider_paused():
        # A paused provider (e.g. after a 401) must not take new orders.
        issues.append("provider_paused")
    return issues


def is_plan_sellable(plan):
    return not plan_readiness(plan)


def _state():
    row = db.get_conn().execute(
        "SELECT value FROM site_settings WHERE key = ?", (STATE_KEY,)
    ).fetchone()
    if not row:
        return {"paused": False, "reason": None}
    try:
        data = json.loads(row["value"])
    except (ValueError, TypeError):
        return {"paused": False, "reason": None}
    if not isinstance(data, dict):
        return {"paused": False, "reason": None}
    return {"paused": bool(data.get("paused")), "reason": data.get("reason")}


def _write_state(state):
    db.get_conn().execute(
        "INSERT INTO site_settings (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (STATE_KEY, json.dumps(state), time.time()),
    )


def is_provider_paused():
    return _state().get("paused", False)


def pause_provider(reason):
    state = {"paused": True, "reason": (reason or "auth")[:200]}
    _write_state(state)
    return state


def resume_provider():
    state = {"paused": False, "reason": None}
    _write_state(state)
    return state


def get_provider_status():
    """Admin-safe status. Never exposes the API key or any secret."""
    state = _state()
    conn = db.get_conn()
    counts = {}
    for row in conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM provider_jobs GROUP BY status"
    ).fetchall():
        counts[row["status"]] = row["cnt"]
    try:
        host = lunakey.get_base_url()
    except lunakey.LunaKeyError:
        host = None
    return {
        "provider": PROVIDER_LUNAKEY,
        "configured": lunakey.is_configured(),
        "enabled": lunakey.is_enabled(),
        "paused": state.get("paused", False),
        "paused_reason": state.get("reason"),
        "base_host": host,
        "jobs": counts,
    }


# ---- Lookup + server-side confirmation -----------------------------------

def lookup_and_confirm(user_id, plan, username, client=None):
    """Look up a profile and persist a server-side confirmation token.

    The purchase endpoint trusts only the UID stored here, never a UID sent by
    the browser. Returns ``(token, normalized_profile)``.
    """
    issues = plan_readiness(plan, client)
    if issues:
        if "api_key_missing" in issues:
            code = "provider_not_configured"
        elif "provider_paused" in issues:
            code = "provider_paused"
        elif "provider_disabled" in issues:
            code = "provider_disabled"
        else:
            code = "plan_not_configured"
        raise ProviderError(code, lunakey.public_message(code), http_status=503)

    # Accept a plain username, "@handle" or a profile link such as
    # https://locket.cam/<handle>. The provider lookup expects the handle, so
    # extract it (preserving case) before calling upstream.
    raw = db.normalize_locket_username(username, lower=False)
    if not raw:
        raise ProviderError("username_required", "Vui lòng nhập tài khoản hoặc link Locket.")

    provider = plan_provider(plan)
    if provider != PROVIDER_LUNAKEY:
        raise ProviderError("invalid_provider", "Gói này không dùng nguồn LunaKey.")

    active_client = client or lunakey.LunaKeyClient()
    try:
        profile = active_client.lookup(raw)
    except lunakey.LunaKeyInvalidRequestError as exc:
        raise ProviderError("lookup_not_found", exc.message, http_status=404)
    except lunakey.LunaKeyConfigError as exc:
        raise ProviderError("provider_not_configured", exc.message, http_status=503)
    except lunakey.LunaKeyError as exc:
        # Never surface raw upstream details.
        raise ProviderError("lookup_failed", lunakey.public_message("lookup_failed"), http_status=502)

    if not profile or not profile.get("uid"):
        raise ProviderError("lookup_not_found", lunakey.public_message("lookup_not_found"), http_status=404)

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.create_provider_lookup(
        token_hash=token_hash,
        provider=PROVIDER_LUNAKEY,
        user_id=user_id,
        plan_id=plan["id"],
        username=profile.get("username") or raw,
        uid=profile.get("uid"),
        profile_json=json.dumps(profile, ensure_ascii=False),
        expires_at=time.time() + LOOKUP_TOKEN_TTL_SECONDS,
    )
    return token, profile


def consume_confirmation(user_id, plan_id, token):
    if not token:
        return None
    token_hash = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
    row = db.consume_provider_lookup(token_hash, user_id, plan_id)
    if not row:
        return None
    profile = None
    try:
        profile = json.loads(row.get("profile_json") or "null")
    except (ValueError, TypeError):
        profile = None
    row["profile"] = profile
    return row


# ---- Durable job creation ------------------------------------------------

def _provider_payload(order):
    user = (order.get("provider_username") or order.get("locket_username") or "").strip()
    category = (order.get("provider_category_snapshot") or "").strip()
    return user, category


def ensure_provider_job_for_order(order_id, max_attempts=None):
    """Create (or reuse) the single durable job for a provider order.

    The request_id and payload are derived once from the order snapshot and are
    then immutable. Admin edits to the plan/username never change them.
    """
    order = db.get_activation_order_by_id(order_id)
    if not order:
        return None
    provider = order.get("activation_provider_snapshot") or PROVIDER_LEGACY
    if provider != PROVIDER_LUNAKEY:
        return None

    existing = db.get_provider_job_by_order(order_id)
    if existing:
        return existing

    user, category = _provider_payload(order)
    if not user or not category:
        raise ProviderError("order_not_configured", "Đơn thiếu thông tin để gửi nguồn kích hoạt.")

    request_id = order.get("provider_request_id") or lunakey.new_request_id(order_id)
    payload = {"user": user, "category": category, "request_id": request_id, "confirm": True}
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    payload_hash = lunakey.payload_hash(user, category, request_id)

    attempts = max_attempts or int(os.getenv("LUNAKEY_MAX_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS)) or DEFAULT_MAX_ATTEMPTS)
    job_id = db.create_provider_job(
        order_id=order_id,
        provider=PROVIDER_LUNAKEY,
        provider_request_id=request_id,
        payload_hash=payload_hash,
        payload_json=payload_json,
        max_attempts=max(1, min(attempts, 20)),
    )

    # Persist the immutable request id on the order for support/reconciliation.
    conn = db.get_conn()
    conn.execute(
        """UPDATE activation_orders
              SET provider_request_id = COALESCE(provider_request_id, ?),
                  provider_username = COALESCE(provider_username, ?),
                  updated_at = ?
            WHERE id = ?""",
        (request_id, user, time.time(), order_id),
    )
    conn.commit()
    return db.get_provider_job_by_id(job_id)


def dispatch_provider_order(order_id, app=None):
    """Enqueue the provider job for a paid order. Idempotent."""
    order = db.get_activation_order_by_id(order_id)
    if not order:
        return ("not_found", "Không tìm thấy đơn kích hoạt.")
    try:
        job = ensure_provider_job_for_order(order_id)
    except ProviderError as exc:
        return ("job_error", {"order": order, "error": exc.code, "msg": exc.message})
    refreshed = db.get_activation_order_by_id(order_id) or order
    result = dict(refreshed)
    if job:
        result["provider_job_status"] = job.get("status")
    return ("ok", result)


def recover_missing_provider_jobs(limit=50):
    """Create jobs for paid provider orders that never got one (crash recovery)."""
    rows = db.get_conn().execute(
        """SELECT o.id FROM activation_orders o
            LEFT JOIN provider_jobs j ON j.order_id = o.id
            WHERE o.activation_provider_snapshot = 'lunakey'
              AND o.status IN ('paid', 'awaiting_queue')
              AND j.id IS NULL
            ORDER BY o.id ASC LIMIT ?""",
        (int(limit),),
    ).fetchall()
    created = 0
    for row in rows:
        try:
            if ensure_provider_job_for_order(row["id"]):
                created += 1
        except ProviderError:
            continue
    return created


# ---- Retry scheduling ----------------------------------------------------

def compute_backoff(attempt_count):
    attempt = max(1, int(attempt_count or 1))
    return min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))


def next_attempt_time(attempt_count, now=None):
    base = time.time() if now is None else now
    return base + compute_backoff(attempt_count)


# ---- Customer-safe order projection --------------------------------------

_INTERNAL_ORDER_FIELDS = (
    "provider_price_deducted",
    "provider_currency",
    "provider_balance_snapshot",
    "provider_balance_at",
    "provider_order_code",
    "provider_request_id",
    "provider_last_error_code",
    "provider_last_error_msg",
    "provider_profile_json",
    "provider_uid",
)

PROVIDER_STATUS_LABELS = {
    "verifying": "Đang xác minh",
    "awaiting_payment": "Chờ thanh toán",
    "processing": "Đã thanh toán, đang xử lý",
    "awaiting_reconciliation": "Đang kiểm tra kết quả",
    "completed": "Thành công",
    "failed": "Thất bại",
    "refunded": "Đã hoàn tiền",
    "cancelled": "Đã hủy",
    "manual_contact": "Chờ admin liên hệ",
    "apk_download": "Sẵn sàng tải",
}


def derive_provider_status(order, job=None):
    if not order:
        return None
    provider = order.get("activation_provider_snapshot") or PROVIDER_LEGACY
    if provider != PROVIDER_LUNAKEY:
        return None
    order_status = order.get("status")
    job_status = (job or {}).get("status")
    if job_status == "awaiting_reconciliation":
        return "awaiting_reconciliation"
    if order_status == "completed":
        return "completed"
    if order_status in ("failed",):
        return "failed"
    if order_status == "refunded":
        return "refunded"
    if order_status == "cancelled":
        return "cancelled"
    if order_status == "awaiting_payment":
        return "awaiting_payment"
    if order_status in ("paid", "awaiting_queue", "queued", "processing"):
        return "processing"
    return order_status


def redact_order_for_customer(order, job=None):
    """Strip internal cost/error/upstream fields before returning to a customer."""
    if not order:
        return order
    safe = dict(order)
    for field in _INTERNAL_ORDER_FIELDS:
        safe.pop(field, None)
    provider = safe.get("activation_provider_snapshot") or PROVIDER_LEGACY
    safe["provider"] = provider
    if provider == PROVIDER_LUNAKEY:
        status = derive_provider_status(order, job)
        safe["provider_status"] = status
        safe["provider_status_label"] = PROVIDER_STATUS_LABELS.get(status, status)
        profile = None
        try:
            profile = json.loads(order.get("provider_profile_json") or "null")
        except (ValueError, TypeError):
            profile = None
        if isinstance(profile, dict):
            safe["provider_profile"] = {
                "username": profile.get("username"),
                "name": profile.get("name"),
                "avatar": profile.get("avatar"),
                "has_gold": profile.get("has_gold"),
                "gold_expiry": profile.get("gold_expiry"),
                "gold_days_left": profile.get("gold_days_left"),
            }
    return safe


def admin_job_view(job):
    """Admin projection of a provider job (includes cost, keeps secrets out)."""
    if not job:
        return None
    view = dict(job)
    view.pop("payload_json", None)  # payload is available via hash/request id
    view["payload_hash_short"] = (job.get("payload_hash") or "")[:12]
    return view


# ---- Warranty policy -----------------------------------------------------

def add_calendar_months(start_ts, months):
    """Add whole months using calendar arithmetic (handles month-end/leap years)."""
    months = int(months)
    if months <= 0:
        return start_ts
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(float(start_ts), tz=timezone.utc)
    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    result = dt.replace(year=year, month=month, day=day)
    return result.timestamp()


def warranty_window(order, start_ts=None):
    """Return (start, end) only when an explicit shop policy is configured.

    Gold expiry is NEVER derived from warranty months: those are separate
    concepts and the provider owns Gold expiry.
    """
    if not order:
        return (None, None)
    policy = (order.get("warranty_policy_snapshot") or "").strip()
    months = order.get("warranty_months_snapshot")
    if policy != "shop_calendar_months" or not months:
        return (None, None)
    start = start_ts if start_ts is not None else order.get("provider_completed_at")
    if not start:
        return (None, None)
    return (start, add_calendar_months(start, months))
