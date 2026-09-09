"""Authenticated SePay webhook receiver.

This endpoint intentionally limits itself to transport authentication and
payload validation. Business fulfillment must be connected separately after
the merchant has reviewed and authorized that workflow.
"""

import hashlib
import hmac
import os
import time

from flask import Blueprint, current_app, jsonify, request


sepay_webhook_bp = Blueprint("sepay_webhook", __name__, url_prefix="/api/payment")

MAX_WEBHOOK_BODY_BYTES = 64 * 1024
DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 300


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
    if (
        not isinstance(transaction_id, int)
        or isinstance(transaction_id, bool)
        or transfer_type not in {"in", "out"}
        or not isinstance(transfer_amount, int)
        or isinstance(transfer_amount, bool)
        or transfer_amount < 0
    ):
        return _error("invalid_payload", "Payload webhook thiếu trường giao dịch hợp lệ.", 400)

    current_app.logger.info(
        "Verified SePay webhook transaction_id=%s transfer_type=%s",
        transaction_id,
        transfer_type,
    )

    # SePay expects HTTP 200 with this JSON body to consider delivery successful.
    return jsonify({"success": True}), 200

