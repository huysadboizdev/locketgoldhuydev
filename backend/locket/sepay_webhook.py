"""Authenticated SePay webhook receiver and payment settlement entry point.

Only inbound transfers that match this application's bank account, transfer
code, expected amount, and supported payment purpose are settled. The shared
payment service owns the atomic state transition and fulfillment dispatch.
"""

import hashlib
import hmac
import os
import re
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request

from . import db, payment_service


sepay_webhook_bp = Blueprint("sepay_webhook", __name__, url_prefix="/api/payment")

MAX_WEBHOOK_BODY_BYTES = 64 * 1024
DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 300
DEFAULT_BANK_CLOCK_SKEW_SECONDS = 300
VIETNAM_TIMEZONE = timezone(timedelta(hours=7))


def _error(error: str, message: str, status: int):
    return jsonify({"success": False, "error": error, "msg": message}), status


def _webhook_enabled() -> bool:
    return os.getenv("PAYMENT_WEBHOOK_ENABLED", "0").strip() == "1"


def _timestamp_tolerance() -> int:
    raw = os.getenv(
        "SEPAY_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS",
        str(DEFAULT_TIMESTAMP_TOLERANCE_SECONDS),
    ).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_TIMESTAMP_TOLERANCE_SECONDS
    return max(30, min(value, 900))


def _bank_clock_skew() -> int:
    raw = os.getenv(
        "SEPAY_TRANSACTION_CLOCK_SKEW_SECONDS",
        str(DEFAULT_BANK_CLOCK_SKEW_SECONDS),
    ).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_BANK_CLOCK_SKEW_SECONDS
    return max(0, min(value, 900))


def _parse_bank_transaction_time(value) -> float | None:
    """Parse SePay's bank-local transaction time without trusting server receipt time."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VIETNAM_TIMEZONE)
    return parsed.timestamp()


def _paid_within_order_window(payload: dict, payment: dict) -> bool:
    """Allow delayed delivery only when the bank says payment happened on time."""
    transaction_time = _parse_bank_transaction_time(payload.get("transactionDate"))
    if transaction_time is None:
        return False
    try:
        created_at = float(payment["created_at"])
        expires_at = float(payment["expires_at"])
    except (KeyError, TypeError, ValueError):
        return False
    skew = _bank_clock_skew()
    return created_at - skew <= transaction_time <= expires_at + skew


def verify_sepay_hmac(raw_body: bytes, timestamp: str, signature: str) -> tuple[bool, str]:
    """Verify SePay's ``sha256=...`` signature over ``timestamp.raw_body``."""
    secret = (os.getenv("SEPAY_WEBHOOK_SECRET") or "").strip()
    if not secret:
        return False, "secret_not_configured"

    timestamp_text = (timestamp or "").strip()
    if not timestamp_text.isdigit():
        return False, "invalid_timestamp"

    timestamp_value = int(timestamp_text)
    if abs(int(time.time()) - timestamp_value) > _timestamp_tolerance():
        return False, "expired_timestamp"

    supplied_signature = (signature or "").strip().lower()
    if not supplied_signature.startswith("sha256="):
        return False, "invalid_signature_format"

    signed_payload = timestamp_text.encode("ascii") + b"." + raw_body
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    expected_signature = f"sha256={digest}"
    if not hmac.compare_digest(expected_signature, supplied_signature):
        return False, "invalid_signature"

    return True, "ok"


def _normalize_account_number(value) -> str:
    """Normalize harmless formatting while keeping account comparison strict."""
    return re.sub(r"[\s.-]", "", str(value or "")).upper()


def _configured_webhook_accounts() -> frozenset[str]:
    """Return the exact bank-account identifiers accepted from SePay.

    Banks can render a VietQR account alias (for example ``HUYDEV204``) while
    SePay reports the underlying numeric account in ``accountNumber``.  Keep
    QR rendering and webhook reconciliation as separate settings, but include
    the QR identifier as a backwards-compatible accepted value.
    """
    raw_accounts = os.getenv("SEPAY_WEBHOOK_ACCOUNT_NUMBERS", "")
    candidates = re.split(r"[,;\r\n]+", raw_accounts)
    candidates.append(payment_service.get_bank_config().get("account_no", ""))
    return frozenset(
        normalized
        for normalized in (_normalize_account_number(value) for value in candidates)
        if normalized
    )


def _masked_account(value: str) -> str:
    normalized = _normalize_account_number(value)
    if len(normalized) <= 4:
        return "*" * len(normalized)
    return f"{'*' * (len(normalized) - 4)}{normalized[-4:]}"


def _extract_transfer_code(payload: dict) -> str | None:
    """Extract this application's transfer code from SePay fields.

    SePay's parsed ``code`` may be empty when the merchant-side code pattern is
    not configured, so the original bank content is checked as a fallback.
    """
    prefix = payment_service.get_transfer_prefix()
    digits = payment_service.get_transfer_digits()
    if not prefix or digits < 1 or digits > 30:
        return None

    pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(prefix)}[0-9]{{{digits}}}(?![A-Z0-9])", re.IGNORECASE)
    for field in ("code", "content", "description"):
        candidate = str(payload.get(field) or "").strip()
        if not candidate:
            continue
        match = pattern.search(candidate)
        if match:
            return match.group(0).upper()
    return None


