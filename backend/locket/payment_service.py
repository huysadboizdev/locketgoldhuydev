import os
import re
import secrets
import time
import urllib.parse
from . import db

TRANSFER_CODE_REGEX = re.compile(r"^LOCKETGOLDHUYDEV[0-9]{3}$")


class PaymentCodePoolExhaustedError(Exception):
    """Raised when all transfer codes in the pool (000-999) are currently in use or quarantined."""
    pass


PoolExhaustedError = PaymentCodePoolExhaustedError


class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused with a different payload."""
    pass


def get_bank_config():
    """Return configured bank details for VietQR without leaking secrets."""
    bank_id = os.environ.get("VIETQR_BANK_ID", "TPB").strip()
    account_no = os.environ.get("VIETQR_ACCOUNT_NO", "HUYDEV204").strip()
    account_name = os.environ.get("VIETQR_ACCOUNT_NAME", "HA QUANG HUY").strip()
    template = os.environ.get("VIETQR_TEMPLATE", "compact2").strip()
    return {
        "bank_id": bank_id,
        "account_no": account_no,
        "account_name": account_name,
        "template": template,
        "is_configured": bool(bank_id and account_no),
    }


def get_payment_config():
    """Return payment system runtime configurations."""
    prefix = os.environ.get("PAYMENT_TRANSFER_PREFIX", "LOCKETGOLDHUYDEV").strip()
    digits = int(os.environ.get("PAYMENT_TRANSFER_DIGITS", "3"))
    ttl = int(os.environ.get("PAYMENT_TTL_SECONDS", "600"))
    reuse_delay = int(os.environ.get("PAYMENT_CODE_REUSE_DELAY_SECONDS", "86400"))
    webhook_enabled = os.environ.get("PAYMENT_WEBHOOK_ENABLED", "0") == "1"
    return {
        "prefix": prefix,
        "digits": digits,
        "ttl": ttl,
        "reuse_delay": reuse_delay,
        "webhook_enabled": webhook_enabled,
    }


def get_transfer_prefix():
    """Return configured prefix for bank transfer code."""
    return get_payment_config()["prefix"]


def get_transfer_digits():
    """Return number of digits in transfer code pool (default 3)."""
    return get_payment_config()["digits"]


def get_payment_ttl_seconds():
    """Return standard payment TTL in seconds (default 600s = 10 min)."""
    return get_payment_config()["ttl"]


def sweep_expired_pending_payments():
    """Sweep overdue pending payment orders and mark them expired."""
    conn = db.get_conn()
    now = time.time()
    cur = conn.execute(
        "UPDATE payment_orders SET status = 'expired', updated_at = ? WHERE status = 'pending' AND expires_at < ?",
        (now, now),
    )
    from . import coupon_service
    coupon_service.sweep_expired_reservations(conn, now)
    conn.commit()
    return cur.rowcount


def generate_internal_payment_code(prefix="PAY"):
    """Generate unique unpredictable internal reference code using secrets module."""
    token = secrets.token_hex(8).upper()
    return f"{prefix}_{token}"


def generate_payment_code(prefix=None):
    """Backward-compatible payment code generator using secrets module.
    Cryptographically secure generator.
    """
    if prefix is None or prefix in ("LK", "TOP", "ORD"):
        return generate_internal_payment_code("PAY")
    return generate_internal_payment_code(prefix)


def generate_transfer_code():
    """Generate a single random 3-digit transfer code formatted with leading zeros.
    Uses secrets.randbelow to guarantee cryptographic entropy.
    """
    cfg = get_payment_config()
    prefix = cfg["prefix"]
    digits = cfg["digits"]
    val = secrets.randbelow(10 ** digits)
    return f"{prefix}{val:0{digits}d}"


def allocate_transfer_code(conn=None, now=None, exclude_code=None):
    """Atomically allocate an available transfer code from the 000-999 pool.
    Must be called inside an active SQLite transaction (e.g. BEGIN IMMEDIATE).

    Quarantine rules:
    - Code is unavailable if currently attached to a pending order with expires_at >= now.
    - Code is unavailable if used in an order created or updated within PAYMENT_CODE_REUSE_DELAY_SECONDS (24h).
    - When renewing, exclude_code is avoided if possible to ensure the renewed code is fresh.

    If pool is completely exhausted, raises PaymentCodePoolExhaustedError (HTTP 503).
    """
    if conn is None:
        conn = db.get_conn()
    if now is None:
        now = time.time()

    cfg = get_payment_config()
    prefix = cfg["prefix"]
    digits = cfg["digits"]
    reuse_delay = cfg["reuse_delay"]
    pool_size = 10 ** digits

    # 1. Sweep any pending payments whose TTL expired into 'expired' status
    conn.execute(
        "UPDATE payment_orders SET status = 'expired', updated_at = ? WHERE status = 'pending' AND expires_at < ?",
        (now, now),
    )

    # 2. Query unavailable / quarantined transfer codes
    cutoff = now - reuse_delay
    rows = conn.execute(
        """SELECT DISTINCT transfer_code FROM payment_orders
           WHERE transfer_code IS NOT NULL AND (
               (status = 'pending' AND expires_at >= ?)
               OR (updated_at > ? OR created_at > ?)
           )""",
        (now, cutoff, cutoff),
    ).fetchall()
    unavailable = {r[0] for r in rows if r[0]}

    # 3. Try random selection up to 30 times for speed under low-to-medium contention
    for _ in range(30):
        val = secrets.randbelow(pool_size)
        candidate = f"{prefix}{val:0{digits}d}"
        if candidate not in unavailable and candidate != exclude_code:
            return candidate

    # 4. If random collisions happen (pool is tight), scan all candidates deterministically
    all_candidates = [f"{prefix}{i:0{digits}d}" for i in range(pool_size)]
    available = [c for c in all_candidates if c not in unavailable and c != exclude_code]
    if not available and exclude_code and exclude_code not in unavailable:
        return exclude_code

    if available:
        return secrets.choice(available)

    raise PaymentCodePoolExhaustedError("All transfer codes in pool are currently in use or in quarantine.")


def build_vietqr_url(amount_vnd=None, transfer_code=None, bank_id=None, account_no=None, account_name=None, template=None, **kwargs):
    """Build dynamic VietQR quick link URL using URL-encoded parameters."""
    cfg = get_bank_config()
    b_id = (bank_id or cfg["bank_id"]).strip()
    acc_no = (account_no or cfg["account_no"]).strip()
    acc_name = (account_name or kwargs.get("account_name") or cfg["account_name"]).strip()
    tmpl = (template or cfg["template"]).strip()
    amt = amount_vnd if amount_vnd is not None else kwargs.get("amount", 0)
    info = transfer_code if transfer_code is not None else kwargs.get("add_info", "")

    params = urllib.parse.urlencode({
        "amount": int(amt),
        "addInfo": str(info).strip(),
        "accountName": acc_name,
    })

    return f"https://img.vietqr.io/image/{b_id}-{acc_no}-{tmpl}.png?{params}"


def dispatch_paid_activation_order(order_id, app=None):
    """Unified fulfillment dispatcher for activation orders in paid/awaiting_queue states.
    Used by:
    1) Coin purchase (routes.py: create_coin_order)
    2) SePay/VietQR confirmation (payment_service.py: confirm_payment)
    3) Admin manual confirmation (admin_api.py: payment_confirm / payment_manual_confirm)
    4) Retry activation

    Behavior per fulfillment mode:
    - auto_activation:
        * If order["queue_client_id"] already set, return ("ok", order) (deduplication)
        * Otherwise enqueue to app.queue_manager.add_to_queue(...)
        * If queue manager fails/raises, leaves order in recoverable paid/awaiting_queue state and returns ("queue_error", ...) without failing payment
    - manual_contact:
        * Stays in 'paid' status (Waiting for Admin contact)
        * Do NOT enqueue to queue_manager
        * Return ("ok", order)
    - apk_download:
        * Transitions to 'completed' status immediately if not already completed
        * Do NOT enqueue to queue_manager
        * Return ("ok", order)
    """
    act_row = db.get_activation_order_by_id(order_id)
    if not act_row:
        return ("not_found", "Không tìm thấy đơn kích hoạt.")

    mode = act_row.get("fulfillment_mode_snapshot") or "auto_activation"
    target_app = app
    if not target_app:
        try:
            from flask import current_app
            target_app = current_app._get_current_object()
        except Exception:
            target_app = None

    if mode == "auto_activation":
        if act_row.get("queue_client_id"):
            return ("ok", dict(act_row))

        if target_app and hasattr(target_app, "queue_manager") and target_app.queue_manager:
            try:
                client_id = target_app.queue_manager.add_to_queue(
                    username=act_row["locket_username"],
                    user_id=act_row["user_id"],
                    platform=act_row["platform"],
                    plan_id=act_row["plan_id"],
                    activation_order_id=act_row["id"],
                )
                refreshed = db.get_activation_order_by_id(order_id)
                res_order = dict(refreshed) if refreshed else dict(act_row)
                res_order["queue_client_id"] = client_id
                return ("ok", res_order)
            except Exception as exc:
                if getattr(target_app, "logger", None):
                    target_app.logger.exception(
                        "Failed to enqueue activation order %s: %s", order_id, exc
                    )
                return ("queue_error", {"order": dict(act_row), "error": str(exc)[:200]})
        return ("ok", dict(act_row))

    elif mode == "manual_contact":
        return ("ok", dict(act_row))

    elif mode == "apk_download":
        if act_row.get("status") != "completed":
            conn = db.get_conn()
            now = time.time()
            conn.execute(
                "UPDATE activation_orders SET status = 'completed', updated_at = ? WHERE id = ?",
                (now, order_id),
            )
            conn.commit()
            refreshed = db.get_activation_order_by_id(order_id)
            return ("ok", dict(refreshed) if refreshed else dict(act_row))
        return ("ok", dict(act_row))

    return ("ok", dict(act_row))


def confirm_payment(payment_id_or_ref, bank_transaction_id=None, current_app_instance=None,
                    audit_context=None, manual_override=False, manual_reason=None):
    """Shared payment confirmation service.
    Can be called by Admin manual confirmation route or future webhook listeners.
    Verifies pending status, checks expiry, performs atomic wallet topup or activation enqueue.
    Returns ('ok', payment_dict) or ('error_code', reason_message).
    """
    if isinstance(payment_id_or_ref, int) or (isinstance(payment_id_or_ref, str) and payment_id_or_ref.isdigit()):
        pay = db.get_payment_order_by_id(int(payment_id_or_ref))
    else:
        pay = db.get_payment_order_by_code(str(payment_id_or_ref))

    if not pay:
        return ("not_found", "Không tìm thấy giao dịch thanh toán.")

    payment_id = pay["id"]
    bank_tx_id = (bank_transaction_id or "").strip()
    if not bank_tx_id:
        bank_tx_id = f"MANUAL_ADMIN_{payment_id}_{int(time.time())}_{secrets.token_hex(3).upper()}"

    status, res = db.confirm_payment_order_tx(
        payment_id,
        bank_tx_id,
        audit_context=audit_context,
        manual_override=manual_override,
        manual_reason=manual_reason,
    )
    if status != "ok":
        return (status, res)

    pay_order = res
    # Dispatch the paid order according to the immutable fulfillment snapshot.
    if pay_order["purpose"] == "plan_purchase":
        conn = db.get_conn()
        act_row = conn.execute(
            "SELECT id FROM activation_orders WHERE payment_order_id = ?", (payment_id,)
        ).fetchone()
        if act_row:
            disp_status, disp_res = dispatch_paid_activation_order(
                act_row["id"], app=current_app_instance
            )
            dispatched = disp_res.get("order", {}) if disp_status == "queue_error" else disp_res
            pay_order["fulfillment_mode"] = dispatched.get("fulfillment_mode_snapshot", "auto_activation")
            pay_order["activation_order_id"] = dispatched.get("id", act_row["id"])
            pay_order["activation_status"] = dispatched.get("status")
            if dispatched.get("queue_client_id"):
                pay_order["queue_client_id"] = dispatched["queue_client_id"]
            if disp_status == "queue_error":
                pay_order["queue_enqueue_failed"] = True
                pay_order["queue_error"] = disp_res.get("error", "Enqueue failed")

    return ("ok", pay_order)


def reject_payment(payment_id_or_ref, status="cancelled", note=None, audit_context=None):
    """Reject a payment by numeric id or public payment/transfer code.

    The database function performs the payment transition, linked activation
    cancellation, and optional admin audit insertion in one transaction.
    """
    if isinstance(payment_id_or_ref, int) or (
        isinstance(payment_id_or_ref, str) and payment_id_or_ref.isdigit()
    ):
        pay = db.get_payment_order_by_id(int(payment_id_or_ref))
    else:
        pay = db.get_payment_order_by_code(str(payment_id_or_ref))

    if not pay:
        return ("not_found", "Payment order was not found.")

    result, payload = db.reject_payment_order_tx(
        pay["id"], status=status, note=note, audit_context=audit_context
    )
    if result != "ok":
        return (result, payload)
    return ("ok", payload)
