"""Non-blocking Telegram notifications for paid orders and fulfillment events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import html
import logging
import os
import threading
from typing import Any

import requests
from flask import current_app, has_app_context


LOGGER = logging.getLogger(__name__)
TELEGRAM_API_ROOT = "https://api.telegram.org"
LOCAL_TIMEZONE = timezone(timedelta(hours=7))


def _is_truthy_env(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _telegram_config() -> tuple[str, str] | None:
    if not _is_truthy_env("TELEGRAM_NOTIFICATIONS_ENABLED"):
        return None
    if (
        has_app_context()
        and current_app.config.get("TESTING")
        and not _is_truthy_env("TELEGRAM_ALLOW_TEST_DELIVERY", "0")
    ):
        return None
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        return None
    return token, chat_id


def _escape(value: Any, max_length: int = 500) -> str:
    """Escape untrusted fields and cap them before building Telegram HTML."""
    return html.escape(str(value or "").strip()[:max_length], quote=True)


def _format_vnd(value: Any) -> str:
    try:
        amount = int(value or 0)
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:,}".replace(",", ".") + " đ"


def _format_time(timestamp: Any = None) -> str:
    try:
        value = float(timestamp) if timestamp is not None else datetime.now().timestamp()
    except (TypeError, ValueError):
        value = datetime.now().timestamp()
    return datetime.fromtimestamp(value, tz=LOCAL_TIMEZONE).strftime("%d/%m/%Y · %H:%M:%S")


def _order_admin_url() -> str | None:
    explicit = (os.getenv("TELEGRAM_ADMIN_ORDERS_URL") or "").strip()
    if explicit.startswith("https://"):
        return explicit
    return None


def _order_message(
    order: dict[str, Any],
    user: dict[str, Any],
    payment: dict[str, Any] | None = None,
) -> str:
    mode = order.get("fulfillment_mode_snapshot") or "auto_activation"
    payment_method = order.get("payment_method") or "coin"
    needs_admin = mode == "manual_contact"

    title = "ĐƠN MỚI · CẦN ADMIN XỬ LÝ" if needs_admin else "ĐƠN HÀNG ĐÃ THANH TOÁN"
    status = "Chờ Admin liên hệ" if needs_admin else {
        "auto_activation": "Đã chuyển vào luồng kích hoạt",
        "apk_download": "Đã mở quyền tải Android",
    }.get(mode, "Đã tiếp nhận")
    fulfillment = {
        "auto_activation": "Kích hoạt tự động",
        "manual_contact": "Admin liên hệ thủ công",
        "apk_download": "Tải ứng dụng Android",
    }.get(mode, mode)
    platform = "iOS" if order.get("platform") == "ios" else "Android"

    if payment_method == "qr":
        paid_value = _format_vnd(
            (payment or {}).get("amount_vnd", order.get("price_vnd_snapshot"))
        )
        payment_label = "Chuyển khoản VietQR"
    else:
        coin = int(order.get("price_coin_snapshot") or 0)
        paid_value = f"{coin:,} Coin".replace(",", ".")
        payment_label = "Ví Coin"

    display_name = (
        user.get("display_name")
        or user.get("username")
        or f"User #{order.get('user_id')}"
    )
    username = (user.get("username") or "").strip()
    email = user.get("email") or "—"
    transfer_code = (payment or {}).get("transfer_code") or (payment or {}).get(
        "payment_code"
    )

    lines = [
        f"🔔 <b>{_escape(title)}</b>",
        f"<b>{_escape(status)}</b>",
        "",
        f"<b>Mã đơn:</b> <code>#{_escape(order.get('id'))}</code>",
        f"<b>Gói:</b> {_escape(order.get('plan_name_snapshot'))}",
        f"<b>Nền tảng:</b> {_escape(platform)}",
        f"<b>Xử lý:</b> {_escape(fulfillment)}",
        "",
        f"<b>Thanh toán:</b> {_escape(payment_label)}",
        f"<b>Thực trả:</b> <b>{_escape(paid_value)}</b>",
    ]

    if transfer_code:
        lines.append(f"<b>Mã chuyển khoản:</b> <code>{_escape(transfer_code)}</code>")
    if order.get("coupon_code_snapshot"):
        discount = (
            _format_vnd(order.get("discount_vnd_snapshot"))
            if payment_method == "qr"
            else f"{int(order.get('discount_coin_snapshot') or 0)} Coin"
        )
        lines.append(
            f"<b>Ưu đãi:</b> <code>{_escape(order.get('coupon_code_snapshot'))}</code> · -{_escape(discount)}"
        )

    account_identity = f"@{_escape(username)}" if username else "Không có username"
    lines.extend(
        [
            "",
            f"<b>Khách hàng:</b> {_escape(display_name)}",
            f"<b>Tài khoản:</b> {account_identity} · {_escape(email)}",
        ]
    )

    if order.get("locket_username"):
        lines.append(f"<b>Locket:</b> @{_escape(order.get('locket_username'))}")
    if needs_admin:
        lines.extend(
            [
                "",
                "⚠️ <b>THÔNG TIN LIÊN HỆ</b>",
                f"<b>Zalo:</b> {_escape(order.get('contact_zalo') or 'Chưa cung cấp')}",
                f"<b>Facebook:</b> {_escape(order.get('contact_facebook') or 'Chưa cung cấp')}",
            ]
        )

    lines.extend(
        [
            "",
            f"<b>Thời gian:</b> {_escape(_format_time((payment or {}).get('paid_at') or order.get('created_at')))}",
        ]
    )
    return "\n".join(lines)


def _send_message(text: str, reply_markup: dict[str, Any] | None = None) -> bool:
    config = _telegram_config()
    if not config:
        return False
    token, chat_id = config
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(
            f"{TELEGRAM_API_ROOT}/bot{token}/sendMessage",
            json=payload,
            timeout=(3.05, 5),
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or body.get("ok") is not True:
            raise RuntimeError("telegram_api_rejected_message")
        return True
    except Exception as exc:
        # Never log the request URL because it contains the bot token.
        LOGGER.warning("Telegram notification failed (%s)", type(exc).__name__)
        return False


def _send_async(text: str, reply_markup: dict[str, Any] | None = None) -> bool:
    if not _telegram_config():
        return False
    thread = threading.Thread(
        target=_send_message,
        args=(text, reply_markup),
        daemon=True,
        name="telegram-notification",
    )
    thread.start()
    return True


def notify_paid_order(order_id: int, payment: dict[str, Any] | None = None) -> bool:
    """Notify the admin once a service order has been paid successfully."""
    if not _is_truthy_env("TELEGRAM_NOTIFY_NEW_ORDERS") or not _telegram_config():
        return False

    from . import db

    order = db.get_activation_order_by_id(order_id)
    if not order:
        LOGGER.warning("Telegram order notification skipped: order %s not found", order_id)
        return False
    user = db.get_user_by_id(order.get("user_id")) or {}
    text = _order_message(order, user, payment)

    reply_markup = None
    admin_url = _order_admin_url()
    if admin_url:
        reply_markup = {
            "inline_keyboard": [[{"text": "Mở đơn trong Admin", "url": admin_url}]],
        }
    return _send_async(text, reply_markup)


def send_telegram_notification(username, uid, product_id, raw_json):
    """Backward-compatible activation-success notification used by the worker."""
    if not _is_truthy_env("TELEGRAM_NOTIFY_ACTIVATION_SUCCESS"):
        return False

    entitlement = (
        (raw_json or {}).get("subscriber", {}).get("entitlements", {}).get("Gold", {})
    )
    expires_at = entitlement.get("expires_date") or "Không xác định"
    message = "\n".join(
        [
            "<b>KÍCH HOẠT ĐÃ HOÀN TẤT</b>",
            "",
            f"<b>Locket:</b> @{_escape(username)}",
            f"<b>UID:</b> <code>{_escape(uid)}</code>",
            f"<b>Sản phẩm:</b> {_escape(product_id)}",
            f"<b>Hết hạn:</b> {_escape(expires_at)}",
            f"<b>Thời gian:</b> {_escape(_format_time())}",
        ]
    )
    return _send_async(message)