def _acknowledge():
    """Return the exact acknowledgement shape expected by SePay."""
    return jsonify({"success": True}), 200


def _process_payment(payload: dict):
    """Settle one matching top-up or plan purchase, atomically and idempotently."""
    if payload["transferType"] != "in":
        current_app.logger.info(
            "Ignored outgoing SePay transaction transaction_id=%s", payload["id"]
        )
        return _acknowledge()

    received_account = _normalize_account_number(payload.get("accountNumber"))
    configured_accounts = _configured_webhook_accounts()
    if not received_account or received_account not in configured_accounts:
        current_app.logger.warning(
            "Ignored SePay transaction for an unexpected account "
            "transaction_id=%s received_account=%s configured_account_count=%s",
            payload["id"],
            _masked_account(received_account),
            len(configured_accounts),
        )
        return _acknowledge()

    transfer_code = _extract_transfer_code(payload)
    if not transfer_code:
        current_app.logger.info(
            "Ignored SePay transaction without a matching transfer code transaction_id=%s",
            payload["id"],
        )
        return _acknowledge()

    payment = db.get_payment_order_by_code(transfer_code)
    if not payment or payment.get("purpose") not in {"wallet_topup", "plan_purchase"}:
        current_app.logger.info(
            "Ignored SePay transaction without a supported payment order transaction_id=%s",
            payload["id"],
        )
        return _acknowledge()

    bank_transaction_id = f"SEPAY_{payload['id']}"
    if payment.get("status") == "paid":
        if payment.get("bank_transaction_id") == bank_transaction_id:
            return _acknowledge()
        current_app.logger.warning(
            "Ignored SePay transaction for an already-paid order transaction_id=%s payment_id=%s",
            payload["id"],
            payment["id"],
        )
        return _acknowledge()

    if payload["transferAmount"] != payment.get("amount_vnd"):
        current_app.logger.warning(
            "Ignored SePay amount mismatch transaction_id=%s payment_id=%s",
            payload["id"],
            payment["id"],
        )
        return _acknowledge()

    recover_expired = _paid_within_order_window(payload, payment)
    status, result = payment_service.confirm_payment(
        payment_id_or_ref=payment["id"],
        bank_transaction_id=bank_transaction_id,
        current_app_instance=current_app._get_current_object(),
        recover_expired=recover_expired,
    )
    if status in {"ok", "already_paid", "expired", "not_found"}:
        if status == "ok":
            current_app.logger.info(
                "Settled SePay payment transaction_id=%s payment_id=%s purpose=%s",
                payload["id"],
                payment["id"],
                payment["purpose"],
            )
        else:
            current_app.logger.warning(
                "SePay payment not settled status=%s transaction_id=%s payment_id=%s purpose=%s",
                status,
                payload["id"],
                payment["id"],
                payment["purpose"],
            )
        return _acknowledge()

    current_app.logger.error(
        "Failed to settle SePay payment transaction_id=%s payment_id=%s purpose=%s status=%s error=%s",
        payload["id"],
        payment["id"],
        payment["purpose"],
        status,
        str(result)[:200],
    )
    return _error(
        "payment_processing_failed",
        "Không thể xử lý giao dịch lúc này; SePay sẽ thử gửi lại.",
        500,
    )


@sepay_webhook_bp.post("/webhook")
def receive_sepay_webhook():
    """Authenticate and acknowledge a SePay JSON webhook event."""
    if not _webhook_enabled():
        return _error("webhook_disabled", "Webhook thanh toán đang bị tắt.", 503)

    if not (os.getenv("SEPAY_WEBHOOK_SECRET") or "").strip():
        current_app.logger.error("SEPAY_WEBHOOK_SECRET is not configured")
        return _error(
            "webhook_not_configured",
            "Webhook SePay chưa được cấu hình trên máy chủ.",
            503,
        )

    raw_body = request.get_data(cache=True)
    if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        return _error("payload_too_large", "Payload webhook vượt quá giới hạn.", 413)

    verified, reason = verify_sepay_hmac(
        raw_body,
        request.headers.get("X-SePay-Timestamp", ""),
        request.headers.get("X-SePay-Signature", ""),
    )
    if not verified:
        current_app.logger.warning("Rejected SePay webhook: %s", reason)
        return _error("invalid_webhook_signature", "Chữ ký webhook không hợp lệ.", 401)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("invalid_payload", "Payload webhook phải là JSON object.", 400)

    transaction_id = payload.get("id")
    transfer_type = payload.get("transferType")
    transfer_amount = payload.get("transferAmount")
    account_number = payload.get("accountNumber")
    if (
        not isinstance(transaction_id, int)
        or isinstance(transaction_id, bool)
        or transfer_type not in {"in", "out"}
        or not isinstance(transfer_amount, int)
        or isinstance(transfer_amount, bool)
        or transfer_amount <= 0
        or not isinstance(account_number, str)
        or not account_number.strip()
    ):
        return _error("invalid_payload", "Payload webhook thiếu trường giao dịch hợp lệ.", 400)

    current_app.logger.info(
        "Verified SePay webhook transaction_id=%s transfer_type=%s",
        transaction_id,
        transfer_type,
    )

    return _process_payment(payload)
